# -*- coding: utf-8 -*-

import time
import unittest

from nive.definitions import Conf, ConfigurationError
from nive.security import User
from nive_datastore.webapi.view import *
from nive_datastore.tests.db_app import *
from nive_datastore.tests import __local

from pyramid import testing 
from pyramid.httpexceptions import HTTPFound
from pyramid.renderers import render



class tWebapi_db(object):

    def setUp(self):
        request = testing.DummyRequest()
        request._LOCALE_ = "en"
        self.request = request
        self.request.content_type = ""
        self.config = testing.setUp(request=request)
        self.config.include('pyramid_chameleon')
        self._loadApp()
        self.app.Startup(self.config)
        self.root = self.app.root()
        user = User(u"test")
        user.groups.append("group:manager")
        self.request.context = self.root
        self.remove = []

    def tearDown(self):
        user = User(u"test")
        for r in self.remove:
            self.root.Delete(r, user)
        self.app.Close()
        testing.tearDown()


    def test_functions(self):
        values = {"key1":"", "key2":"null", "key3":"undefined", "key4":"123", "key5":"123.456"}
        self.assert_(ExtractJSValue(values, "key1", "default", "string")=="default")
        self.assert_(ExtractJSValue(values, "key2", "default", "string")=="default")
        self.assert_(ExtractJSValue(values, "key3", "default", "string")=="default")
        self.assert_(ExtractJSValue(values, "key4", "default", "int")==123)
        self.assert_(ExtractJSValue(values, "key5", "default", "float")==123.456)
        
        
    def test_deserialize(self):
        user = User(u"test")
        view = APIv1(self.root, self.request)
        r = self.root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        items = [o1]
        values = DeserializeItems(view, items)
        self.assert_(len(values)==1)
        items = o1
        values = DeserializeItems(view, items)
        self.assert_(len(values)==1)
        def ToDict():
            return {"no": 0}
        o1.ToDict = ToDict
        items = o1
        values = DeserializeItems(view, items)
        self.assert_(len(values)==1)
        self.assert_(values[0]["no"]==0)


    def test_serialize(self):
        user = User(u"test")
        view = APIv1(self.root, self.request)
        r = self.root
        values = {"link": u"the link 1", "comment": u"some text"}
        result, data, errors = SerializeItem(view, values, "bookmark", "newItem")
        self.assert_(result)
        self.assert_(data==values)
        result, data, errors = SerializeItem(view, values, "bookmark", "no subset")
        self.assert_(result)
        self.assert_(data==values)


    def test_new(self):
        view = APIv1(self.root, self.request)
        user = User(u"test")
        user.groups.append("group:manager")

        # add success
        # single item
        self.request.POST = {"pool_type": "bookmark", "link": u"the link", "comment": u"some text"}
        result = view.newItem()
        self.assert_(len(result["result"])==1)
        self.root.Delete(result["result"][0], user=user)
        # single item list
        self.request.POST = {"items": [{"pool_type": "bookmark", "link": u"the link", "comment": u"some text"}]}
        result = view.newItem()
        self.assert_(len(result["result"])==1)
        self.root.Delete(result["result"][0], user=user)
        # multiple items list
        self.request.POST = {"items": [{"pool_type": "bookmark", "link": u"the link 1", "comment": u"some text"},
                                                  {"pool_type": "bookmark", "link": u"the link 2", "comment": u"some text"},
                                                  {"pool_type": "bookmark", "link": u"the link 3", "comment": u"some text"}]}
        result = view.newItem()
        self.assert_(len(result["result"])==3)
        self.root.Delete(result["result"][0], user=user)
        self.root.Delete(result["result"][1], user=user)
        self.root.Delete(result["result"][2], user=user)

        # add failure
        # no type
        self.request.POST = {"pool_type": "nonono", "link": u"the link", "comment": u"some text"}
        result = view.newItem()
        self.assert_(len(result["result"])==0)
        self.request.POST = {"link": u"the link", "comment": u"some text"}
        result = view.newItem()
        self.assert_(len(result["result"])==0)
        # validatio error
        self.request.POST = {"pool_type": "track", "number": u"the link", "something": u"some text"}
        result = view.newItem()
        self.assert_(len(result["result"])==0)
        # single item list
        self.request.POST = {"items": [{"pool_type": "nonono", "link": u"the link", "comment": u"some text"}]}
        result = view.newItem()
        self.assert_(len(result["result"])==0)
        self.request.POST = {"items": [{"link": u"the link", "comment": u"some text"}]}
        result = view.newItem()
        self.assert_(len(result["result"])==0)
        # multiple items list
        self.request.POST = {"items": [{"pool_type": "bookmark", "link": u"the link 1", "comment": u"some text"},
                                                  {"link": u"the link 2", "comment": u"some text"},
                                                  {"pool_type": "bookmark", "link": u"the link 3", "comment": u"some text"}]}
        result = view.newItem()
        self.assert_(len(result["result"])==0)
        
        # to many
        self.app.configuration.unlock()
        self.app.configuration.maxStoreItems = 2
        self.request.POST = {"items": [{"pool_type": "bookmark", "link": u"the link 1", "comment": u"some text"},
                                                  {"link": u"the link 2", "comment": u"some text"},
                                                  {"pool_type": "bookmark", "link": u"the link 3", "comment": u"some text"}]}
        result = view.newItem()
        self.app.configuration.maxStoreItems = 20
        self.app.configuration.lock()
        self.assert_(len(result["result"])==0)
        
        
    def test_get(self):
        view = APIv1(self.root, self.request)
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        o2 = create_track(r, user)
        self.remove.append(o2.id)
        o3 = create_bookmark(r, user)
        self.remove.append(o3.id)
        
        # get single
        self.request.POST = {"id": str(o1.id)}
        result = view.getItem()
        self.assert_(len(result)==1)
        self.assert_(result[0]["link"]=="the link")
        
        # get three
        self.request.POST = {"id": [o1.id,o2.id,o3.id]}
        result = view.getItem()
        self.assert_(len(result)==3)
        self.assert_(result[0]["link"]=="the link")
        self.assert_(result[1]["url"]=="the url")
        self.assert_(result[2]["link"]=="the link")
        
        # get two rigth
        self.root.Delete(o3.id, user=user)
        self.request.POST = {"id": [o1.id,o2.id,o3.id]}
        result = view.getItem()
        self.assert_(len(result)==2)
        self.assert_(result[0]["link"]=="the link")
        self.assert_(result[1]["url"]=="the url")

        # get none
        self.request.POST = {"id": ""}
        result = view.getItem()
        self.assert_(result.get("error"))
        
        self.request.POST = {"id": "ababab"}
        result = view.getItem()
        self.assert_(result.get("error"))


    def test_set(self):
        view = APIv1(self.root, self.request)
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        o2 = create_track(r, user)
        self.remove.append(o2.id)
        o3 = create_bookmark(r, user)
        self.remove.append(o3.id)
        
        # update single
        self.request.POST = {"id": str(o1.id), "link": u"the link new", "comment": u"some text"}
        result = view.setItem()
        self.assert_(len(result)==1)
        o = self.root.GetObj(o1.id)
        self.assert_(o.data.link=="the link new")
        
        # update single
        self.request.POST = {"items": [{"id": str(o1.id), "link": u"the link", "comment": u"some text"}]}
        result = view.setItem()
        self.assert_(len(result["result"])==1)
        o = self.root.GetObj(result["result"][0])
        self.assert_(o.data.link=="the link")
        
        # update multiple
        self.request.POST = {"items": [
                             {"id": str(o1.id), "link": u"the link new", "comment": u"some text"},
                             {"id": str(o2.id), "url": u"the url new"},
                             {"id": str(o3.id), "link": u"the link new", "comment": u"some text"},
                             ]}
        result = view.setItem()
        self.assert_(len(result["result"])==3)
        o = self.root.GetObj(result["result"][0])
        self.assert_(o.data.link=="the link new")
        o = self.root.GetObj(result["result"][1])
        self.assert_(o.data.url=="the url new")
        o = self.root.GetObj(result["result"][2])
        self.assert_(o.data.link=="the link new")
        
        # failures
        # update single
        self.request.POST = {"link": u"the link new", "comment": u"some text"}
        result = view.setItem()
        self.assert_(len(result["result"])==0)
        # update single
        self.request.POST = {"id": str(9999999), "link": u"the link new", "comment": u"some text"}
        result = view.setItem()
        self.assert_(len(result["result"])==0)
        
        # update single
        self.request.POST = {"items": [{"link": u"the link", "comment": u"some text"}]}
        result = view.setItem()
        self.assert_(len(result["result"])==0)
        
        # not found
        self.request.POST = {"items": [
                             {"id": str(o1.id), "link": u"the link new", "comment": u"some text"},
                             {"id": "999999999", "url": u"the url new"},
                             {"id": str(o3.id), "link": u"the link new", "comment": u"some text"},
                             ]}
        result = view.setItem()
        self.assert_(len(result["result"])==0)
        # no id
        self.request.POST = {"items": [
                             {"id": str(o1.id), "link": u"the link new", "comment": u"some text"},
                             {"url": u"the url new"},
                             {"id": str(o3.id), "link": u"the link new", "comment": u"some text"},
                             ]}
        result = view.setItem()
        self.assert_(len(result["result"])==0)
        # validation error
        self.request.POST = {"items": [
                             {"id": str(o1.id), "link": u"the link new", "comment": u"some text"},
                             {"id": str(o2.id), "number": 444},
                             {"id": str(o3.id), "link": u"the link new", "comment": u"some text"},
                             ]}
        result = view.setItem()
        self.assert_(len(result["result"])==0)


    def test_delete(self):
        view = APIv1(self.root, self.request)
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        o2 = create_track(r, user)
        self.remove.append(o2.id)
        o3 = create_bookmark(r, user)
        self.remove.append(o3.id)
        
        # delete single
        self.request.POST = {"id": str(o1.id)}
        result = view.deleteItem()
        self.assert_(len(result["result"])==1)
        o = self.root.GetObj(o1.id)
        self.assert_(o==None)

        # delete two
        self.request.POST = {"id": [str(o2.id),str(o3.id)]}
        result = view.deleteItem()
        self.assert_(len(result["result"])==2)
        o = self.root.GetObj(o2.id)
        self.assert_(o==None)
        o = self.root.GetObj(o3.id)
        self.assert_(o==None)

        # delete error
        self.request.POST = {"id": 9999999}
        result = view.deleteItem()
        self.assert_(len(result["result"])==0)
        self.request.POST = {"idno": 9999999}
        result = view.deleteItem()
        self.assert_(len(result["result"])==0)

        # delete json err
        self.request.POST = {"id": "oh no"}
        result = view.deleteItem()
        self.assert_(len(result["result"])==0)
        
        
    def test_itemcontext(self):
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        o2 = create_track(r, user)
        self.remove.append(o2.id)
        
        self.request.context = o1
        view = APIv1(o1, self.request)
        result = view.getContext()
        self.assert_(result)
        self.assert_(result["link"]=="the link")

        self.request.context = o2
        view = APIv1(o2, self.request)
        result = view.getContext()
        self.assert_(result)
        self.assert_(result["url"]=="the url")


        self.request.context = o1
        view = APIv1(o1, self.request)
        self.request.POST = {"link": u"the link new", "comment": u"some text"}
        result = view.updateContext()
        o = self.root.GetObj(o1.id)
        self.assert_(o.data.link==u"the link new")

        self.request.context = o2
        view = APIv1(o2, self.request)
        self.request.POST = {"number": 444}
        result = view.updateContext()
        self.assert_(result.get("error"))
        o = self.root.GetObj(o2.id)
        self.assert_(o.data.number==123)
   
   
    def test_listings(self):
        user = User(u"test")
        user.groups.append("group:manager")
        view = APIv1(self.root, self.request)
        r = self.root
        objs=r.GetObjs()
        for o in objs:
            r.Delete(o.id, obj=o, user=user)
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        o2 = create_track(r, user)
        self.remove.append(o2.id)
        o3 = create_bookmark(r, user)
        self.remove.append(o3.id)
        o4 = create_track(r, user)
        self.remove.append(o4.id)

        # testing listings and parameter
        self.request.POST = {}
        result = view.listItems()
        self.assert_(len(result["items"])==4)

        self.request.POST = {"start":2}
        result = view.listItems()
        self.assert_(result["start"]==2)
        self.assert_(len(result["items"])==2)

        self.request.POST = {"pool_type": "track"}
        result = view.listItems()
        self.assert_(len(result["items"])==2)

        self.request.POST = {"sort":"pool_change", "order":"<", "size":2}
        result = view.listItems()
        self.assert_(len(result["items"])==2)

        self.request.POST = {"sort":"id", "order":"<", "size":2}
        result = view.listItems()
        self.assert_(len(result["items"])==2)
        ids = result["items"]
        self.request.POST = {"sort":"id", "order":">", "size":2}
        result = view.listItems()
        self.assert_(result["items"]!=ids)
        
        self.request.POST = {"sort":"id", "order":"<", "size":4}
        result = view.listItems()
        ids = result["items"]
        self.request.POST = {"sort":"id", "order":">", "size":4}
        result = view.listItems()
        self.assert_(ids[0]==result["items"][3])
        self.assert_(ids[1]==result["items"][2])
        
        
    def test_listingsContainer(self):
        user = User(u"test")
        user.groups.append("group:manager")
        view = APIv1(self.root, self.request)
        r = self.root
        objs=r.GetObjs()
        for o in objs:
            r.Delete(o.id, obj=o, user=user)
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        o3 = create_bookmark(r, user)
        self.remove.append(o3.id)
        
        o2 = create_bookmark(o1, user)
        create_track(o1, user)
        create_track(o1, user)
        create_track(o3, user)

        # testing listings and parameter
        self.request.POST = {}
        result = view.listItems()
        self.assert_(len(result["items"])==2)

        view = APIv1(o1, self.request)
        result = view.listItems()
        self.assert_(len(result["items"])==3)

        view = APIv1(o1, self.request)
        result = view.listItems()
        self.assert_(len(result["items"])==3)

        view = APIv1(o2, self.request)
        result = view.listItems()
        self.assert_(len(result["items"])==0)

        view = APIv1(o1, self.request)
        self.request.POST = {"pool_type": "track"}
        result = view.listItems()
        self.assert_(len(result["items"])==2)

        
    def test_listingsFailure(self):
        user = User(u"test")
        user.groups.append("group:manager")
        view = APIv1(self.root, self.request)
        r = self.root

        # testing listings and parameter
        self.request.POST = {"start": "wrong number"}
        result = view.listItems()
        self.assert_(result["error"])
        self.assert_(len(result["items"])==0)

        # testing listings and parameter
        self.request.POST = {"size": "wrong number"}
        result = view.listItems()
        self.assert_(result["error"])
        self.assert_(len(result["items"])==0)


    def test_searchConf(self):
        user = User(u"test")
        user.groups.append("group:manager")
        view = APIv1(self.root, self.request)
        r = self.root
        objs=r.GetObjs()
        for o in objs:
            r.Delete(o.id, obj=o, user=user)
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        o3 = create_bookmark(r, user)
        self.remove.append(o3.id)
        
        o2 = create_bookmark(o1, user)
        create_track(o1, user)
        create_track(o1, user)
        create_track(o3, user)

        self.request.POST = {}
        result = view.searchItems()
        self.assert_(len(result["items"])==6)

        self.request.POST = {"profile":"bookmarks"}
        result = view.searchItems()
        self.assert_(len(result["items"])==3)
    
        # container activated
        self.request.POST = {"profile":"tracks"}
        result = view.searchItems()
        self.assert_(len(result["items"])==0, result)

        view = APIv1(o1, self.request)
        self.request.POST = {"profile":"tracks"}
        result = view.searchItems()
        self.assert_(len(result["items"])==2, result)
    
        self.request.POST = {"size":2}
        result = view.searchItems()
        self.assert_(len(result["items"])==2)
        self.assert_(result["size"]==2)
        self.assert_(result["start"]==1,result)
        self.assert_(result["total"]==6)

        self.request.POST = {"size":2,"start":3}
        result = view.searchItems()
        self.assert_(len(result["items"])==2)
        self.assert_(result["size"]==2)
        self.assert_(result["start"]==3,result)
        self.assert_(result["total"]==6)

        self.request.POST = {"size":2,"start":6}
        result = view.searchItems()
        self.assert_(len(result["items"])==1, result)
        self.assert_(result["size"]==1)
        self.assert_(result["start"]==6)
        self.assert_(result["total"]==6,result)

    
    def test_searchParam(self):
        user = User(u"test")
        user.groups.append("group:manager")
        view = APIv1(self.root, self.request)
        r = self.root
        objs=r.GetObjs()
        for o in objs:
            r.Delete(o.id, obj=o, user=user)
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        o3 = create_bookmark(r, user)
        self.remove.append(o3.id)

        o2 = create_bookmark(o1, user)
        create_track(o1, user)
        create_track(o1, user)
        create_track(o3, user)

        self.request.POST = {}

        profile = {
            "container": False,
            "fields": ["id", "pool_changedby"],
            "parameter": {}
        }
        result = view.searchItems(profile=profile)
        self.assert_(len(result["items"])==6)

        profile = {
            "container": False,
            "fields": ["id", "pool_changedby"],
            "parameter": {"pool_changedby":"test"},
            "operators": {"pool_changedby":"="}
        }
        result = view.searchItems(profile=profile)
        self.assert_(len(result["items"])==6)

        profile = {
            "container": False,
            "fields": ["id", "pool_changedby"],
            "parameter": {"pool_changedby":"test"},
            "operators": {"pool_changedby":"<>"}
        }
        result = view.searchItems(profile=profile)
        self.assert_(len(result["items"])==0)

        profile = {
            "container": False,
            "fields": ["pool_type"],
            "parameter": {"pool_changedby":"test"},
            "operators": {"pool_changedby":"="},
            "groupby": "pool_type"
        }
        result = view.searchItems(profile=profile)
        self.assert_(len(result["items"])==2)

    
    def test_searchFailure(self):
        user = User(u"test")
        user.groups.append("group:manager")
        view = APIv1(self.root, self.request)
        r = self.root

        # testing listings and parameter
        self.request.POST = {"start": "wrong number"}
        result = view.searchItems()
        self.assert_(result["error"])
        self.assert_(len(result["items"])==0)

        # testing listings and parameter
        self.request.POST = {"size": "wrong number"}
        result = view.searchItems()
        self.assert_(result["error"])
        self.assert_(len(result["items"])==0)

        # testing listings and parameter
        self.request.POST = {"profile": "not a profile"}
        result = view.searchItems()
        self.assert_(result["error"])
        self.assert_(len(result["items"])==0)

        # testing listings and parameter
        profiles = self.app.configuration.profiles
        self.app.configuration.unlock()
        self.app.configuration.profiles = None
        self.request.POST = {"profile": "all"}
        try:
            result = view.searchItems()
        except:
            self.app.configuration.profiles = profiles
            self.app.configuration.lock()
            raise
        self.app.configuration.profiles = profiles
        self.assert_(result["error"])
        self.assert_(len(result["items"])==0)
        self.app.configuration.lock()

        
    def test_renderjson(self):
        user = User(u"test")
        user.groups.append("group:manager")
        view = APIv1(self.root, self.request)
        r = self.root
        objs=r.GetObjs()
        for o in objs:
            r.Delete(o.id, obj=o, user=user)
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        o3 = create_bookmark(r, user)
        self.remove.append(o3.id)

        o2 = create_bookmark(o1, user)
        create_track(o1, user)
        create_track(o1, user)
        create_track(o3, user)

        values = view.renderJson()
        self.assert_(values=={})

        self.request.POST = {"subtree": "1"}
        values = view.renderJson()
        self.assert_(values!={})
        self.assert_(len(values["items"])==2)
        self.assert_(len(values["items"][0]["items"])==1)
        self.assert_(values["items"][0]["link"]==u"the link")
        self.assert_(values["items"][0].get("share")==None)
                                            
        view = APIv1(o1, self.request)
        self.request.POST = {"subtree": "0"}
        values = view.renderJson()
        self.assert_(values!={})
        self.assert_(values.get("items")==None)
        

    def test_rendertmpl(self):
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        objs=r.GetObjs()
        for o in objs:
            r.Delete(o.id, obj=o, user=user)
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        o3 = create_bookmark(r, user)
        self.remove.append(o3.id)

        o2 = create_bookmark(o1, user)
        create_track(o1, user)
        create_track(o1, user)
        create_track(o3, user)

        view = APIv1(o1, self.request)
        data = view.renderTmpl()
        self.assert_(data)


    def test_newform(self):
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        
        view = APIv1(r, self.request)

        self.request.POST = {"pool_type": "bookmark", "link": u"the link", "comment": u"some text"}
        result = view.newItemForm()
        self.assert_(result["result"])

        objs=len(r.GetObjsList(fields=["id"]))
        self.request.POST = {"pool_type": "bookmark", "link": u"the link", "comment": u"some text", "create$": "1"}
        result = view.newItemForm()
        self.assert_(result["result"])
        self.remove.append(result["result"])
        self.assert_(objs+1==len(r.GetObjsList(fields=["id"])))


    def test_newformfailures(self):
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        
        view = APIv1(r, self.request)

        # no type
        self.request.POST = {"link": u"the link", "comment": u"some text"}
        result = view.newItemForm()
        self.assertFalse(result["result"])

        objs=len(r.GetObjsList(fields=["id"]))
        self.request.POST = {"link": u"the link", "comment": u"some text", "create$": "1"}
        result = view.newItemForm()
        self.assertFalse(result["result"])
        self.assert_(objs==len(r.GetObjsList(fields=["id"])))
        
        # wrong subset
        self.request.POST = {"subset": "unknown!", "pool_type": "bookmark", "link": u"the link", "comment": u"some text"}
        self.assertRaises(ConfigurationError, view.newItemForm)

        # wrong action
        objs=len(r.GetObjsList(fields=["id"]))
        self.request.POST = {"pool_type": "bookmark", "link": u"the link", "comment": u"some text", "unknown$": "1"}
        result = view.newItemForm()
        self.assert_(result["result"])
        self.remove.append(result["result"])
        self.assert_(objs==len(r.GetObjsList(fields=["id"])))
        
        
    def test_setform(self):
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        
        view = APIv1(o1, self.request)

        self.request.POST = {}
        result = view.setItemForm()
        self.assert_(result["result"])

        objs=len(r.GetObjsList(fields=["id"]))
        self.request.POST = {"link": u"the new link", "comment": u"some new text", "create$": "1"}
        result = view.setItemForm()
        self.assert_(result["result"])
        self.remove.append(result["result"])
        self.assert_(objs==len(r.GetObjsList(fields=["id"])))


    def test_newformfailures(self):
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        
        view = APIv1(o1, self.request)

        # wrong subset
        self.request.POST = {"subset": "unknown!", "pool_type": "bookmark", "link": u"the link", "comment": u"some text"}
        self.assertRaises(ConfigurationError, view.setItemForm)

        # wrong action
        objs=len(r.GetObjsList(fields=["id"]))
        self.request.POST = {"pool_type": "bookmark", "link": u"the link", "comment": u"some text", "unknown$": "1"}
        result = view.setItemForm()
        self.assert_(result["result"])
        self.remove.append(result["result"])
        self.assert_(objs==len(r.GetObjsList(fields=["id"])))
        
        
    def test_noaction(self):
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        
        view = APIv1(o1, self.request)

        self.request.POST = {"action": "unknown!"}
        result = view.action()
        self.assertFalse(result["result"])

        # test returns true if no workflow loaded
        self.request.POST = {"action": "unknown!", "test":"true"}
        result = view.action()
        self.assert_(result["result"])

        self.request.POST = {"action": "unknown!", "transition":"oooooo"}
        result = view.action()
        self.assertFalse(result["result"])


    def test_nostate(self):
        user = User(u"test")
        user.groups.append("group:manager")
        r = self.root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)
        
        view = APIv1(o1, self.request)

        result = view.state()
        self.assertFalse(result["result"])





class tWebapi_db_sqlite(tWebapi_db, __local.SqliteTestCase):
    """
    see tests.__local
    """

class tWebapi_db_mysql(tWebapi_db, __local.MySqlTestCase):
    """
    see tests.__local
    """
    
class tWebapi_db_pg(tWebapi_db, __local.PostgreSqlTestCase):
    """
    see tests.__local
    """



