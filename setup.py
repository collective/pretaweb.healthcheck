from setuptools import setup, find_packages
import os

version = '2.0.0.dev0'

setup(name='pretaweb.healthcheck',
      version=version,
      description="Load balancer health checker for a Plone/Zope Instance",
      long_description=open("README.rst").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.rst")).read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        ],
      keywords='Zope Plone load-balancing health-check haproxy',
      author='Adam Terrey',
      author_email='software@pretaweb.com',
      url='https://github.com/collective/pretaweb.healthcheck',
      license='GPL',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['pretaweb'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'Products.CMFPlone',
          'lxml',
          'plone.protect',  # GET is safe.
          'plone.subrequest',
          'setuptools',
      ],
      entry_points="""
      # -*- Entry points: -*-
      [z3c.autoinclude.plugin]
      target = plone
      """,
      )

