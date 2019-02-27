# -*- coding: utf-8 -*-

import unittest

from nive.security import User
from nive.definitions import ContainmentError
from nive_datastore.app import DataStorage, IDataStorage
from nive_datastore.tests import db_app
from nive_datastore.tests import __local


class AppTest_db(object):

    def setUp(self):
        self._loadApp()
        self.remove = []
        
    def tearDown(self):
        u = User("test")
        u.groups.append("group:manager")
        root = self.app.root
        for r in self.remove:
            root.Delete(r, u)
        self.app.Close()

    def test_realdata(self):
        ccc = self.app.db.GetCountEntries()
        r = self.app.root
        user = User("test")
        user.groups.append("group:manager")
        # add to root
        o1 = db_app.create_bookmark(r, user)
        self.remove.append(o1.id)

        o2 = db_app.create_track(r, user)
        self.remove.append(o2.id)

        self.assertEqual(ccc+2, self.app.db.GetCountEntries(), "Delete failed")

        r.Delete(o1.id, user=user, obj=o1)
        r.Delete(o2.id, user=user)
        self.assertEqual(ccc, self.app.db.GetCountEntries(), "Delete failed")


    def test_realdata_container(self):
        ccc = self.app.db.GetCountEntries()
        r=self.app.root
        user = User("test")
        user.groups.append("group:manager")
        # add to root
        o1 = db_app.create_bookmark(r, user)
        self.remove.append(o1.id)

        o2 = db_app.create_track(r, user)
        self.remove.append(o2.id)

        self.assertEqual(ccc+2, self.app.db.GetCountEntries(), "Delete failed")

        o3 = db_app.create_track(o1, user)

        self.assertRaises(ContainmentError, db_app.create_bookmark, o2, user)

        self.assertEqual(ccc+3, self.app.db.GetCountEntries(), "Delete failed")

        r.Delete(o1.id, user=user, obj=o1)
        r.Delete(o2.id, user=user)
        self.assertEqual(ccc, self.app.db.GetCountEntries(), "Delete failed")


    def test_interfaces(self):
        self.assertFalse(IDataStorage.providedBy(123))
        self.assertTrue(IDataStorage.providedBy(DataStorage(None)))
        
        
    def test_app(self):
        app = DataStorage(None)
        


class AppTest_db_Sqlite(AppTest_db, __local.SqliteTestCase):
    pass
        
class AppTest_db_MySql(AppTest_db, __local.MySqlTestCase):
    pass
    
class AppTest_db_Postgres(AppTest_db, __local.PostgreSqlTestCase):
    pass
        