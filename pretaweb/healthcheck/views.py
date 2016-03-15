from datetime import datetime
from datetime import timedelta
from pretaweb.healthcheck.check import HealthCheck
from pretaweb.healthcheck.check import STATUS_ERROR
from Products.Five import BrowserView

import logging


logger = logging.getLogger(__name__)

CACHED_HEALTH_CHECK_RESULT = STATUS_ERROR
HEALTH_CHECK_NEXT_EXPIRE = datetime.utcnow() - timedelta(seconds=1)


class HealthCheckView(BrowserView):

    def __call__(self):
        environ = self.request.environ
        context = self.context

        global CACHED_HEALTH_CHECK_RESULT
        global HEALTH_CHECK_NEXT_EXPIRE

        use_https = environ.get('HTTPS', False)

        db = self.context._p_jar.db()

        cache_percent_mod = float(db.getCacheSize()) / 100
        cache_utiliziation_before = db.cacheSize() / cache_percent_mod

        health_check = HealthCheck(last_result=CACHED_HEALTH_CHECK_RESULT,
                                   expire_time=HEALTH_CHECK_NEXT_EXPIRE,
                                   traverser=context.restrictedTraverse,
                                   context=self.context,
                                   base=self.request.base,
                                   host=environ.get('HTTP_HOST'),
                                   use_https=use_https,
                                   )

        HEALTH_CHECK_NEXT_EXPIRE, CACHED_HEALTH_CHECK_RESULT = health_check()

        cache_utiliziation_after = db.cacheSize() / cache_percent_mod

        # Get status
        status = CACHED_HEALTH_CHECK_RESULT

        # Construst Response
        response = self.request.response
        response.setStatus(status)
        response.setHeader('Content-type:', 'text/plain')
        responseLine = '%s %s\n' % (
            status,
            {200: 'OK', 503: 'Service Unavailable'}.get(status, ''))

        logger.info('healthcheck result: %s', responseLine)
        logger.info('Cache fill level before: %.2f %%. After: %.2f %%.',
                    cache_utiliziation_before, cache_utiliziation_after)

        return responseLine
