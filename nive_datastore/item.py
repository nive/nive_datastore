# Copyright 2012-2014 Arndt Droullier, Nive GmbH. All rights reserved.
# Released under GPL3. See license.txt

"""
Item
----
"""

from nive_datastore.i18n import _
from nive.components.baseobjects import ObjectContainerBase
from nive.definitions import ObjectConf


class item(ObjectContainerBase):

    def Init(self):
        self.queryRestraints = {}, {}
    
    


# Root definition ------------------------------------------------------------------
#@nive_module
configuration = ObjectConf(
    id = "item",
    context = "nive_datastore.item.item",
    extensions = ("nive_datastore.pydispatch.Dispatcher",),
    name = _(u"Data item"),
    description = u""
)
