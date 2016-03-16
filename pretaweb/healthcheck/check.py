from datetime import datetime
from datetime import timedelta
from lxml import etree
from os import getenv
from plone.app.layout.navigation.interfaces import INavigationRoot
from plone.subrequest import subrequest
from Products.CMFPlone.interfaces.siteroot import IPloneSiteRoot
from random import choice
from random import randint
from StringIO import StringIO
from time import time
from ZODB.POSException import ConflictError

import logging
import re
import urllib


logger = logging.getLogger(__name__)

STATUS_ERROR = 500
STATUS_HEALTHY = 200

CSS_IMPORT_RE = re.compile(r'@import\s+url\([\'"]{0,1}([^)]+?)[\'"]{0,1}\)')

INTERVAL = int(getenv('healthcheck_cache_interval', 3600))
INTERVAL_VARIANCE = int(getenv('healthcheck_cache_variance',  1800))


class RequestError(Exception):
    def __init__(self, url, status):
        self.url = url
        self.status = status


class ServerError(RequestError):
    pass


class PloneLoader(object):
    def __init__(self, base, host, uses_https, url):
        self.start_url = url
        self.base = base
        self.host = host
        self.uses_https = uses_https
        self.urls = set()

    def _request(self, url, raises):
        logger.info('Calling %r',
                    url)
        response = subrequest(url)
        status = response.getStatus()
        if status >= 400:
            raise RequestError(url=url, status=status)
        return response

    def _wake_resource(self, url, start_url=None):
        if url in self.urls:
            return
        if not start_url:
            start_url = self.start_url
        self._lastRequestedURL = url
        response = subrequest(url)
        status = response.getStatus()
        if status == 200:
            logger.debug('Successfully loaded %r',
                         url)
            self.urls.add(url)
            return response

        elif 300 <= status < 400:
            logger.info('Page %r contains a reference on %r '
                        'but redirects with status code %r. '
                        'The Resource was not woken up. Fix your page',
                        start_url, url, status)
        else:
            logger.error('Page %r contains a reference to %r. '
                         'Trying to load the resource triggered an error '
                         'with status code %r',
                         start_url, url, status)
        self.urls.add(url)
        return None

    def _wake_css_resource(self, url):
        cssURLResourcePattern = re.compile(r"url\('?([^')]+)'?\)")

        # Get css resources and parse for url(...) directives

        response = self._wake_resource(url)
        if not response:
            return
        body = response.getBody()
        if not body:
            return

        if not (url.endswith('.css') or
                response.getHeader('content-type').startswith('text/css')):
            return
        if url.endswith('.kss'):
            return
        # get CSS working path
        workingPath = url.split('/')
        workingPath.pop()
        workingPath = self.base + '/'.join(workingPath)

        # parse URLs
        for match in cssURLResourcePattern.finditer(body):
            groups = match.groups()
            if len(groups) > 0:
                ref_url = '/'.join(url.split('/')[:-1])
                normalized_link = self._normalize_link(ref_url, groups[0])
                if normalized_link is None:
                    continue
                self._wake_resource(normalized_link, url)

    def _normalize_link(self, reference_url, link):
        base = self.base

        protocol = 'https' if self.uses_https else 'http'

        link = link.split('#')[0]
        if not len(link):
            return None
        link = urllib.unquote(link)
        if link[0] == '/':
            link = protocol + '://' + self.host + link
        link = link.rstrip('/')

        # Link same as base - ignore
        if reference_url == link:
            return None

        # Absolute URL - add without base
        if link.startswith(base):
            p = link[len(base):]
            return p

        # Relative URL - add with workingURL
        elif not (link.startswith('http://') or link.startswith('https://')):
            ll = reference_url + '/' + link
            if reference_url.startswith(base):
                return ll[len(base):]
            return ll

        else:
            logger.debug('\tResource out of scope: %s', link)

        return None

    def __call__(self):
        try:
            response = self._request(self.start_url, raises=True)
        except RequestError, e:
            if e.status == 401:
                logger.info('I tried to warm up a Plone site %r that '
                            'is private',
                            self.start_url)
                return
            else:
                raise
        body = response.getBody()

        logger.info('Plone site %s, Status %s',
                    self.start_url, response.getStatus())

        try:
            tree = etree.parse(StringIO(body), etree.HTMLParser())
        except etree.XMLSyntaxError:
            logger.warning('Error parsing the front page', exc_info=True)
            return

        self.process_body(body, tree)

    def process_body(self, body, tree):
        normal_links = tree.xpath('/html/body//a/@href|'
                                  '/html/body//img/@src|'
                                  '/html//script/@src')
        for link in normal_links:
            normalized_link = self._normalize_link(self.start_url, link)
            if normalized_link is None:
                continue
            self._wake_resource(normalized_link)

        for css_link in tree.xpath('/html//link/@href'):
            normalized_link = self._normalize_link(self.start_url, css_link)
            if normalized_link is None:
                continue
            self._wake_css_resource(normalized_link)

        for match in CSS_IMPORT_RE.finditer(body):
            groups = match.groups()
            if len(groups) > 0:
                normalized_link = self._normalize_link(self.start_url,
                                                       groups[0])
                if normalized_link is None:
                    continue
                self._wake_css_resource(normalized_link)


class HealthCheck(object):
    """
    Query URLs, recursivly.
    """
    def __init__(self,
                 last_result,
                 expire_time,
                 context,
                 traverser,
                 base,
                 host,
                 use_https,
                 paths=None,
                 ):
        self.last_result = last_result
        self.expire_time = expire_time
        self.context = context
        self.traverser = traverser
        self.base = base
        self.host = host
        self.use_https = use_https
        self.paths = paths

    def __call__(self):
        if datetime.utcnow() < self.expire_time:
            return self.expire_time, self.last_result
        start = time()

        try:
            if self.last_result == STATUS_HEALTHY:
                logger.info('Doing limited recheck')
                self._wake_plone(choice(list(self._get_pages())))
            else:
                logger.info('Doing full check')
                for plone in self._get_pages():
                    self._wake_plone(plone)
        except Exception, e:
            if isinstance(e, ConflictError):
                raise
            logger.exception('Healthcheck found a problem')
            # Instance no longer healthy
            result = STATUS_ERROR
        else:
            logger.info('Finished health check in %i. Passed.',
                        time() - start)
            result = STATUS_HEALTHY

        new_expire_in = INTERVAL + randint(0, INTERVAL_VARIANCE)
        new_expire = datetime.utcnow() + timedelta(seconds=new_expire_in)

        logger.info('Next health check in %s', new_expire.isoformat())

        return new_expire, result

    def _get_pages(self):
        logger.debug('Checking a list of given paths')
        if self.paths:
            return self._get_path_filtered_pages()
        else:
            return self._get_all_plone_and_navroots()

    def _get_path_filtered_pages(self):
        logger.debug('Checking all toplevel plone pages and their '
                     'direct nav root pages')
        for path in self.paths:
            try:
                yield self.context.unrestrictedTraverse(path)
            except KeyError:
                logger.warning(('I was asked to to a halth check for %r '
                                'but I cannot find an object on this '
                                'path. I ignore this'), path)
                continue

    def _get_all_plone_and_navroots(self):
        for item in self.context.values():
            if IPloneSiteRoot.providedBy(item):
                if INavigationRoot.providedBy(item):
                    yield item
                for sub_item in item.values():
                    if INavigationRoot.providedBy(sub_item):
                        yield sub_item
            elif INavigationRoot.providedBy(item):
                yield item

    def _wake_plone(self, plone):
        url = '/'.join(plone.getPhysicalPath())
        plone_loader = PloneLoader(self.base, self.host, self.use_https, url)
        plone_loader()
