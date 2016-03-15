Introduction
============

Provide a central URL to check the health of your Plone Sites and for
warming up the cache.

The package has been written with HAPROXY and performance in mind.

The provided view, ``@healthcheck`` will iterate over each Plone Site
and load the frontpage and all linked resources.
It will also check the Plone Site for direct descendent Navigation Roots.
If you have a multilingual Site, you usually have a root folder for each language and this folder is a navigation root.
So this means, every language gets warmed up.

haproxy calls the URL quite often. A cache mechanism ensures that by default:

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

collective.warmup is a standalone script, existing outsite of zope/plone.
You can configure it to call anything in your page, like the search page.

Advantages of collective.warmup:

    - can be executed once during a deployment
    - can warm up any resource, also a search

Advantages of pretaweb.healthcheck:

    - Can be integrated in haproxy
    - Caching included in pretaweb.healthcheck
    - Logs quite a few helpful information you can only get from within Zope, for example, how much of the cache is used after warmup

If you use haproxy, you want to use pretaweb.healthcheck.

Configuration
-------------

You can control cache times with environment variables:

    - `healthcheck_cache_interval`

      The default is 3600 seconds. You can define any value in seconds.

    - `healthcheck_cache_variance`

      the default is 1800 seconds. You can define any value in seconds.

To calculate the next expire time, the cache_interval is taken, and a random number between 0 and the cache_variance is added.
This time is calculated after every expiration.

Todo
----
- [ ] Allow some form of configuration to filter out specific navroots. Useful if one has many languages an not each backend zeoclient handles each language
- [ ] Caching under Plone 5 is currently not working very well: `subrequest bug`_ 

.. _`subrequest bug`: https://github.com/plone/plone.subrequest/issues/6
