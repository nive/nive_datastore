
# Nive Data Storage
Nive Data Storage is a high level storage for structured data featuring many 
functional components and a Web API. 

## Features
- Structured data collections
- Typed collections
- Python and Json collection configuration
- Hierarchical cotainer support for data 
- Web API and Python connectors
- Workflow support
- Json and custom data renderes
- Build in form generator
- Detailed security permissions

## Version
The package will soon be released as stable 1.0 version. For a better package management the previous
`nive` package has been split up into several smaller packages.

If you are updating from version 0.9.11 or older please read `update-0.9.11-to-1.0.txt`.
Version 0.9.12 is compatible.

## Source code
The source code is hosted on github: https://github.com/nive/nive_datastore

## Documentation
http://datastore.nive.co

## Installation

1) download and install packages
   
  bin/pip install nive_datastore

2) create a new datastore project and activate it

replace `datastoreSqlite` with `datastoreMysql` to use MySql as database server

  bin/pcreate -t datastoreSqlite myStorage
  cd myStorage
  ../bin/python setup.py develop

3)

Add new data collection configurations in __init__.py

4) start pyramid

  ../bin/pserve development.ini

### Translations
Translations can be extracted using lingua>=3.2

    > pip install lingua-3.2
    > bin/pot-create -o nive_datastore/locale/nive_datastore.pot nive_datastore

