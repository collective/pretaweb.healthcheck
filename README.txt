Introduction
============

Providing a mecenisim to front-end load ballencers to check
wether a Zope instance with one or more Plone sites installed
is sutiable for sending requests to.

Exposes a @@healthcheck browser view. When called it will 
treverse the ZODB for Plone instences makeing sub requests
to their front page. Theirby forcing Zope to load Plone
objects, this therefore works as a pre-cache mechinisim in
order to reduce the time spent on the first request once
the instance has become available to the load ballencer.
The browser view will return a status of 200 meaing 
that the Plone sites have all "woken up" or 503 meaning
there was an error in loading at least one of the Plone
sites.  On successive polls, the browser view returns
200 if it has been allready run successivly, or tries
to pre-cache again if it has not yet been successifully run.

Examples:

$ curl http://localhost:8080/@@healthcheck
200 OK
Good morning Plone world! Waking Plone sites...
7 site(s) found.
/PloneTest
	HTTP status: 200
	front page size: 33360
/Plone
	HTTP status: 200
	front page size: 20277
/cg5
	HTTP status: 200
	front page size: 22540
/cg6
	HTTP status: 200
	front page size: 32106
/12/mnt/Plone2331
	HTTP status: 200
	front page size: 21047
/13/mnt/Mi Plone
	HTTP status: 200
	front page size: 21115
/17/mnt/PloneB
	HTTP status: 200
	front page size: 20461
Done waking Plone sites.


$ curl http://localhost:8080/@@healthcheck
200 OK
Plone sites already woken.


After deleting random objects in /PloneTest and then a restart:

$ curl http://localhost:8080/@@healthcheck
503 Service Unavailable
Good morning Plone world! Waking Plone sites...
7 site(s) found.
/PloneTest
	HTTP status: 404
Error in waking Plone sites. See instance logs more details.





