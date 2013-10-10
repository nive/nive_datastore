# -*- coding: utf-8 -*-
# Copyright 2012, 2013 Arndt Droullier, Nive GmbH. All rights reserved.
# Released under GPL3. See license.txt

__doc__ = """
Nive Datastore Application configuration (sqlite example) and usage
-------------------------------------------------------------------
The `Nive DataStore` is a highlevel storage with a focus on build in 
functional extensions like form renderer, workflow integration, 
hierarchical data structures, flexible renderer and a web api.

Sqllite or Mysql are used as data backend so the goal is not replace 
database systems but to provide a flexible, easy and convenient way 
to store data items.

Database connection and basic datastore application configuration
::
    
    from nive.definitions import AppConf, DatabaseConf

    app = AppConf("nive_datastore.app",
                  id = "storage",
                  title = "My Data Storage",
                  maxStoreItems = 20,
                  maxBatchNumber = 100,
                  profiles = {"all":  {"type": "bookmark", "container": False,
                                       "fields": ["id", "link", "comment", "pool_changedby"],
                                       "parameter": {"share": True}
                                       }
                              },
                  defaultProfile = "all"
    )
    dbConfiguration = DatabaseConf(
                       fileRoot="/var/opt/datastore",
                       context=u"Sqlite3",
                       dbName="/var/opt/datastore/items.db"
    )
    app.modules.append(dbConfiguration)

**Items**

Item data field definitions are registered as typed collections. Each collection
has a unique type id, a custom set of data fields and many other options. Use
`nive.definitions.ObjectConf` as configuration class to define a new collection.

A simple example. Stores a bookmark and comment: ::

    bookmark = ObjectConf(
        id = "bookmark",
        name = _(u"Bookmarks"),
        dbparam = "bookmarks",
        data = (
          FieldConf(id="link",     datatype="url",  size=500,   default=u"",  name=u"Link url"),
          FieldConf(id="share",    datatype="bool", size=2,     default=False,name=u"Share link"),
          FieldConf(id="comment",  datatype="text", size=50000, default=u"",  name=u"Comment")
        ),
        forms = {
          "newItem": {"fields": ("link", "share", "comment") }, 
          "setItem": {"fields": ("link", "share", "comment") }
        },
        render = ("link", "share", "comment", "id", "pool_create", "pool_change"),
        template = "bookmark.pt",
    )
    app.modules.append(bookmark)  # app is the AppConf() defined in the previous example 
    
**Groups and permissions**

``configuration.acl`` and ``configuration.groups``

*Permissions:* read, search, add, edit, delete, webform, tojson, toxml, render, action

*Groups:* group:reader, group:manager, group:admin
    
By default groups and permissions are set up to reflect simple content management
workflows with four different roles. Groups can be used for both: view permissions
and workflow execution. 

The data storage has no workflow activated by default. So by reassigning permissions 
in `configuration.acl` the predefined groups can simply be customized. 

**Webforms**

The systems provides a build in form renderer. Form configurations are included in the collection
definition (`configuration.form`) and support by default create and edit modes. 

**Workflow**

Workflow processes can be added to the system to build a event system or extend the 
functionality. You can define and use multiple workflow processes and assign a process
to an item as needed (or define defaults). A workflow process is organized in states and
transitions. A transition can take one or multiple callbacks to be executed with the 
transition.  

By default the workflow is disabled. See `nive.definitions.AppConf.workflowEnabled` and 
`nive.definitions.ObjectConf.workflowID`

**Meta data**

The system automatically tracks create and change information in a shared meta table
(shared by all items). This table also stores the items globally unique id. To define 
database fields used for all collections use `nive.definitions.AppConf.meta`.

"""
import copy

from nive.i18n import _
from nive.definitions import implements, Interface
from nive.definitions import AppConf, FieldConf, GroupConf
from nive.definitions import SystemFlds, UserFlds
from nive.security import ALL_PERMISSIONS, Allow, Everyone, Deny
from nive.components.objects.base import ApplicationBase

#@nive_module
configuration = AppConf(
    id = "storage",
    title = u"Nive Data Storage",
    context = "nive_datastore.app.DataStorage",
    workflowEnabled = False,
    meta = copy.deepcopy(list(SystemFlds)) + copy.deepcopy(list(UserFlds)) 
)

configuration.modules = [
    # items / collections
    # -> no collections defined by default. See documentation how to define collections 
    #    based on 'nive.definitions.ObjectConf' 
    # root
    "nive_datastore.root",  
    # web api (view layer)
    "nive_datastore.webapi",
    #extensions
    #"nive.components.extensions.localgroups",
    # tools
    "nive.components.tools.dbStructureUpdater", "nive.components.tools.dbSqldataDump", "nive.components.tools.statistics",
    # administration and persistence
    "nive.adminview",
    "nive.components.extensions.persistence.dbPersistenceConfiguration"
]


configuration.acl = [
    (Allow, Everyone, 'view'),
    (Allow, 'group:reader', 'read'),
    (Allow, 'group:reader', 'search'),
    (Allow, 'group:reader', 'tojson'),
    (Allow, 'group:reader', 'toxml'),
    (Allow, 'group:reader', 'render'),

    (Allow, 'group:manager', 'read'),
    (Allow, 'group:manager', 'add'),
    (Allow, 'group:manager', 'update'), 
    (Allow, 'group:manager', 'delete'), 
    (Allow, 'group:manager', 'search'),
    (Allow, 'group:manager', 'webform'),
    (Allow, 'group:manager', 'tojson'),
    (Allow, 'group:manager', 'toxml'),
    (Allow, 'group:manager', 'render'),
    (Allow, 'group:manager', 'action'),

    (Allow, 'group:admin', ALL_PERMISSIONS), 
    (Deny, Everyone, ALL_PERMISSIONS),
]

configuration.groups = [
    GroupConf(id="group:reader",  name="group:reader"),
    GroupConf(id="group:author",  name="group:manager"),
    GroupConf(id="group:admin",   name="group:admin"),
]

class IItem(Interface):
    """
    """

class IDatastorage(Interface):
    """
    """
    
class DataStorage(ApplicationBase):
    """ the main cms application class """
    implements(IDatastorage)
    
    