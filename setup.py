import os
import sys

from setuptools import setup
from setuptools import find_packages

here = os.path.abspath(os.path.dirname(__file__))

try:
    README = open(os.path.join(here, 'readme.md')).read()
    CHANGES = open(os.path.join(here, 'changes.txt')).read()
except:
    README = ''
    CHANGES = ''

requires = [
    'nive', 
    'nive_userdb'
]

setupkw = dict(
      name='nive_datastore',
      version='0.9.13',
      description='Nive Data Storage - High level storage for structured data',
      long_description=README + '\n\n' + CHANGES,
      classifiers=[
        "Intended Audience :: Developers",
        "Programming Language :: Python",
        "Framework :: Pyramid",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7"
      ],
      author='Arndt Droullier, Nive GmbH',
      author_email='info@nive.co',
      url='http://www.nive.co/website/en/open_source.html',
      keywords='collection storage workflow forms pyramid',
      license='GPL 3',
      packages=find_packages(),
      include_package_data=True,
      zip_safe=False,
      install_requires=requires,
      tests_require=requires,
      test_suite="nive_datastore",
      entry_points = """\
        [pyramid.scaffold]
        datastore-sqlite=nive_datastore.scaffolds:DatastoreSqliteTemplate
        datastore-mysql=nive_datastore.scaffolds:DatastoreMysqlTemplate
        datastore-postgres=nive_datastore.scaffolds:DatastorePostgresTemplate
      """
)

setup(**setupkw)
