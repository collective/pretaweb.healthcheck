
import logging
import re
import sys
import traceback
import urllib
from lxml import etree
from StringIO import StringIO

from plone.subrequest import subrequest
from Products.Five import BrowserView
from zope.component import getMultiAdapter

logger = logging.getLogger("pretaweb.healthcheck")


healthCheckDone = False
healthCheckResult = 503

class RequestError (Exception): pass
class ServerError (RequestError): pass


class HealthCheck (BrowserView):




    def parseLinks (self, workingPath, links):
        base = self.request.base
        workingURL = base + workingPath
        host = self.request.environ.get("HTTP_HOST")
        

        if self.request.environ.get("HTTPS", False):
            protocol = "https"
        else:
            protocol = "http"


        newLinks = set()
        for l in links:
            l = l.split("#")[0]
            if len(l) > 0:
                l = urllib.unquote(l)
                if l[0] == "/":
                    l = protocol + "://" + host + l
                if l.endswith("/"):
                    l = l[:-1]


                # Link same as base - ignore
                if workingURL == l:
                    pass

                # Absolute URL - add without base
                elif l.startswith(base):
                    p = l[len(base):]
                    newLinks.add (p)


                # Relative URL - add with workingURL 
                elif not (l.startswith("http://") or l.startswith("https://")):
                    ll = workingURL + "/" + l
                    p = ll[len(base):]
                    newLinks.add(p)


                # Other URLs
                else:
                    if self.verbose:
                        logger.debug ("\tResource out of scope: %s" % l)


        return newLinks
                



    def wakeResources (self, resources):
        byteCount = 0
        
        for url in resources:
            response = subrequest(url)
            status = response.getStatus()
            if status == 200:
                body = response.getBody()
                byteCount += len(body)

                if self.verbose:
                    logger.debug("\tGot status %s for resource: %s" % (status, url))

            elif status >= 500:
                if not self.ignoreResourceServerError:
                    logger.info ("\tGot status %s for resource: %s" % (status, url))
                    raise ServerError ()
                else:
                    logger.debug ("\tGot status %s for resource: %s" % (status, url))
            else:
                logger.debug ("\tGot status %s for resource: %s" % (status, url))

        return byteCount




    def wakeCssResources (self, resources, alreadyDone):
        byteCount = 0
        urlResources = set()
        cssURLResourcePattern = re.compile (r"url\('?([^')]+)'?\)")

        # Get css resources and parse for url(...) directives

        for url in resources:
            response = subrequest(url)
            status = response.getStatus()

            if status == 200:

                if self.verbose:
                    logger.info ("\tGot status %s for resource: %s" % (status, url))

                body = response.getBody()
                byteCount += len(body)

                # detect if document is CSS
                if (url.endswith (".css")
                        or response.getHeader("content-type").startswith("text/css")) and not url.endswith(".kss"):

                    # get CSS working path
                    workingPath = url.split("/")
                    workingPath.pop()
                    workingPath = self.request.base + "/".join (workingPath)


                    # parse URLs
                    foundURLs = []
                    for mo in cssURLResourcePattern.finditer(body):
                        groups = mo.groups()
                        if len(groups) > 0:
                            foundURLs.append(groups[0])
                    urlResources = urlResources.union ( self.parseLinks(workingPath, foundURLs) )

                else:
                    logger.debug ("\tNot a CSS document: %s" % url)


            elif status >= 500:
                if not self.ignoreResourceServerError:
                    logger.info ("\tGot status %s for resource: %s" % (status, url))
                    raise ServerError ()
                logger.debug ("\tGot status %s for resource: %s" % (status, url))

            else:
                logger.debug ("\tGot status %s for resource: %s" % (status, url))


        # wake those extra resources

        alreadyDone = alreadyDone.union (resources)
        urlRresources = urlResources.difference (alreadyDone)
        logger.debug ("\tFound %s resources referenced from CSS" % len(urlResources))
        byteCount += self.wakeResources (urlResources)


        return byteCount
        


    def wakePlone (self, plone):
        """Pre-caching mechenisim for plones sites. By making sub requests
        to bring objects into memory"""
        cssImportPattern = re.compile (r"@import\s+url\(([^)]+)\)\s*;")


        # Request the front page

        url_path = "/".join (plone.getPhysicalPath())
        response = subrequest(url_path)
        status = int(response.getStatus())

        logger.info ("Plone Site: %s" % url_path)
        logger.debug("\tHTTP status: %s" % status)

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
            doc = etree.parse (StringIO(body), etree.HTMLParser())
        except etree.XMLSyntaxError:
            logger.debug ("\tWarning: XMLSyntaxError on front page")
        else:
            links = doc.xpath("/html/body//a/@href")
            images = doc.xpath("/html/body//img/@src")
            headLink = doc.xpath ("/html//link/@href")
            scripts = doc.xpath ("/html//script/@src")

            cssImports = []
            for mo in cssImportPattern.finditer(body):
                groups = mo.groups()
                if len(groups) > 0:
                    cssImports.append(groups[0])

            resources = self.parseLinks (url_path, links)
            resources = resources.union( self.parseLinks (url_path, images) )
            resources = resources.union( self.parseLinks (url_path, scripts) )

            logger.debug ("\tFound %s sub resources to load." % len(resources))
            byteCount += self.wakeResources (resources)   

            cssResources = self.parseLinks (url_path, headLink)
            cssResources = cssResources.union( self.parseLinks (url_path, cssImports) )
            cssResources = cssResources.difference (resources)

            logger.debug ("\tFound %s css resources to load." % len(cssResources) )
            byteCount += self.wakeCssResources (cssResources, alreadyDone=resources)

        logger.info ("Approximate of bytes retrieved for site resources: %s" % len(body))








    def traverse (self):
        context = self.context


        # Discovery

        def findPlones (context):
            plones = context.objectValues("Plone Site")
            folders = context.objectValues("Folder")
            for folder in folders:
                plones += findPlones(folder)
            return plones

        plones = findPlones(context)
        logger.info ("%s site(s) found.\n" % len(plones))


        # Wake-up time

        for p in plones:
            self.wakePlone (p)




    def healthStatus (self):
        global healthCheckDone
        global healthCheckResult


        # healthCheckDone doesn't persist application restarts, 
        # so this ensures that the health check is only done
        # on the first poll
        if healthCheckDone:
            logger.debug ("Health check already done.")

        else:
            logger.info ("Good morning Plone world! Checking health...")
            healthCheckDone = True
            healthCheckResult = 503

            try:
                # Do healthChecks 
                self.traverse()

            except:
                # Instance not healthy
                logger.info ("Exception raised during health check.")
                healthCheckResult = 503
                plonesWoke = False

                logger.info (traceback.format_exc())

            else:
                logger.info ("Finished health check. Pass.")
                healthCheckResult = 200

        return healthCheckResult




    def __call__ (self):


        # Contextual Setup

        self.verbose = self.request.get("verbose", False) == "yes"
        self.ignoreResourceServerError = self.request.get("ignoreResourceServerError") == "yes"


        # Get status

        status = self.healthStatus ()


        # Construst Response

        response = self.request.response
        response.setStatus (status)
        response.setHeader ("Content-type:", "text/plain")
        responseLine = "%s %s\n" % (
                status,
                { 200:"OK", 503:"Service Unavailable" }.get(status, "") )

        logger.debug ("helthcheck result: " + responseLine)

        return responseLine
        
            



