Introduction
============

Provide a central URL to check the health of your Plone sites and for
warming up the cache.

The package has been written with HAProxy and performance in mind.

The provided view, ``@healthcheck`` will iterate over each Plone site
and load the frontpage and all linked resources.
It will also check the Plone site for direct descendent Navigation Roots.
If you have a multilingual site, you usually have a root folder for each language and this folder is a navigation root.
So this means, every language gets warmed up.

There is an alternative mode. If you call the view paths:list get parameters, healthcheck will check these pages, together with the resources this page references. There is no check if the path is INavigationRoot or an IPloneSite.
So this allows you to add any page to the check and the cache.

HAProxy calls the URL quite often. A cache mechanism ensures that by default:

  1. The check happens only between every 30-90 minutes. Inbetween you get a cached result
  2. If previous checks were successful, only one random site/navroot will be checked

The healthcheck will fail, if any navigation root page will fail to render.
There is only one exception. We will not fail on 401s. This may happen with pages that are private in nature.
They cannot be properly warmed up with this, but at least the healthcheck won't fail.
Resources referenced from the front page will NOT trigger an error.
Unfortunately, this is too often the case.

Comparison with collective.warmup
---------------------------------
This package was here first.

collective.warmup is a standalone script, existing outsite of zope/Plone.

Advantages of collective.warmup over pretaweb.healthcheck:

    - can be executed once during a deployment
    - Does (maybe?) not have the failure modes explained below

Advantages of pretaweb.healthcheck over collective.warmup:

    - Can be integrated in HAProxy
    - Caching included in pretaweb.healthcheck
    - Logs quite a few helpful information you can only get from within Zope, for example, how much of the cache is used after warmup

If you use HAProxy, you want to use pretaweb.healthcheck.

Installation
------------

Add the egg as a dependency to your policy egg.
This package does not store persistent configuration. There is no configuration option within the Plone site.

No installation or uninstallation profile needs to be executed.

Configuration
-------------

You can control cache times with environment variables:

    - `healthcheck_cache_interval`

      The default is 3600 seconds. You can define any value in seconds.

    - `healthcheck_cache_variance`

      the default is 1800 seconds. You can define any value in seconds.

To calculate the next expire time, the cache_interval is taken, and a random number between 0 and the cache_variance is added.
This time is calculated after every expiration.

If you do not want to warm up every single Plone site / navigation root, you can give paths to check for. These paths are checked **together** with the resources the page references::

    http://yourserver:port/@@healthcheck?paths:list=/Plone/en&paths:list=/Plone/en/a/b/c/d/expensive_page

Would load all resources of the english front page and the one expensive page deep down your site.

If you trust that your cache will cache all images and css files, you can tell the healthcheck not to load these resources::

    http://yourserver:port/@@healthcheck?deep:boolean=False

Failure modes
-------------

If you are going to integrate this package in your deployment together with HAProxy, be aware of the new failure modes.

If you have many Plones on a single Zope instance and a few of them are not actively used, they are still checked. If they produce failures after a minor Plone update, all Plone pages will not be available, because this package told HAProxy, that it itself is broken.

If you allow people to modify Plone pages through the web in such a way that the frontpage can become broken, your complete site can go down, but not necessary soonish.
the default cache expiration is 1 hour plus a random amount from half an hour. But if the previous check was successful, we don't need the cache warmup functionality, so we pick only a single page at random. If you think this is not a problem, do the math for yourself::

    >>> math.log(abs(probability - 1)) / math.log((sites - broken_sites) / float(sites)) * healthcheck_cache_interval * (healthcheck_cache_variance / 2)

If you have a zope instance with 20 Plone sites, after 17 hours you have a 50% chance that your instance gets identified as broken. If each instance has three language folders, the time increase to a bit more than two days. This is not a good start for debugging.

If you are in such a situation, you have a few possibilities:

  - Move your unused Plone pages into a subfolder. They won't be found any more. Earlier versions used the virtual_hosting mapping to find Plone sites. This version doesn't
  - Have proper monitoring in Place. `Sentry`_ has proper `Plone integration`_ and in its default configuration will send you mails for errors only and only once. So after cutting the noise by fixing a bunch of invisible bugs, every mail is usually an actionable item.
  - Configure this package and HAProxy so that you can use different backend for different Plone sites or language folders. Then the breakage is more local.

If you have a dedicated Zope Instance for a single Plone site, and your users can't break the Plone page easily, this is much less an issue.


Todo
----
- [ ] Caching under Plone 5 is currently not working very well: `subrequest bug`_ 

Testing
-------
The code has full test coverage for everything except the views.
To exercise the tests in a development checkout, run buildout, then run::

    $ ./bin/py.test --cov=pretaweb --cov-report=term-missing

.. _`subrequest bug`: https://github.com/Plone/Plone.subrequest/issues/6
.. _Plone integration: https://docs.getsentry.com/hosted/clients/python/integrations/zope/
.. _Sentry: https://www.getsentry.com
