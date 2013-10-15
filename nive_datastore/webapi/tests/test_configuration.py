# -*- coding: utf-8 -*-

import time
import unittest

from nive.helper import FormatConfTestFailure

from nive_datastore.webapi import view




class TestConf(unittest.TestCase):

    def test_confcontainer(self):
        r=view.container_views.test()
        if not r:
            return
        print FormatConfTestFailure(r)
        self.assert_(False, "Configuration Error")

    def test_confitems(self):
        r=view.item_views.test()
        if not r:
            return
        print FormatConfTestFailure(r)
        self.assert_(False, "Configuration Error")

