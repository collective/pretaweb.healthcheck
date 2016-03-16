from datetime import datetime
from datetime import timedelta
from pretaweb.healthcheck.check import HealthCheck
from pretaweb.healthcheck.check import STATUS_ERROR
from Products.Five import BrowserView

import logging


logger = logging.getLogger(__name__)

CACHED_HEALTH_CHECK_RESULT = STATUS_ERROR
HEALTH_CHECK_NEXT_EXPIRE = datetime.utcnow() - timedelta(seconds=1)

CHECK_IN_PROGRESS = False


class HealthCheckView(BrowserView):

    def __call__(self, paths=None):
        environ = self.request.environ
        context = self.context

        global CACHED_HEALTH_CHECK_RESULT
        global HEALTH_CHECK_NEXT_EXPIRE
        global CHECK_IN_PROGRESS

        if CHECK_IN_PROGRESS and datetime.utcnow() < HEALTH_CHECK_NEXT_EXPIRE:
            logger.info('Check in progress, ignoring returning old result')
            return self.build_response(CACHED_HEALTH_CHECK_RESULT)
        else:
            CHECK_IN_PROGRESS = True

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
                                   paths=paths,
                                   )

        HEALTH_CHECK_NEXT_EXPIRE, CACHED_HEALTH_CHECK_RESULT = health_check()

        cache_utiliziation_after = db.cacheSize() / cache_percent_mod

        # Get status
        status = CACHED_HEALTH_CHECK_RESULT
        CHECK_IN_PROGRESS = False

        logger.info('healthcheck result: %r', status)
        logger.info('Cache fill level before: %.2f %%. After: %.2f %%.',
                    cache_utiliziation_before, cache_utiliziation_after)

        return self.build_response(status)

    def build_response(self, status):
        # Construst Response
        response = self.request.response
        response.setStatus(status)
        response.setHeader('Content-type:', 'text/plain')
        responseLine = '%s %s\n' % (
            status,
            {200: 'OK', 503: 'Service Unavailable'}.get(status, ''))

        return responseLine
