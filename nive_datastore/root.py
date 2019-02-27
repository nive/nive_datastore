# Copyright 2012-2014 Arndt Droullier, Nive GmbH. All rights reserved.
# Released under GPL3. See license.txt

"""
Root
----
The *root* is the entry point of the data storage. All contained items are stored 
in the database. The root itself does not store anything in the database by default.
The system supports multiple roots with unique urls to access items. 

Also this object provides search functions and sql query wrappers.
"""

from nive_datastore.i18n import _
from nive.container import Root
from nive.definitions import RootConf
from nive.definitions import AllTypesAllowed


class root(Root):

    def Init(self):
        self.queryRestraints = {}, {}
    
    


# Root definition ------------------------------------------------------------------
#@nive_module
configuration = RootConf(
    id = "api",
    context = "nive_datastore.root.root",
    default = True,
    subtypes = AllTypesAllowed,
    extensions = ("nive_datastore.pydispatch.Dispatcher",),
    name = _("Data root"),
    description = ""
)
