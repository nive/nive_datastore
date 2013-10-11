# -*- coding: utf-8 -*-

import time
import unittest


from nive.utils.path import DvPath
from nive.definitions import *
from nive.portal import Portal
from nive_datastore.app import DataStorage

from nive.tests import __local


collection1 = ObjectConf(
    id = "bookmark",
    name = u"Bookmarks",
    dbparam = "bookmarks",
    subtypes="*",
    data = (
        FieldConf(id="link",     datatype="url",  size=500,   default=u"",  name=u"Link url"),
        FieldConf(id="share",    datatype="bool", size=2,     default=False,name=u"Share link"),
        FieldConf(id="comment",  datatype="text", size=50000, default=u"",  name=u"Comment"),
    ),
    forms = {
        "newItem": {"fields": ("link", "share", "comment"), "ajax":True, "newItem": True}, 
        "setItem": {"fields": ("link", "share", "comment"), "ajax":True}
    },
    render = ("id", "link", "comment", "pool_changedby", "pool_change"),
    template = "nive_datastore.webapi.tests:bookmark.pt"
)

collection2 = ObjectConf(
    id = "track",
    name = u"Track",
    dbparam = "tracks",
    subtypes=None,
    data = (
        FieldConf(id="url",       datatype="url",    size=500,   default=u"",  name=u"Url", required=True),
        FieldConf(id="number",    datatype="number", size=8,     default=0,    name=u"Some number"),
        FieldConf(id="something", datatype="text",   size=50000, default=u"",  name=u"Some text"),
    ),
    forms = {
        "newItem": {"fields": ("url", "number", "something"), "newItem": True }, 
        "setItem": {"fields": ("url", "number", "something") }
    }
)


dbconf = DatabaseConf(
    dbName = __local.ROOT+"datastore.db",
    fileRoot = __local.ROOT,
    context = "Sqlite3"
)
appconf = AppConf("nive_datastore.app",
    profiles={"bookmarks":  
                  {"pool_type": "bookmark", 
                   "container": False,
                   "fields": ["id", "link", "comment", "pool_changedby"],
                   "parameter": {}},
              "tracks":  
                  {"pool_type": "track", 
                   "container": True,
                   "fields": ["id", "link", "comment", "pool_changedby"],
                   "parameter": {}},
              "all": 
                  {"container": False,
                   "fields": ["id", "pool_create", "pool_changedby"],
                   "parameter": {}},
    },
    defaultProfile = "all"
)
appconf.modules.append(collection1)
appconf.modules.append(collection2)

def app(confs=()):
    a = DataStorage()
    a.Register(appconf)
    a.Register(dbconf)
    for c in confs:
        a.Register(c)
    p = Portal()
    p.Register(a)
    a.Startup(None)
    dbfile = DvPath(a.dbConfiguration.dbName)
    if not dbfile.IsFile():
        dbfile.CreateDirectories()
    try:
        a.Query("select id from pool_meta where id=1")
        a.Query("select id from bookmarks where id=1")
        a.Query("select id from tracks where id=1")
        a.Query("select id from pool_files where id=1")
    except:
        a.GetTool("nive.components.tools.dbStructureUpdater")()
    return a

def app_nodb():
    a = DataStorage()
    a.Register(appconf)
    a.Register(DatabaseConf())
    p = Portal()
    p.Register(a)
    #a.Startup(None)
    return a

def root(a):
    r = a.GetRoot()
    return r

