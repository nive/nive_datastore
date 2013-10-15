
# Nive Data Storage
Nive Data Storage is a high level storage for structured data featuring many 
functional components and a Web API. 

## Features
- Structured data collections
- Typed collections
- Python and Json collection configuration
- Hierarchical cotainer support for data 
- Web API and Python connectors
- Worflow support
- Json and custom data renderes
- Build in form generator
- Detailed security permissions

## Version
This version is a beta release. The application is stable and complete. The public API as documented 
on the website is stable will not change. 

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



