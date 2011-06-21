
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


cssImportPatern = re.compile (r"@import\s+url\(([^)]+)\)\s*;")


class RequestError (Exception): pass


class HealthCheck (BrowserView):




    def parseLinks (self, workingPath, links):
        base = self.request.base
        workingURL = base + workingPath
        output = self.output

        newLinks = set()
        for l in links:
            if len(l) > 0:
                l = l.split("#")[0]
                l = urllib.unquote(l)

                if l[0] == "/":
                    l = base + l

                elif workingURL == l:
                    pass

                elif l.startswith(base):
                    p = l[len(base):]
                    newLinks.add (p)


                elif not (l.startswith("http://") or l.startswith("https://")):
                    ll = workingURL + "/" + l
                    p = ll[len(base):]
                    newLinks.add(p)

                else:
                    output.write ("\tResource out of scope: %s\n" % l)


        return newLinks
                



    def wakePlone (self, plone):
        """Pre-caching mechenisim for plones sites. By making sub requests
        to bring objects into memory"""
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
            for mo in cssImportPatern.finditer(body):
                groups = mo.groups()
                if len(groups) > 0:
                    cssImports.append(groups[0])

            resources = self.parseLinks (url_path, links)
            resources = resources.union( self.parseLinks (url_path, images) )
            resources = resources.union( self.parseLinks (url_path, headLink) )
            resources = resources.union( self.parseLinks (url_path, scripts) )
            resources = resources.union( self.parseLinks (url_path, cssImports) )

            output.write ("\tFound %s sub resources to load.\n" % len(resources))

            for resURL in resources:
                resResponse = subrequest(resURL)
                resStatus = resResponse.getStatus()
                if resStatus == 200:
                    resBody = resResponse.getBody()
                    byteCount += len(resBody)

                    # output.write ("\tGot status %s for resource: %s\n" % (resStatus, resURL))

                else:
                    output.write ("\tGot status %s for resource: %s\n" % (resStatus, resURL))
                

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
                output.write ("Exception raised during health check. See instance logs more details.\n")
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

        self.output = StringIO()


        # Get status

        status = self.healthStatus ()


        # Construst Response

        response = self.request.response
        response.setStatus (status)
        response.setHeader ("Content-type:", "text/plain")
        responseLine = "%s %s\n" % (
                status,
                { 200:"OK", 503:"Service Unavailable" }.get(status, "") )

        return responseLine + self.output.getvalue()
        
            



