# -*- coding: utf-8 -*-

import time
import unittest

from nive.helper import FormatConfTestFailure

from nive_datastore.webapi import view




class TestConf(unittest.TestCase):

    def test_conf1(self):
        r=view.configuration.test()
        if not r:
            return
        print FormatConfTestFailure(r)
        self.assert_(False, "Configuration Error")


