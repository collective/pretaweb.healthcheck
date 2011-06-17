
import sys
import traceback
from StringIO import StringIO
from Products.Five import BrowserView
from zope.component import getMultiAdapter
from plone.subrequest import subrequest


plonesWoke = False


class RequestError (Exception): pass


class HealthCheck (BrowserView):



    def wakePlones (self, output):
        """Pre-caching mechenisim for plones sites"""

	context = self.context

        def findPlones (context):
            plones = context.objectValues("Plone Site")
            folders = context.objectValues("Folder")
            for folder in folders:
                plones += findPlones(folder)
            return plones

	plones = findPlones(context)

        output.write ("%s site(s) found.\n" % len(plones))

        for p in plones:
	    url_path = "/".join (p.getPhysicalPath())

	    response = subrequest(url_path)
	    status = int(response.getStatus())

	    output.write("%s\n" % url_path)
	    output.write("\tHTTP status: %s\n" % status)

	    if status >= 400 and status != 401:
	        # Bad news - 4xx (client) and 5xx (server) errors.
	        # With the exception of 401 for unautherized access
	        # which is an acceptable error

	        raise RequestError()

	    body = response.getBody()
	    output.write ("\tfront page size: %s\n" % len(body))




    def __call__ (self):
        global plonesWoke
        context = self.context
	output = StringIO()

        if plonesWoke:
	    output.write("Plone sites already woken.\n")
	    returnStatus = 200

	else:
	    # Plone Waking: the purpas is to force zope to bring
	    # needed objects into it's cache as a way of precaching.

	    output.write ("Good morning Plone world! Waking Plone sites...\n")

	    try:
	        self.wakePlones(output)

	    except:
	        output.write ("Error in waking Plone sites. See instance logs more details.\n")
	        returnStatus = 503
	        plonesWoke = False

	        sys.stderr.write("Error in waking Plone sites. (pretaweb.healthcheck)")
	        traceback.print_exc(file=sys.stderr)

	    else:
	        output.write ("Done waking Plone sites.\n")
	        returnStatus = 200
	        plonesWoke = True


	# Construst Response

	response = self.request.response
	response.setStatus (returnStatus)
	response.setHeader ("Content-type:", "text/plain")

        if returnStatus == 200:
	    body = "200 OK\n" + output.getvalue()
	elif returnStatus == 503:
	    body = "503 Service Unavailable\n" + output.getvalue()
	else:
	    raise Exception("Invalid returnStatus")

	return body
	
	    
