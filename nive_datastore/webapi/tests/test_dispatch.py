# -*- coding: utf-8 -*-

import time
import unittest

from nive.definitions import Conf, ConfigurationError
from nive.security import User
from nive_datastore.tests.db_app import *
from nive_datastore.tests.test_app import create_bookmark, create_track
from nive_datastore.webapi.view import *

from pyramid import testing 
from pyramid.httpexceptions import HTTPFound
from pyramid.renderers import render



class tWebapi(unittest.TestCase):

    def setUp(self):
        request = testing.DummyRequest()
        request._LOCALE_ = "en"
        self.request = request
        self.config = testing.setUp(request=request)
        self.app = app()
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



    def test_newUnsecured(self):
        user = User(u"test")
        user.groups.append("group:manager")

        # add success
        # single item
        param = {"pool_type": "bookmark", "link": u"the link", "comment": u"some text"}
        result, stat = self.root.dispatch("newItem", **param)
        self.assert_(len(result["result"])==1)
        self.root.Delete(result["result"][0], user=user)
        # single item list
        param = {"items": [{"pool_type": "bookmark", "link": u"the link", "comment": u"some text"}]}
        result, stat = self.root.dispatch("newItem", **param)
        self.assert_(len(result["result"])==1)
        self.root.Delete(result["result"][0], user=user)
        # multiple items list
        param = {"items": [{"pool_type": "bookmark", "link": u"the link 1", "comment": u"some text"},
                                      {"pool_type": "bookmark", "link": u"the link 2", "comment": u"some text"},
                                      {"pool_type": "bookmark", "link": u"the link 3", "comment": u"some text"}]}
        result,stat = self.root.dispatch("newItem", **param)
        self.assert_(len(result["result"])==3)
        self.root.Delete(result["result"][0], user=user)
        self.root.Delete(result["result"][1], user=user)
        self.root.Delete(result["result"][2], user=user)

        # add failure
        # no type
        param = {"pool_type": "nonono", "link": u"the link", "comment": u"some text"}
        result,stat = self.root.dispatch("newItem", **param)
        self.assert_(len(result["result"])==0)
        param = {"link": u"the link", "comment": u"some text"}
        result,stat = self.root.dispatch("newItem", **param)
        self.assert_(len(result["result"])==0)
        # validatio error
        param = {"pool_type": "track", "number": u"the link", "something": u"some text"}
        result,stat = self.root.dispatch("newItem", **param)
        self.assert_(len(result["result"])==0)
        # single item list
        param = {"items": [{"pool_type": "nonono", "link": u"the link", "comment": u"some text"}]}
        result,stat = self.root.dispatch("newItem", **param)
        self.assert_(len(result["result"])==0)
        param = {"items": [{"link": u"the link", "comment": u"some text"}]}
        result,stat = self.root.dispatch("newItem", **param)
        self.assert_(len(result["result"])==0)
        # multiple items list
        param = {"items": [{"pool_type": "bookmark", "link": u"the link 1", "comment": u"some text"},
                                                  {"link": u"the link 2", "comment": u"some text"},
                                                  {"pool_type": "bookmark", "link": u"the link 3", "comment": u"some text"}]}
        result,stat = self.root.dispatch("newItem", **param)
        self.assert_(len(result["result"])==0)
        
        # to many
        self.app.configuration.unlock()
        self.app.configuration.maxStoreItems = 2
        param = {"items": [{"pool_type": "bookmark", "link": u"the link 1", "comment": u"some text"},
                                                  {"link": u"the link 2", "comment": u"some text"},
                                                  {"pool_type": "bookmark", "link": u"the link 3", "comment": u"some text"}]}
        result,stat = self.root.dispatch("newItem", **param)
        self.app.configuration.maxStoreItems = 20
        self.app.configuration.lock()
        self.assert_(len(result["result"])==0)
        
        
        
    def test_newSecured(self):
        user = User(u"test")
        user.groups.append("group:manager")

        # add success
        # single item
        param = {"pool_type": "bookmark", "link": u"the link", "comment": u"some text"}
        result, stat = self.root.dispatch("newItem", True, self.request, **param)
        self.assert_(len(result["result"])==1)
        self.root.Delete(result["result"][0], user=user)
