from pretaweb.healthcheck.check import PloneLoader
import pytest


def make_subrequester(monkeypatch, status, response, **special_replies):
    memory = []

    class Response(object):
        def __init__(self, url, status, headers, body):
            self.url = url
            self.status = status
            self.body = body
            self.headers = headers

        def getStatus(self):
            return self.status

        def getHeader(self, key):
            try:
                return self.headers[key.lower()]
            except KeyError:
                raise KeyError('Key "%r" not found for resource "%r"',
                               key.lower(), self.url)

        def getBody(self):
            return self.body

    def subrequest(url):
        memory.append(url)
        if url in special_replies:
            return Response(url, *special_replies[url])
        else:
            return Response(url, status, {}, response)
    monkeypatch.setattr('pretaweb.healthcheck.check.subrequest', subrequest)
    return memory


def test_plone_loader(monkeypatch):
    loader = PloneLoader('http://example.com',
                         'example.com',
                         False,
                         'http://example.com')
    subrequest_memory = make_subrequester(monkeypatch, 200, '')
    loader()
    assert ['http://example.com'] == subrequest_memory


def test_plone_loader_no_fail_on_401(monkeypatch):
    loader = PloneLoader('http://example.com',
                         'example.com',
                         False,
                         'http://example.com')
    make_subrequester(monkeypatch, 401, '')
    loader()
    assert True


def test_plone_loader_failed(monkeypatch):
    loader = PloneLoader('http://example.com',
                         'example.com',
                         False,
                         'http://example.com')
    make_subrequester(monkeypatch, 599, '')
    try:
        loader()
        assert False
    except Exception, e:
        assert 'http://example.com' == e.url
        assert 599 == e.status


def test_plone_loader_with_urls(monkeypatch):
    plone_body = '''
<html>
  <body>
    <div>
      <a href="/a"></a>
      <a href="#xx"></a>
      <img src="/b"></img>
      <script src="/c"></script>
    </div>
  </body>
</html>
'''
    loader = PloneLoader('http://example.com',
                         'example.com',
                         False,
                         'http://example.com')
    subrequest_memory = make_subrequester(monkeypatch, 200, plone_body)
    loader()
    assert ['http://example.com',
            '/a',
            '/b',
            '/c'] == subrequest_memory


@pytest.mark.parametrize('url,status_code,expected', (
    ('/a', 200, ['/a']),
    ('/a', 299, ['/a']),
    ('/a', 300, ['/a']),
    ('/a', 399, ['/a']),
    ('/a', 400, ['/a']),
    ('/a', 499, ['/a']),
    ('/a', 500, ['/a']),
    ('/a', 599, ['/a']),
))
def test_wake_resource(monkeypatch, status_code, url, expected):
    loader = PloneLoader('http://example.com',
                         'example.com',
                         False,
                         'http://example.com')
    subrequest_memory = make_subrequester(monkeypatch, 200, 'xx',
                                          **{url: (status_code, {}, '')})

    loader._wake_resource(url)
    loader._wake_resource(url)

    assert expected == subrequest_memory


@pytest.mark.parametrize('url,content,content_type,expected', (
    ('/a', 'url(/image)', 'text/css', ['/a', '/image']),
    ('/a.css', 'url(/image)', 'text/html', ['/a.css', '/image']),
    ('/a.css', 'url(/image)', 'text/css', ['/a.css', '/image']),
    ('/a.html', 'url(/image)', 'text/html', ['/a.html']),
    ('/a.kss', 'url(/image)', 'text/css', ['/a.kss']),
    ('/a', '', 'text/css', ['/a']),
    ('/a.css', 'url(#xx)', 'text/css', ['/a.css']),
))
def test_wake_css_resource(monkeypatch, url, content, content_type,
                           expected):
    loader = PloneLoader('http://example.com',
                         'example.com',
                         False,
                         'http://example.com')
    other_urls = {url: (200, {'content-type': content_type}, content),
                  '/image': (200, {}, '')}
    subrequest_memory = make_subrequester(monkeypatch, 200, content,
                                          **other_urls)

    loader._wake_css_resource(url)
    loader._wake_css_resource(url)

    assert expected == subrequest_memory


def test_plone_loader_finds_css(monkeypatch):
    plone_body = '''
<html>
  <head>
    <link href="/a" />
    <link href="#xx" />
    <link href="/b" />
    <link href="/c.css" />
    <link href="/d" />
    <link href="/e" />
    <link href="/f.kss" />
    <style>
      @import url("/x");
      @import url("#xx");
  <body>
  </body>
</html>
'''
    loader = PloneLoader('http://example.com',
                         'example.com',
                         False,
                         'http://example.com')
    ignore_link = 'url(/dontfollow)'
    follow_link = 'url(/follow_me)'
    bad_link = 'url(#xx)'
    resources = {'/a': (200, {'content-type': 'text/css'}, follow_link),
                 '/b': (200, {'content-type': 'text/css'}, ''),
                 '/c.css': (200, {'content-type': 'text/html'}, follow_link),
                 '/d': (200, {'content-type': 'text/html'}, ignore_link),
                 '/e': (200, {'content-type': 'text/css'}, bad_link),
                 '/f.kss': (200, {'content-type': 'text/css'}, ignore_link),
                 '/x': (200, {'content-type': 'text/css'}, follow_link),
                 }
    # a: Link should be followed, because ct is right
    # b: should be followed but has no content
    # c: should be followed because ends with .css
    # d: should not be followed, because no indication of css
    # e: should not be followed, because indication that it is kss
    # x: should be followed for same reasons as a
    subrequest_memory = make_subrequester(monkeypatch, 200, plone_body,
                                          **resources)
    loader()
    assert ['http://example.com',
            '/a',
            '/follow_me',
            '/b',
            '/c.css',
            '/d',
            '/e',
            '/f.kss',
            '/x',
            ] == subrequest_memory


@pytest.mark.parametrize('url,expected', (
    ('#x', None),
    ('', None),
    ('/ex', None),
    ('http://example.com/x', '/x'),
    ('https://example.com/x', None),
    ('bla', '/ex/bla'),
))
def test_normalize_link(url, expected):
    loader = PloneLoader('http://example.com',
                         'example.com',
                         False,
                         'http://example.com')

    assert expected == loader._normalize_link('http://example.com/ex', url)


def test_normalize_link_https():
    loader = PloneLoader('http://example.com',
                         'example.com',
                         False,
                         'http://example.com')

    assert '/ex2' == loader._normalize_link('https://example.com/ex', '/ex2')


def test_normalize_link_relative_ref_link():
    loader = PloneLoader('http://example.com',
                         'example.com',
                         False,
                         'http://example.com')

    assert '/ex/ex2' == loader._normalize_link('/ex', 'ex2')
