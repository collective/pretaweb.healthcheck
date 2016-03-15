from datetime import datetime
import pytest
from pretaweb.healthcheck.check import HealthCheck
from pretaweb.healthcheck.check import STATUS_HEALTHY
from pretaweb.healthcheck.check import STATUS_ERROR
from datetime import timedelta as td
from ZODB.POSException import ConflictError


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
                          )
    new_expire, new_result = checker()
    assert new_expire == ten_minutes_from_now
    assert new_result == last_result


def test_recheck_checks_one():
    checker = HealthCheck(last_result=STATUS_HEALTHY,
                          expire_time=quite_old,
                          traverser=None,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          )

    def _get_plones():
        return (1, 2)

    remember_them = []

    def _wake_plone(a_plone):
        remember_them.append(a_plone)

    checker._get_plones = _get_plones
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
                          )

    def _get_plones():
        return (1, 2)

    remember_them = []

    def _wake_plone(a_plone):
        remember_them.append(a_plone)

    checker._get_plones = _get_plones
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
                          )

    def _get_plones():
        raise ConflictError()

    checker._get_plones = _get_plones

    pytest.raises(ConflictError, checker)


def test_check_does_handle_other_exceptions():
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=None,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          )

    def _get_plones():
        raise KeyError()

    checker._get_plones = _get_plones

    new_expire, result = checker()
    assert is_between_20_to_100_minutes_from_now(new_expire)
    assert result == STATUS_ERROR


def test_get_plones_handles_empty():
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=None,
                          context={},
                          base=None,
                          host=None,
                          use_https=False,
                          )

    assert [] == list(checker._get_plones())


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
                          )

    plones = list(checker._get_plones())
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
                          )

    plones = list(checker._get_plones())
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
                          )

    plones = list(checker._get_plones())
    assert [{'de': 'de_folder'}, 'de_folder'] == plones


def xxtest_wake_vh_plone(monkeypatch):
    monkeypatch.setattr('pretaweb.healthcheck.check.IPloneSiteRoot',
                        FakeSiteRoot([True, False]))
    checker = HealthCheck(last_result=STATUS_ERROR,
                          expire_time=quite_old,
                          traverser=lambda x: x,
                          context=None,
                          base=None,
                          host=None,
                          use_https=False,
                          )

    remember_them = []

    def _wake_plone(a_plone):
        remember_them.append(a_plone)

    checker._wake_plone = _wake_plone

    checker._wake_vh_plone('a')
    checker._wake_vh_plone('b')

    assert ['b'] == remember_them


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
                          )
    checker._wake_plone(FakePloneObj())

    assert ['a/b/c'] == urls_gotten
