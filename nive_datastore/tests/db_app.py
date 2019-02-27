# -*- coding: utf-8 -*-

import time
import unittest


from nive.utils.path import DvPath
from nive.definitions import ObjectConf, FieldConf, AppConf, DatabaseConf
from nive.portal import Portal
from nive_datastore.app import DataStorage


collection1 = ObjectConf("nive_datastore.item",
    id = "bookmark",
    name = "Bookmarks",
    dbparam = "bookmarks",
    subtypes="*",
    data = (
        FieldConf(id="link",     datatype="url",  size=500,   default="",  name="Link url"),
        FieldConf(id="share",    datatype="bool", size=2,     default=False,name="Share link"),
        FieldConf(id="comment",  datatype="text", size=50000, default="",  name="Comment"),
    ),
    forms = {
        "newItem": {"fields": ("link", "share", "comment"), "ajax":True, "newItem": True}, 
        "setItem": {"fields": ("link", "share", "comment"), "ajax":True}
    },
    toJson = ("id", "link", "comment", "pool_changedby", "pool_change"),
    template = "nive_datastore.webapi.tests:bookmark.pt"
)

collection2 = ObjectConf("nive_datastore.item",
    id = "track",
    name = "Track",
    dbparam = "tracks",
    subtypes=None,
    data = (
        FieldConf(id="url",       datatype="url",    size=500,   default="",  name="Url", required=True),
        FieldConf(id="number",    datatype="number", size=8,     default=0,    name="Some number"),
        FieldConf(id="something", datatype="text",   size=50000, default="",  name="Some text"),
    ),
    forms = {
        "newItem": {"fields": ("url", "number", "something"), "newItem": True }, 
        "setItem": {"fields": ("url", "number", "something") }
    },
    toJson = ("url", "number")
)


appconf = AppConf("nive_datastore.app",
    search = {
            "bookmarks":
                {"pool_type": "bookmark",
                 "container": False,
                 "fields": ["id", "link", "comment", "pool_changedby"],
                 "parameter": {},
                 "dynamic": {"size":10},
                 "size": 10},
            "tracks":
                {"pool_type": "track",
                 "container": True,
                 "fields": ["id", "link", "comment", "pool_changedby"],
                 "dynamic": {"size":10},
                 "parameter": {}},
            "default":
                {"container": False,
                 "fields": ["id", "pool_create", "pool_changedby"],
                 "dynamic": {"size":10, "start": 1},
                 "parameter": {}},
    },
)
appconf.modules.append(collection1)
appconf.modules.append(collection2)
appconf.lock()

def app_db(confs=None):
    a = DataStorage()
    a.Register(appconf)
    if confs:
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
        a.Query("select pool_wfp from pool_meta where id=1")
        a.Query("select id from bookmarks where id=1")
        a.Query("select id from tracks where id=1")
        a.Query("select id from pool_files where id=1")
    except:
        a.GetTool("nive.tools.dbStructureUpdater")()
    return a

def app_nodb():
    a = DataStorage()
    a.Register(appconf)
    a.Register(DatabaseConf())
    p = Portal()
    p.Register(a)
    #a.Startup(None)
    return a

def create_bookmark(c, user):
    type = "bookmark"
    data = {"link": "the link", "comment": "some text"}
    return c.Create(type, data=data, user=user)

def create_track(c, user):
    type = "track"
    data = {"url": "the url", "number": 123, "something": "some text"}
    return c.Create(type, data=data, user=user)