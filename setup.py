from setuptools import setup, find_packages
import os

version = '0.1'

setup(name='pretaweb.healthcheck',
      version=version,
      description="Health Checker for a Multi Tenant Plone Zope Instance",
      long_description=open("README.txt").read() + "\n" +
                       open(os.path.join("docs", "HISTORY.txt")).read(),
      # Get more strings from
      # http://pypi.python.org/pypi?:action=list_classifiers
      classifiers=[
        "Programming Language :: Python",
        ],
      keywords='Zope Plone load-balancing health-check',
      author='Adam Terrey',
      author_email='software@pretaweb.com',
      url='http://www.pretaweb.com',
      license='NONE',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['pretaweb'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'setuptools',
          # -*- Extra requirements: -*-
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
