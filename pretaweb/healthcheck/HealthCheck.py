from datetime import datetime, timedelta
import logging
import re
import traceback
import urllib
from lxml import etree
from StringIO import StringIO

from plone.subrequest import subrequest
from Products.Five import BrowserView

from Products.CMFPlone.interfaces.siteroot import IPloneSiteRoot

from random import random

logger = logging.getLogger(__name__)

STATUS_ERROR = 500
STATUS_HEALTHY = 200

healthCheckResult = None
healthCheckExpire = None

healthCheckIntervalMin = timedelta(minutes=5)
healthCheckIntervalMax = timedelta(minutes=10)


class RequestError (Exception):
    pass


class ServerError (RequestError):
    pass


class HealthCheck (BrowserView):

    _lastRequestedURL = None

    def parseLinks(self, workingPath, links):
        base = self.request.base
        workingURL = base + workingPath
        host = self.request.environ.get('HTTP_HOST')

        if self.request.environ.get('HTTPS', False):
            protocol = 'https'
        else:
            protocol = 'http'

        newLinks = set()
        for l in links:

            # Unfortuantly there are ^still^ GET requests in plone
            # which have side affects. Most notably:
            # xxx/content_status_modify?workflow_action=retract
            # which has a habbit of bringing down the front page if the
            # healthchecker somehow gets admin access.
            if '?' in l:
                pass

            l = l.split('#')[0]
            if not len(l):
                continue
            l = urllib.unquote(l)
            if l[0] == '/':
                l = protocol + '://' + host + l
            l = l.rstrip('/')

            # Link same as base - ignore
            if workingURL == l:
                continue

            # Absolute URL - add without base
            if l.startswith(base):
                p = l[len(base):]
                newLinks.add(p)

            # Relative URL - add with workingURL
            elif not (l.startswith('http://') or l.startswith('https://')):
                ll = workingURL + '/' + l
                p = ll[len(base):]
                newLinks.add(p)

            # Other URLs
            else:
                if self.verbose:
                    logger.debug('\tResource out of scope: %s', l)

        return newLinks

    def wakeResources(self, resources):
        byteCount = 0

        for url in resources:
            self._lastRequestedURL = url
            response = subrequest(url)
            status = response.getStatus()
            if status == 200:
                body = response.getBody()
                byteCount += len(body)

                if self.verbose:
                    logger.debug(
                        '\tGot status %s for resource: %s',
                        status, url)

            elif status >= 500:
                if not self.ignoreResourceServerError:
                    logger.info(
                        '\tGot status %s for resource: %s',
                        status, url)
                    raise ServerError()
                else:
                    logger.debug(
                        '\tGot status %s for resource: %s',
                        status, url)
            else:
                logger.debug(
                    '\tGot status %s for resource: %s',
                    status, url)

        return byteCount

    def wakeCssResources(self, resources, alreadyDone):
        byteCount = 0
        urlResources = set()
        cssURLResourcePattern = re.compile(r"url\('?([^')]+)'?\)")

        # Get css resources and parse for url(...) directives

        for url in resources:
            self._lastRequestedURL = url
            response = subrequest(url)
            status = response.getStatus()

            if status == 200:

                if self.verbose:
                    logger.info(
                        '\tGot status %s for resource: %s',
                        status, url)

                body = response.getBody()
                byteCount += len(body)

                # detect if document is CSS
                if (url.endswith('.css') or response.getHeader(
                        'content-type').startswith('text/css')):
                    if url.endswith('.kss'):
                        continue

                    # get CSS working path
                    workingPath = url.split('/')
                    workingPath.pop()
                    workingPath = self.request.base + '/'.join(workingPath)

                    # parse URLs
                    foundURLs = []
                    for mo in cssURLResourcePattern.finditer(body):
                        groups = mo.groups()
                        if len(groups) > 0:
                            foundURLs.append(groups[0])
                    urlResources = urlResources.union(
                        self.parseLinks(workingPath, foundURLs))

                else:
                    logger.debug('\tNot a CSS document: %s', url)

            elif status >= 500:
                if not self.ignoreResourceServerError:
                    logger.info(
                        '\tGot status %s for resource: %s',
                        status, url)
                    raise ServerError()
                logger.debug(
                    '\tGot status %s for resource: %s',
                    status, url)

            else:
                logger.debug(
                    '\tGot status %s for resource: %s',
                    status, url)

        # wake those extra resources

        alreadyDone = alreadyDone.union(resources)
        logger.debug(
            '\tFound %s resources referenced from CSS',
            len(urlResources))
        byteCount += self.wakeResources(urlResources)

        return byteCount

    def wakePlone(self, plone):
        """Pre-caching mechenisim for plones sites. By making sub requests
        to bring objects into memory"""
        cssImportPattern = re.compile(r'@import\s+url\(([^)]+)\)\s*;')

        # Request the front page

        url_path = '/'.join(plone.getPhysicalPath())
        self._lastRequestedURL = url_path
        response = subrequest(url_path)
        status = int(response.getStatus())

        logger.info('Plone Site: %s', url_path)
        logger.debug('\tHTTP status: %s', status)

        if status >= 400 and status != 401:
            # Bad news - 4xx (client) and 5xx (server) errors.
            # With the exception of 401 for unautherized access
            # which is an acceptable error
            raise RequestError()

        # Process output

        byteCount = 0
        body = response.getBody()
        byteCount += len(body)

        try:
            doc = etree.parse(StringIO(body), etree.HTMLParser())
        except etree.XMLSyntaxError:
            logger.debug('\tWarning: XMLSyntaxError on front page')
        else:
            links = doc.xpath('/html/body//a/@href')
            images = doc.xpath('/html/body//img/@src')
            headLink = doc.xpath('/html//link/@href')
            scripts = doc.xpath('/html//script/@src')

            cssImports = []
            for mo in cssImportPattern.finditer(body):
                groups = mo.groups()
                if len(groups) > 0:
                    cssImports.append(groups[0])

            resources = self.parseLinks(url_path, links)
            resources = resources.union(self.parseLinks(url_path, images))
            resources = resources.union(self.parseLinks(url_path, scripts))

            logger.debug('\tFound %s sub resources to load.', len(resources))
            byteCount += self.wakeResources(resources)

            cssResources = self.parseLinks(url_path, headLink)
            cssResources = cssResources.union(
                self.parseLinks(url_path, cssImports))
            cssResources = cssResources.difference(resources)

            logger.debug(
                '\tFound %s css resources to load.',
                len(cssResources))
            byteCount += self.wakeCssResources(cssResources,
                                               alreadyDone=resources)

        logger.info(
            'Approximate of bytes retrieved for site resources: %s',
            len(body))

    def wakeVHPlones(self, recheck=False):
        context = self.context

        # use the virtual hosting definitions for plone discovery.
        # Sort randomly since on subsequent calls to healthcheck
        # healthcheck is only looking for one live site.
        vh = context.virtual_hosting
        plone_paths = set([tuple(line.split('/')[1:])
                           for line in vh.lines if '/' in line])
        plone_paths = list(plone_paths)
        plone_paths.sort(key=lambda x: random())

        logger.info(
            '%s entrie(s) found in virtual host monster.',
            len(plone_paths))

        plones_discovered = 0

        for path in plone_paths:
            obj = context.restrictedTraverse(path)
            if IPloneSiteRoot.providedBy(obj):
                plones_discovered += 1

                if recheck:
                    # absorbe exceptions on a recheck, we are only trying to
                    # finde a single healthy site
                    try:
                        self.wakePlone(obj)
                    except:
                        logger.info(
                            'Exception raised during recheck (non fatal)')
                        logger.info(
                            'Last requested URL: %s',
                            self._lastRequestedURL)
                        logger.info(traceback.format_exc())
                    else:
                        return
                else:
                    # exceptions... let it be.
                    self.wakePlone(obj)

        if plones_discovered > 0 and recheck:
            raise Exception('No healthy Plones found on recheck')

        return

    def recheck(self):
        logger.info(
            'Recheck - finding single healthy site in virtual_hosting maps...')
        try:
            self.wakeVHPlones(recheck=True)

        except:
            # Instance no longer healthy
            logger.info('Exception raised during health recheck.')
            status = STATUS_ERROR
            logger.info(traceback.format_exc())

        else:
            logger.info('Finished health recheck. Pass.')
            status = STATUS_HEALTHY

        return status

    def comprehensiveCheck(self):

        logger.info(
            'Comprehensive check - testing all sites '
            'in virtual_hosting maps...')
        try:
            self.wakeVHPlones()
        except:
            # Instance not healthy
            logger.info('Exception raised during health check.')
            status = STATUS_ERROR

            logger.info('Last requested URL: %s', self._lastRequestedURL)
            logger.info(traceback.format_exc())

        else:
            logger.info('Finished health check. Pass.')
            status = STATUS_HEALTHY

        return status

    def healthStatus(self):

        global healthCheckResult
        global healthCheckExpire

        now = datetime.now()
        if healthCheckExpire is not None and now < healthCheckExpire:
            logger.debug('Health check already done.')

        else:

            # Do check
            if healthCheckResult != STATUS_HEALTHY:
                healthCheckResult = self.comprehensiveCheck()
            else:
                healthCheckResult = self.recheck()

            # Find interval to next check
            #
            extra = (healthCheckIntervalMax -
                     healthCheckIntervalMin).seconds * random()
            extra = round(extra)
            interval = healthCheckIntervalMin + timedelta(seconds=extra)

            # Set next check time
            healthCheckExpire = datetime.now() + interval

            logger.info('Next health check after %s', healthCheckExpire)

        return healthCheckResult

    def __call__(self):

        # Contextual Setup
        self.verbose = self.request.get('verbose', False) == 'yes'
        # this is a bit of a security issue -
        # self.request.get('ignoreResourceServerError') == 'yes'
        self.ignoreResourceServerError = True

        # Get status
        status = self.healthStatus()

        # Construst Response

        response = self.request.response
        response.setStatus(status)
        response.setHeader('Content-type:', 'text/plain')
        responseLine = '%s %s\n' % (
            status,
            {200: 'OK', 503: 'Service Unavailable'}.get(status, ''))

        logger.debug('healthcheck result: %s', responseLine)

        return responseLine
