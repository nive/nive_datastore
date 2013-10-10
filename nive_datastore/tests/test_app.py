# -*- coding: utf-8 -*-

import time
import unittest

from nive.security import User
from nive_datastore.app import *
from nive_datastore.tests.db_app import *

def create_bookmark(c, user):
    type = "bookmark"
    data = {"link": u"the link", "comment": u"some text"}
    return c.Create(type, data=data, user=user)

def create_track(c, user):
    type = "track"
    data = {"url": u"the url", "number": 123, "something": u"some text"}
    return c.Create(type, data=data, user=user)


class AppTest(unittest.TestCase):

    def setUp(self):
        self.app = app()
        self.remove = []
        
    def tearDown(self):
        u = User(u"test")
        u.groups.append("group:manager")
        root = self.app.root()
        for r in self.remove:
            root.Delete(r, u)
        self.app.Close()

    def test_realdata(self):
        a=self.app
        ccc = a.db.GetCountEntries()
        r=root(a)
        user = User(u"test")
        user.groups.append("group:manager")
        # add to root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)

        o2 = create_track(r, user)
        self.remove.append(o2.id)

        self.assertEqual(ccc+2, a.db.GetCountEntries(), "Delete failed")

        r.Delete(o1.id, user=user, obj=o1)
        r.Delete(o2.id, user=user)
        self.assertEqual(ccc, a.db.GetCountEntries(), "Delete failed")


    def test_realdata_container(self):
        a=self.app
        ccc = a.db.GetCountEntries()
        r=root(a)
        user = User(u"test")
        user.groups.append("group:manager")
        # add to root
        o1 = create_bookmark(r, user)
        self.remove.append(o1.id)

        o2 = create_track(r, user)
        self.remove.append(o2.id)

        self.assertEqual(ccc+2, a.db.GetCountEntries(), "Delete failed")

        o3 = create_track(o1, user)

        self.assertRaises(ContainmentError, create_bookmark, o2, user)

        self.assertEqual(ccc+3, a.db.GetCountEntries(), "Delete failed")

        r.Delete(o1.id, user=user, obj=o1)
        r.Delete(o2.id, user=user)
        self.assertEqual(ccc, a.db.GetCountEntries(), "Delete failed")


    def test_interfaces(self):
        self.assertFalse(IItem.providedBy(123))
        self.assertFalse(IDatastorage.providedBy(123))
        
        
    def test_app(self):
        app = DataStorage(None)
        
        
        