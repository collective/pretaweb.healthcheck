Introduction
============

Provides a mechanism to front-end load balancers to check whether a Zope
instance with one or more Plone sites installed is suitable for sending
requests to.

Suitability for a load balancer in this case is
- Are the Plone sites and their sub-resources pre-cached into memory? and
- Do the Plone sites and their sub-resources return valid HTTP status codes?

The health check works in this way:
- http://my.zope.instance/@@healthcheck is called
- If the health check has already run successfully 200 OK is returned
- The health checker traverses the ZODB looking for Plone insistences
- For each instance the front page is sub-requested (by making a sub-requests,
  this forces the relevant Zope objects in the cache)
- The front page is inspected for second level pages and resources associated
  with the page like images and css.
- Those resources are sub-requested to bring them into the cache
- CSS is inspected for resources and those resources and also sub-requested
- If successful a status code of 200 OK is returned otherwise 503 Service
  Unavailable is returned

The health check will fail if
- The Plone front-page returns a 4xx client error or a 5xx server error. Except
  for 401 Unauthorised access (unauthorised access is valid because a
  restricted Plone site is a valid situation.)
- If a sub-resource returns a 5xx (server) error.

Options
- http://my.zope.instance/@@healthcheck?verbose=yes gives more output to the
  instance logs
- http://my.zope.instance/@@healthcheck?ignoreResourceServerError=yes ignores
  5xx server errors on sub-requests to resources discovered on the front page
  or CSS


