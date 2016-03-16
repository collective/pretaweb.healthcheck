from datetime import datetime
from datetime import timedelta as td
from pretaweb.healthcheck.check import HealthCheck
from pretaweb.healthcheck.check import NotExpired
from pretaweb.healthcheck.check import STATUS_ERROR
from pretaweb.healthcheck.check import STATUS_HEALTHY
from ZODB.POSException import ConflictError

import pytest


now = datetime.utcnow()

quite_old = now - td(days=100)

ten_minutes_from_now = now + td(seconds=600)


def is_between_20_to_100_minutes_from_now(testtime):
    return (now + td(seconds=20*60)) < testtime < (now + td(seconds=100*60))


def test_first_run():
    checker = HealthCheck(last_result=None,
                          expire_time=quite_old,
                          traverser=None,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )
    new_expire, result = checker()
    assert is_between_20_to_100_minutes_from_now(new_expire)


def test_cached_run():
    last_result = 'same'
    checker = HealthCheck(last_result=last_result,
                          expire_time=ten_minutes_from_now,
                          traverser=None,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )
    pytest.raises(NotExpired, checker)


def test_avoid_parallel_runs(monkeypatch):
    monkeypatch.setattr('pretaweb.healthcheck.check.AM_I_RUNNING', True)
    last_result = 'same'
    checker = HealthCheck(last_result=last_result,
                          expire_time=ten_minutes_from_now,
                          traverser=None,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )
    pytest.raises(NotExpired, checker)


def test_recheck_checks_one():
    checker = HealthCheck(last_result=STATUS_HEALTHY,
                          expire_time=quite_old,
                          traverser=None,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )

    def _get_pages():
        return (1, 2)

    remember_them = []

    def _wake_plone(a_plone):
        remember_them.append(a_plone)

    checker._get_pages = _get_pages
    checker._wake_plone = _wake_plone

    new_expire, result = checker()
    assert is_between_20_to_100_minutes_from_now(new_expire)
    assert result == STATUS_HEALTHY

    assert len(remember_them) == 1
    assert remember_them[0] in (1, 2)


def test_full_check_after_unhealthy_check():
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=None,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )

    def _get_pages():
        return (1, 2)

    remember_them = []

    def _wake_plone(a_plone):
        remember_them.append(a_plone)

    checker._get_pages = _get_pages
    checker._wake_plone = _wake_plone

    new_expire, result = checker()
    assert is_between_20_to_100_minutes_from_now(new_expire)
    assert result == STATUS_HEALTHY

    assert len(remember_them) == 2


def test_check_does_not_handle_conflict_error():
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=None,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )

    def _get_pages():
        raise ConflictError()

    checker._get_pages = _get_pages

    pytest.raises(ConflictError, checker)


def test_check_does_handle_other_exceptions():
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=None,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )

    def _get_pages():
        raise KeyError()

    checker._get_pages = _get_pages

    new_expire, result = checker()
    assert is_between_20_to_100_minutes_from_now(new_expire)
    assert result == STATUS_ERROR


def test_get_pages_handles_empty():
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=None,
                          context={},
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )

    assert [] == list(checker._get_pages())


class FakeSiteRoot(object):
    def __init__(self, replies):
        self.replies = replies

    def providedBy(self, whatever):
        return self.replies.pop()


def test_get_plone_navroots(monkeypatch):
    monkeypatch.setattr('pretaweb.healthcheck.check.INavigationRoot',
                        FakeSiteRoot([True, True]))
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=None,
                          context={'a': 'a', 'b': 'b'},
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )

    plones = list(checker._get_pages())
    assert ['a', 'b'] == plones


def test_get_plone_site_root_and_nav_root(monkeypatch):
    monkeypatch.setattr('pretaweb.healthcheck.check.IPloneSiteRoot',
                        FakeSiteRoot([False, True]))
    monkeypatch.setattr('pretaweb.healthcheck.check.INavigationRoot',
                        FakeSiteRoot([False, True]))
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=None,
                          context={'a': {'myplone': True}},
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )

    plones = list(checker._get_pages())
    assert [{'myplone': True}] == plones


def test_get_plone_navroots_multilingual(monkeypatch):
    monkeypatch.setattr('pretaweb.healthcheck.check.IPloneSiteRoot',
                        FakeSiteRoot([False, True]))
    monkeypatch.setattr('pretaweb.healthcheck.check.INavigationRoot',
                        FakeSiteRoot([True, True]))
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=None,
                          context={'a': {'de': 'de_folder'}},
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )

    plones = list(checker._get_pages())
    assert [{'de': 'de_folder'}, 'de_folder'] == plones


class FakeContext(object):
    def unrestrictedTraverse(self, path):
        if 'missing' in path:
            raise KeyError
        return path


def test_get_plone_from_paths():
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=None,
                          context=FakeContext(),
                          base=None,
                          host=None,
                          use_https=False,
                          paths=['/a', '/missing'],
                          )

    plones = list(checker._get_pages())
    assert ['/a'] == plones


class FakePloneObj(object):
    def getPhysicalPath(self):
        return ('a', 'b', 'c')


def test_wake_plone(monkeypatch):
    urls_gotten = []

    class PloneLoader(object):
        def __init__(self, base, host, use_https, url):
            urls_gotten.append(url)

        def __call__(self):
            pass

    monkeypatch.setattr('pretaweb.healthcheck.check.PloneLoader',
                        PloneLoader)

    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=lambda x: x,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          paths=None,
                          )
    checker._wake_plone(FakePloneObj())

    assert ['a/b/c'] == urls_gotten
