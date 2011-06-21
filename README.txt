Introduction
============

Provides a mechanism to front-end load balancers to check whether a Zope
instance with one or more Plone sites installed is suitable for sending
requests to.

Exposes a @@healthcheck browser view. When called the health checker traverses
the ZODB for Plone instances and performs a health check looking for a http
status of 200 OK 401 Unauthorised access. Unauthorised access is valid because
a restricted Plone site is a valid situation.

The health check also acts as a pre-caching mechanism in order to speed up
first the requests after an instance started. This is used to ensure the Pone
sites and their resources are loaded into memory before a load balancer decides
that the instance is ok for sending requests to. The health checker does this
by parsing the front page for images, CSS and Java Script; as well as parsing
the CSS for it's related resources as well.

Subsequent requests to the health checker return 200 OK without doing any ZODB
traversing - there by only doing a health check once every start.


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





