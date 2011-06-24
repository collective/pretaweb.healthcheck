
import sys
import traceback
import urllib
import re
from StringIO import StringIO
from lxml import etree
from Products.Five import BrowserView
from zope.component import getMultiAdapter
from plone.subrequest import subrequest


healthCheckDone = False


class RequestError (Exception): pass
class ServerError (RequestError): pass


class HealthCheck (BrowserView):




    def parseLinks (self, workingPath, links):
        base = self.request.base
        workingURL = base + workingPath
        output = self.output
        host = self.request.environ.get("HTTP_HOST")
        

        if self.request.environ.get("HTTPS", False):
            protocol = "https"
        else:
            protocol = "http"


        newLinks = set()
        for l in links:
            if len(l) > 0:
                l = l.split("#")[0]
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
                        output.write ("\tResource out of scope: %s\n" % l)


        return newLinks
                



    def wakeResources (self, resources):
        output = self.output
        byteCount = 0
        
        for url in resources:
            response = subrequest(url)
            status = response.getStatus()
            if status == 200:
                body = response.getBody()
                byteCount += len(body)

                if self.verbose:
                    output.write ("\tGot status %s for resource: %s\n" % (status, url))

            elif status >= 500:
                output.write ("\tGot status %s for resource: %s\n" % (status, url))
                if not self.ignoreResourceServerError:
                    raise ServerError ()

            else:
                output.write ("\tGot status %s for resource: %s\n" % (status, url))

        return byteCount




    def wakeCssResources (self, resources, alreadyDone):
        output = self.output
        byteCount = 0
        urlResources = set()
        cssURLResourcePattern = re.compile (r"url\('?([^')]+)'?\)")

        # Get css resources and parse for url(...) directives

        for url in resources:
            response = subrequest(url)
            status = response.getStatus()

            if status == 200:

                if self.verbose:
                    output.write ("\tGot status %s for resource: %s\n" % (status, url))

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
                    output.write ("\tNot a CSS document: %s\n" % url)


            elif status >= 500:
                output.write ("\tGot status %s for resource: %s\n" % (status, url))
                if not self.ignoreResourceServerError:
                    raise ServerError ()

            else:
                output.write ("\tGot status %s for resource: %s\n" % (status, url))


        # wake those extra resources

        alreadyDone = alreadyDone.union (resources)
        urlRresources = urlResources.difference (alreadyDone)
        output.write ("\tFound %s resources referenced from CSS\n" % len(urlResources))
        byteCount += self.wakeResources (urlResources)


        return byteCount
        


    def wakePlone (self, plone):
        """Pre-caching mechenisim for plones sites. By making sub requests
        to bring objects into memory"""
        cssImportPattern = re.compile (r"@import\s+url\(([^)]+)\)\s*;")
        output = self.output


        # Request the front page

        url_path = "/".join (plone.getPhysicalPath())
        response = subrequest(url_path)
        status = int(response.getStatus())

        output.write("%s\n" % url_path)
        output.write("\tHTTP status: %s\n" % status)

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
            output.write ("\tWarning: XMLSyntaxError on front page\n")
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

            output.write ("\tFound %s sub resources to load.\n" % len(resources))
            byteCount += self.wakeResources (resources)   

            cssResources = self.parseLinks (url_path, headLink)
            cssResources = cssResources.union( self.parseLinks (url_path, cssImports) )
            cssResources = cssResources.difference (resources)

            output.write ("\tFound %s css resources to load.\n" % len(cssResources) )
            byteCount += self.wakeCssResources (cssResources, alreadyDone=resources)

        output.write ("\tNumber of bytes retrieved: %s\n" % len(body))







    def traverse (self):
        context = self.context
        output = self.output


        # Discovery

        def findPlones (context):
            plones = context.objectValues("Plone Site")
            folders = context.objectValues("Folder")
            for folder in folders:
                plones += findPlones(folder)
            return plones

        plones = findPlones(context)
        output.write ("%s site(s) found.\n" % len(plones))


        # Wake-up time

        for p in plones:
            self.wakePlone (p)




    def healthStatus (self):
        global healthCheckDone
        output = self.output


        # healthCheckDone doesn't persist application restarts, 
        # so this ensures that the health check is only done
        # on the first poll
        if healthCheckDone:
            output.write("Health check already done.\n")
            status = 200

        else:
            output.write ("Good morning Plone world! Checking health...\n")

            try:
                # Do healthChecks
                self.traverse()

            except:
                # Instance not healthy
                output.write ("Exception raised during health check.\n")
                status = 503
                plonesWoke = False

                sys.stderr.write("Exception raised during health check. (pretaweb.healthcheck)")
                traceback.print_exc(file=sys.stderr)

            else:
                output.write ("Finished health check.\n")
                status = 200
                healthCheckDone = True

        return status




    def __call__ (self):


        # Contextual Setup

        self.output = sys.stderr
        self.verbose = self.request.get("verbose", False) == "yes"
        self.ignoreResourceServerError = self.request.get("ignoreResourceServerError") == "yes"


        # Get status

	self.output.write("pretaweb.healthcheck checking health:\n")
        status = self.healthStatus ()


        # Construst Response

        response = self.request.response
        response.setStatus (status)
        response.setHeader ("Content-type:", "text/plain")
        responseLine = "%s %s\n" % (
                status,
                { 200:"OK", 503:"Service Unavailable" }.get(status, "") )

        self.output.write ("pretaweb.healthcheck result: " + responseLine)

        return responseLine
        
            



