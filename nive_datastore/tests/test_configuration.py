# -*- coding: utf-8 -*-

import time
import unittest

from nive.helper import FormatConfTestFailure

from nive_datastore import app, root




class TestConf(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_conf1(self):
        r=app.configuration.test()
        if not r:
            return
        print FormatConfTestFailure(r)
        self.assert_(False, "Configuration Error")

    def test_conf2(self):
        r=root.configuration.test()
        if not r:
            return
        print FormatConfTestFailure(r)
        self.assert_(False, "Configuration Error")
