# Copyright 2012-2014 Arndt Droullier, Nive GmbH. All rights reserved.
# Released under GPL3. See license.txt

import time
import logging
import json
import copy

from pyramid.httpexceptions import HTTPForbidden
from pyramid.security import has_permission

from nive.definitions import ViewModuleConf, ViewConf, Conf
from nive.definitions import IObject, IContainer
from nive.workflow import WorkflowNotAllowed
from nive.views import BaseView
from nive.forms import Form, ObjectForm
from nive.security import Allow, Everyone
from nive.helper import JsonDataEncoder
from nive.helper import ResolveName

from nive_datastore.i18n import _

# view module definition ------------------------------------------------------------------

#@nive_module
item_views = ViewModuleConf(
    id = "DatastoreAPIv1-Item",
    name = _(u"Data storage item api"),
    containment = "nive_datastore.app.IDataStorage",
    view = "nive_datastore.webapi.view.APIv1",
    context = "nive.definitions.IObject",
    views = (
        # read
        ViewConf(name="",            attr="getContext",  permission="api-read",       renderer="json"),
        # update
        ViewConf(name="update",      attr="setContext",  permission="api-update",     renderer="json"),
        # rendering
        ViewConf(name="subtree",     attr="subtree",     permission="api-subtree"),
        ViewConf(name="render",      attr="render",      permission="api-render"),
        # forms
        ViewConf(name="updateForm",  attr="updateForm",  permission="api-updateform"),
        # workflow
        ViewConf(name="action",      attr="action",      permission="api-action",     renderer="json"),
        ViewConf(name="state",       attr="state",       permission="api-state",      renderer="json"),
    ),
    acl = (
        (Allow, "group:reader",  "api-read"),
        (Allow, "group:reader",  "api-subtree"),
        (Allow, "group:reader",  "api-render"),

        (Allow, "group:editor", "api-read"),
        (Allow, "group:editor", "api-update"), 
        (Allow, "group:editor", "api-subtree"),
        (Allow, "group:editor", "api-render"),
        (Allow, "group:editor", "api-updateform"),
        (Allow, "group:editor", "api-action"),
        (Allow, "group:editor", "api-state"),
    )
)

#@nive_module
container_views = ViewModuleConf(
    id = "DatastoreAPIv1-Container",
    name = _(u"Data storage container api"),
    containment = "nive_datastore.app.IDataStorage",
    view = "nive_datastore.webapi.view.APIv1",
    context = "nive.definitions.IContainer",
    views = (
        # list and search
        ViewConf(name="listItems",  attr="listItems",  permission="api-search", renderer="json"),
        ViewConf(name="searchItems",attr="searchItems",permission="api-search", renderer="json"),
        # read contained item
        ViewConf(name="getItem",    attr="getItem",    permission="api-read",   renderer="json"),
        # rendering
        ViewConf(name="subtree",    attr="subtree",    permission="api-subtree"),
        ViewConf(name="render",     attr="render",     permission="api-render"),
        # add and update contained item
        ViewConf(name="newItem",    attr="newItem",    permission="api-add",    renderer="json"),
        ViewConf(name="setItem",    attr="setItem",    permission="api-update", renderer="json"),
        # forms
        ViewConf(name="newItemForm",attr="newItemForm",permission="api-addform"),
        # delete
        ViewConf(name="deleteItem", attr="deleteItem", permission="api-delete", renderer="json"),
    ),
    acl = (
        (Allow, "group:reader", "api-search"),
        (Allow, "group:reader", "api-read"),
    
        (Allow, "group:editor", "api-search"),
        (Allow, "group:editor", "api-read"),
        (Allow, "group:editor", "api-add"),
        (Allow, "group:editor", "api-update"),
        (Allow, "group:editor", "api-addform"),
        (Allow, "group:editor", "api-delete"), 
    )
)

DefaultMaxStoreItems = 20
DefaultMaxBatchNumber = 100
jsUndefined = (u"", u"null", u"undefined", None)
ignoreFields = ("pool_dataref","pool_datatbl")

# internal data processing ------------------------------------------------------------

def DeserializeItems(view, items):
    # Convert item objects to dicts before returning to the user
    values = []

    if not isinstance(items, (list,tuple)):
        items = [items]
    metafields = view.context.app.GetAllMetaFlds(False)
    for item in items:
        try:
            # try the items ToDict function if available
            data = item.ToDict()
            values.append(data)
            continue
        except (ValueError, AttributeError):
            pass
        data = {}
        # meta 
        for field in metafields:
            if field["id"] in ignoreFields:
                continue
            data[field["id"]] = item.meta[field["id"]]
        # data
        for field in item.configuration.data:
            if field["id"] == "id":
                continue
            data[field["id"]] = item.data[field["id"]]
        values.append(data)
    return values

def SerializeItem(view, values, typename, formsubset):
    # Serialize items based on formsubset values
    if isinstance(typename, basestring):
        typeconf = view.context.app.GetObjectConf(typename)
    else:
        typeconf = typename
            
    try:
        fconf = typeconf.forms.get(formsubset)
    except AttributeError:
        fconf = None
    if not fconf:
        formsubset = None
        
    # load form
    form = Form(view=view, loadFromType=typeconf)
    form.Setup(subset=formsubset)
    result, data, errors = form.ValidateSchema(values)
    return result, data, errors
        
        
def ExtractJSValue(values, key, default, format):
    value = values.get(key, default)
    if value in jsUndefined:
        return default
    elif format=="int":
        return int(value)
    elif format=="bool":
        if value in (1, True, "1","true","True","Yes","yes","checked"):
            return True
        return False
    elif format=="float":
        return float(value)
    return value



class APIv1(BaseView):

    # json datastore api

    def getItem(self):
        """
        Returns the items for the id(s). 
        
        - id: the items' id or a list of multiple items
        
        returns json encoded data, if multiple items
        """
        response = self.request.response
        ids = self.GetFormValue("id")
        if not isinstance(ids, (list,tuple)):
            try:
                ids = [int(ids)]
            except (ValueError, TypeError):
                # set http response code (invalid request)
                response.status = u"400 Invalid id"
                return {"error": u"Invalid id"}
        if not ids:
            # set http response code (invalid request)
            response.status = u"400 Empty id"
            return {"error": u"Empty id"}

        items = []
        error = []
        for id in ids:
            item = self.context.GetObj(id)
            if not item:
                error.append(u"Item not found.")
                continue
            items.append(item)
        return DeserializeItems(self, items)
    
    
    def newItem(self):
        """
        Creates a single item or a set of items as batch. Values are serialized and
        validated by 'newItem' form subset. If not set, all fields are allowed. 
        
        Request parameter:
        
        - type: the new type to be created. Must be set for each item.
        - <fields>: A single item can be passed as form values.
        - items (optional): One or multiple items to be stored. Multiple items have to be passed as 
          array. Maximum number of 20 items allowed.
          
        Returns json encoded result: {"result": list of new item ids}
        """
        response = self.request.response

        user = self.User()

        items = self.GetFormValue("items")
        if not items:
            values = self.GetFormValues()
            typename = values.get("type") or values.get("pool_type")
            if not typename:
                response.status = u"400 No type given"
                return {"error": "No type given", "result":[]}
            typeconf = self.context.app.GetObjectConf(typename)
            if not typeconf:
                response.status = u"400 Unknown type"
                return {"error": "Unknown type", "result":[]}
            subset = self.GetFormValue("subset") or "newItem"
            result, values, errors = SerializeItem(self, values, typename=typeconf, formsubset=subset)
            if not result:
                response.status = u"400 Validation error"
                return {"error": str(errors), "result":[]}
            item = self.context.Create(typename, data=values, user=user)
            if not item:
                response.status = u"400 Validation error"
                return {"error": "Validation error", "result":[]}
            return {"result": [item.id]}

        maxStoreItems = self.context.app.configuration.get("maxStoreItems") or DefaultMaxStoreItems
        if len(items) > maxStoreItems:
            response.status = u"413 Too many items"
            return {"error": u"Too many items.", "result":[]}

        validated = []
        cnt = 1
        defaulttype = self.GetFormValue("type") or self.GetFormValue("pool_type")
        for values in items:
            typename = values.get("type") or values.get("pool_type") or defaulttype
            if not typename:
                response.status = u"400 No type given"
                return {"error": "No type given: Item "+str(cnt), "result":[]}
            typeconf = self.context.app.GetObjectConf(typename)
            if not typeconf:
                response.status = u"400 Unknown type"
                return {"error": "Unknown type", "result":[]}
            subset = self.GetFormValue("subset") or "newItem"
            result, values, errors = SerializeItem(self, values, typename=typeconf, formsubset=subset)
            if not result:
                response.status = u"400 Validation error"
                return {"error": str(errors), "result":[]}
            validated.append(values)
            cnt += 1

        new = []
        error = []
        for values in validated:
            item = self.context.Create(typename, data=values, user=user)
            if not item:
                error.append("Creation error")
                continue
            new.append(item.id)
        return {"result": new, "error": error}


    def setItem(self):
        """
        Store a single item or a set of items as batch. Values are serialized and
        validated by 'setItem' form subset. If not set, all fields are allowed. 
        
        Request parameter:
        
        - <fields>: A single item can be passed as form values.
        - items (optional): One or multiple items to be stored. Multiple items have to be passed as 
          array. Maximum number of 20 items allowed.
          
        Returns json encoded result: {"result": list of stored item ids}
        """
        response = self.request.response

        user = self.User()

        items = self.GetFormValue("items")
        if not items or isinstance(items, dict):
            values = items or self.GetFormValues()
            id = values.get("id")
            if not id:
                response.status = u"400 No id given"
                return {"error": "No id given", "result": []}
            item = self.context.GetObj(id)
            if not item:
                response.status = u"404 Not found"
                return {"error": "Not found", "result": []}
            subset = self.GetFormValue("subset") or "setItem"
            result, values, errors = SerializeItem(self, values, typename=item.configuration, formsubset=subset)
            if not result:
                response.status = u"400 Validation error"
                return {"error": str(errors), "result": []}
            result = item.Update(data=values, user=user)
            if not result:
                response.status = u"500 Storage error"
                return {"error": "Storage error", "result": []}
            return {"result": [item.id]}

        maxStoreItems = self.context.app.configuration.get("maxStoreItems") or DefaultMaxStoreItems
        if len(items) > maxStoreItems:
            response.status = u"413 Too many items"
            return {"error": u"Too many items.", "result": []}
        
        validated = []
        cnt = 1
        for values in items:
            id = values.get("id")
            if not id:
                response.status = u"400 No id given"
                return {"error": "No id given: Item "+str(cnt), "result": []}
            item = self.context.GetObj(id)
            if not item:
                response.status = u"404 Not found"
                return {"error": "Not found: Item "+str(cnt), "result": []}
            subset = self.GetFormValue("subset") or "setItem"
            result, values, errors = SerializeItem(self, values, typename=item.configuration, formsubset=subset)
            if not result:
                response.status = u"400 Validation error"
                return {"error": str(errors), "result": []}
            validated.append((values, item))
            cnt += 1
        
        stored = []
        error = []
        for values, item in validated:
            result = item.Update(data=values, user=user)
            if not result:
                error.append("500 Storage error")
            stored.append(item.id)
        return {"result": stored, "error": error}        

    
    def deleteItem(self):
        """
        Delete one or more items.
        
        Request parameter:
        
        - id: the items' id or a list of ids

        Returns json encoded result: {"result": ids of deleted items}
        """
        response = self.request.response

        ids = self.GetFormValue("id")
        if not ids:
            # set http response code (invalid request)
            response.status = u"400 Empty id"
            return {"error": u"Empty id", "result": []}

        if not isinstance(ids, list):
            try:
                ids = [int(ids)]
            except ValueError:
                ids=None
        if not ids:
            # set http response code (invalid request)
            response.status = u"400 Invalid id"
            return {"error": u"Invalid id.", "result": []}

        user = self.User()

        deleted = []
        error = []
        for id in ids:
            result = self.context.Delete(id, user=user)
            if result:
                deleted.append(id)

        return {"result": deleted, "error": error}
            

    def listItems(self):
        """
        Returns a list of batched items for a single or all types stored in the current container. 
        The result only includes the items ids. For a complete list of values use `subtree` or `searchItems`.
        
        Request parameter:
        
        - type (optional): the items type identifier 
        - sort (optional): sort field. a meta field or if type is not empty, one of the types fields. 
        - order (optional): '<','>'. order the result list based on values ascending '<' or descending '>'
        - size (optional): number of batched items. maximum is 100.
        - start (optional): start number of batched result sets.

        Returns json encoded result set: {"items":[item ids], "start":number}
        """
        response = self.request.response

        # process owner mode
        user = self.User()
                
        values = self.GetFormValues()
        type = values.get("type") or values.get("pool_type")

        try:
            start = ExtractJSValue(values, u"start", 0, "int")
        except ValueError:
            # set http response code (invalid request)
            response.status = u"400 Invalid parameter"
            return {"error": "Invalid parameter: start", "items": []}
        
        try:
            size = ExtractJSValue(values, u"size", 20, "int")
            maxBatchNumber = self.context.app.configuration.get("maxBatchNumber") or DefaultMaxBatchNumber
            if size > maxBatchNumber:
                size = maxBatchNumber
        except ValueError:
            # set http response code (invalid request)
            response.status = u"400 Invalid parameter"
            return {"error": "Invalid parameter: size", "items": []}

        order = values.get("order",None)
        if order == u"<":
            ascending = 1
        else:
            ascending = 0

        sort = values.get("sort",None)
        if not sort in [v["id"] for v in self.context.app.GetAllMetaFlds()]:
            if type:
                if not sort in [v["id"] for v in self.context.app.GetAllObjectFlds(type)]:
                    sort = None
        
        parameter = {"pool_unitref": self.context.id}
        result = self.context.dataroot.Select(type, parameter=parameter, fields=["id"], start=start, max=size, ascending=ascending, sort=sort)
        ids = [v[0] for v in result]
        result = {"items": ids, "start": start}
        return result

    
    def searchItems(self, profile=None):
        """
        Returns a list of batched items for a single or multiple keys. 
        Search profiles can be preconfigured and stored in the datastore application 
        configuration as (see `nive.search` for a full list of keyword options and 
        usage) ::
        
          {"profilename": {"type": "", "container": False,
                           "fields": [], "parameter": {}, "operators": {}}, "groups": []}
          
        If `type` is not empty this function uses `nive.search.SearchType`, if empty `nive.search.Search`.
        The data fields to be included in the result have to be assigned respectively. In other words
        if `type` is given the types data fields can be included in the result otherwise not.
        
        `container` determines whether to search in the current container or search all items in the tree.
        
        Request parameter:
        
        - profile: defines the search parameter profile and result fields. profiles are loaded 
          from the application configuration. 
        - sort (optional): sort field. a meta field or if type is not empty, one of the types fields.
        - order (optional): '<','>'. order the result list based on values ascending '<' or descending '>'
        - size (optional): number of batched items. 
        - start (optional): start number of batched result sets.

        Returns json encoded result set: {"items":[items], "start":number, "size":number, "total":number}
        """
        response = self.request.response
        if not profile:
            profiles = self.context.app.configuration.get("search")
            if not profiles:
                response.status = u"400 No search profiles found"
                return {"error": "No search profiles found", "items":[]}

            profilename = self.GetFormValue("profile") or self.context.app.configuration.get("defaultSearch")
            if not profilename:
                response.status = u"400 Empty search profile name"
                return {"error": "Empty search profile name", "items":[]}
            profile = profiles.get(profilename)
            if not profile:
                response.status = u"400 Unknown profile"
                return {"error": "Unknown profile", "items":[]}
        
        if profile.get("groups"):
            grps = profile.get("groups")
            user = self.User()
            #TODO local groups
            if not user or not user.InGroups(grps):
                raise HTTPForbidden, "Profile not allowed"


        values = self.GetFormValues()
        try:
            start = ExtractJSValue(values, u"start", 0, "int")
        except ValueError:
            # set http response code (invalid request)
            response.status = u"400 Invalid parameter"
            return {"error": "Invalid parameter: start", "items":[]}
        
        try:
            size = ExtractJSValue(values, u"size", 50, "int")
            maxBatchNumber = self.context.app.configuration.get("maxBatchNumber") or DefaultMaxBatchNumber
            if size > maxBatchNumber:
                size = maxBatchNumber
        except ValueError:
            # set http response code (invalid request)
            response.status = u"400 Invalid parameter"
            return {"error": "Invalid parameter: size", "items":[]}
        
        type = profile.get("type") or profile.get("pool_type")

        order = values.get("order",None)
        if order == u"<":
            ascending = 1
        elif order == u">":
            ascending = 0
        else:
            ascending = None

        sort = values.get("sort",None)
        if not sort in [v["id"] for v in self.context.app.GetAllMetaFlds()]:
            if type:
                if not sort in [v["id"] for v in self.context.app.GetAllObjectFlds(type)]:
                    sort = None
        
        if profile.get("container"):
            parameter = {"pool_unitref": self.context.id}
        else:
            parameter = {}
        parameter.update(profile.get("parameter",{}))
        operators = profile.get("operators")
        fields = profile.get("fields")
        kws = {}
        for key,value in profile.items():
            if key in ("pool_type", "parameter", "operators", "fields", "container"):
                continue
            kws[key] = value
        
        if start!=None and start!=0:
            # Search Functions use 0 based index, searchItems 1 based index
            kws["start"] = start-1
        if size!=None:
            kws["max"] = size
        if ascending!=None:
            kws["ascending"] = ascending
        if sort!=None:
            kws["sort"] = sort
        if type:
            result = self.context.dataroot.SearchType(type, parameter=parameter, fields=fields, operators=operators, **kws)
        else:
            result = self.context.dataroot.Search(parameter=parameter, fields=fields, operators=operators, **kws)
        values = {"items": result["items"], 
                  "start": result["start"]+1, 
                  "size": result["count"], 
                  "total": result["total"]}
        return values


    # called with item as context ------------------------------------------------------------

    def getContext(self):
        """
        Returns the item loaded as context by traversal. 
        
        returns json encoded data        
        """
        item = self.context
        return DeserializeItems(self, item)[0]
    
    
    def updateContext(self):
        """
        Stores the item loaded as context by traversal. Values are serialized and
        validated by 'setItem' form subset. If not set, all fields are allowed. 
        
        Request parameter:
        
        - <fields>: The items values.

        returns json encoded result       
        """
        response = self.request.response
        item = self.context
        subset = self.GetFormValue("subset") or "setItem"
        result, values, errors = SerializeItem(self, self.GetFormValues(), typename=self.context.configuration, formsubset=subset)
        if not result:
            response.status = u"400 Validation error"
            return {"error": str(errors)}
        result = self.context.Update(data=values, user=self.User())
        return {"result": result}
    

    # tree renderer ----------------------------------------------------------------------------------

    def _renderTree(self, context, profile):
        # cache field ids and types
        fields = {}
        for conf in context.app.GetAllObjectConfs():
            if conf.id in profile.fields:
                # custom list of fields in profile for type 
                fields[conf.id] = profile.fields[conf.id]
                continue
            # use type default
            render = conf.get("toJson")
            if not render:
                continue
            fields[conf.id] = render
        
        # prepare parameter
        parameter = {}
        if profile.get("parameter"):
            parameter.update(profile.parameter)
        if not "pool_type" in parameter:
            parameter["pool_type"] = fields.keys()
        
        # prepare types to descent in tree structure
        temp = profile.descent
        descenttypes = []
        for t in temp:
            resolved = ResolveName(t)
            if resolved:
                descenttypes.append(resolved)
            elif t in parameter["pool_type"]:
                descenttypes.append(t)
        operators={"pool_type":"IN"}
        if profile.get("operators"):
            operators.update(profile.operators)
            
        # lookup levels
        levels = profile.get("levels")
        if levels == None:
            levels = 10000

        def itemValues(item):
            iv = {}
            if item.IsRoot():
                return iv
            name = item.GetTypeID()
            if not name in fields:
                return iv
            for field in fields[item.GetTypeID()]:
                iv[field] = item.GetFld(field)
            return iv
        
        _c_descent = [[],[]]
        def descent(item):
            # cache values: first list = descent, second list = do not descent
            t = item.GetTypeID()
            if t in _c_descent[0]:
                return True
            if t in _c_descent[1]:
                return False
            
            for t in descenttypes:
                if isinstance(t, basestring):
                    if item.GetTypeID()==t:
                        if not t in _c_descent[0]:
                            _c_descent[0].append(t)
                        return True
                else:
                    if t.providedBy(item):
                        if not t in _c_descent[0]:
                            _c_descent[0].append(item.GetTypeID())
                        return True
            if not t in _c_descent[1]:
                _c_descent[1].append(item.GetTypeID())
            return False
            
        def itemSubtree(item, lev, includeSubtree=False):
            if profile.get("secure",True) and not has_permission("api-subtree", item, self.request):
                return {}
            current = itemValues(item)
            if (includeSubtree or descent(item)) and lev>0 and IContainer.providedBy(item):
                lev = lev - 1
                current["items"] = []
                items = item.GetObjs(parameter=parameter, operators=operators)
                for i in items:
                    current["items"].append(itemSubtree(i, lev))
            return current

        return itemSubtree(context, levels, includeSubtree=True)
        
    
    def subtree(self, profile=None):
        """
        Returns complex results like parts of a subtree including several levels. Contained items
        can be accessed through `items` in the result. `subtree` uses the items configuration
        `render` option to determine the result values rendered in a json document.
        If `render` is None the item will not be rendered at all.
        
        Parameter:

        - profile: name of the subtree profile to use for subtree rendering
        
        returns json document
        """
        if not profile:
            def returnError(error, status):
                data = json.dumps(error)
                return self.SendResponse(data, mime="application/json", raiseException=False, status=status)
            
            profiles = self.context.app.configuration.get("subtree")
            if not profiles:
                status = u"400 No subtree profile found"
                return returnError({"error": "No subtree profile found"}, status)

            profilename = self.GetFormValue("profile") or self.context.app.configuration.get("defaultSubtree")
            if not profilename:
                status = u"400 Empty subtree profile name"
                return returnError({"error": "Empty subtree profile name"}, status)
            profile = profiles.get(profilename)
            if not profile:
                status = u"400 Unknown profile"
                return returnError({"error": "Unknown profile"}, status)
        
        if isinstance(profile, dict):
            profile = Conf(**profile)

        values = self._renderTree(self.context, profile)
        data = JsonDataEncoder().encode(values)
        return self.SendResponse(data, mime="application/json", raiseException=False)
        

    def renderTmpl(self, template=None):
        """
        Renders the items template defined in the configuration (`ObjectConf.template`). The template
        will be called with a dictionary containing the item, request and view. See `pyramid.renderers`
        for possible template engines. 
        """
        values = {}
        values[u"item"] = self.context
        values[u"view"] = self
        values[u"request"] = self.request
        return self.DefaultTemplateRenderer(values, template)
    

    # form rendering ------------------------------------------------------------

    def newItemForm(self):
        """
        Renders and executes a web form based on the items configuration values. 
        Form form setup `pool_type` and `subset` are required. If subset is not 
        given it defaults to `newItem`. `subset` is the form identifier used in
        the items configuration as `form`. 
        
        For example ::

            collection1 = ObjectConf(
                id = "bookmark",
                name = u"Bookmarks",
                dbparam = "bookmarks",
                subtypes="*",
                data = (
                    FieldConf(id="link",     datatype="url",  size=500,   default=u"",  name=u"Link url"),
                    FieldConf(id="share",    datatype="bool", size=2,     default=False,name=u"Share link"),
                    FieldConf(id="comment",  datatype="text", size=50000, default=u"",  name=u"Comment"),
                ),
                forms = {
                    "newItem": {"fields": ("link", "share", "comment"), "ajax": True, assets: False},
                    "setItem": {"fields": ("link", "share", "comment"), "ajax": True, assets: True}
                },
                render = ("id", "link", "comment", "pool_changedby", "pool_change"),
                template = "nive_datastore.webapi.tests:bookmark.pt"
            )

        defines the newItem form subset as ::
        
            {"fields": ("link", "share", "comment"), "ajax": True}        
        
        The function returns rendered form html and result state as X-Result header:

        - X-Result: true or false
        - content: required html head includes like js and css files and rendered form html

        To get required assets in a seperate call use `?assets=only` as query parameter. This will
        return the required css and js assets for the specific form only.
        """
        headeronly = self.GetFormValue("assets")=="only"
        typename = self.GetFormValue("type") or self.GetFormValue("pool_type")
        if not typename:
            return {u"result": False, u"content": u"", u"head": u"", u"message": u"No type given"}
        typeconf = self.context.app.GetObjectConf(typename)
        subset = self.GetFormValue("subset") or "newItem"
        if not subset:
            return {u"result": False, u"content": u"", u"head": u"", u"message": u"No subset given"}
        form = ItemForm(view=self, loadFromType=typeconf)
        form.subsets = typeconf.forms
        subsetdef = form.subsets.get(subset)
        if subsetdef and not subsetdef.get("actions"):
            # add default new item actions
            subsetdef = subsetdef.copy()
            subsetdef.update(form.defaultNewItemAction)
            form.subsets[subset] = subsetdef

        form.Setup(subset=subset, addTypeField=True)
        form.use_ajax = True
        if headeronly:
            return self.SendResponse(data=form.HTMLHead(ignore=()))
        # process and render the form.
        result, data, action = form.Process(pool_type=typename)
        if IObject.providedBy(result):
            result = result.id
        head = u""
        if subsetdef.get("assets"):
            assets = subsetdef.get("assets")
            if not isinstance(assets, (tuple, list)):
                assets = ()
            head = form.HTMLHead(ignore=assets)
        return self.SendResponse(data=head+data, headers=(("XResult", str(result)),))
        #return {u"result": result, u"content": data, u"head": head}
        

    def updateForm(self):
        """
        Renders and executes a web form based on the items configuration values. 
        Form setup requires `subset` passed in the request. If subset is not 
        given it defaults to `setItem`. `subset` is the form identifier used in
        the items configuration as `form`. 
        
        For example ::

            collection1 = ObjectConf(
                id = "bookmark",
                name = u"Bookmarks",
                dbparam = "bookmarks",
                subtypes="*",
                data = (
                    FieldConf(id="link",     datatype="url",  size=500,   default=u"",  name=u"Link url"),
                    FieldConf(id="share",    datatype="bool", size=2,     default=False,name=u"Share link"),
                    FieldConf(id="comment",  datatype="text", size=50000, default=u"",  name=u"Comment"),
                ),
                forms = {
                    "newItem": {"fields": ("link", "share", "comment"), "ajax": True}, 
                    "setItem": {"fields": ("link", "share", "comment"), "ajax": True}
                },
                render = ("id", "link", "comment", "pool_changedby", "pool_change"),
                template = "nive_datastore.webapi.tests:bookmark.pt"
            )

        defines the setItem form subset as ::
        
            {"fields": ("link", "share", "comment"), "ajax": True}        
        
        The function returns rendered form html and result state as X-Result header:

        - X-Result: true or false
        - content: required html head includes like js and css files and rendered form html

        To get required assets in a seperate call use `?assets=only` as query parameter. This will
        return the required css and js assets for the specific form only.
        """
        headeronly = self.GetFormValue("assets")=="only"
        typeconf = self.context.configuration
        subset = self.GetFormValue("subset") or "newItem"
        if not subset:
            return self.SendResponse(data=u"No subset given", headers=(("XResult", "true"),))
        form = ItemForm(view=self, loadFromType=typeconf)
        form.subsets = copy.deepcopy(typeconf.forms)
        subsetdef = form.subsets.get(subset)
        if subsetdef and not subsetdef.get("actions"):
            # add default new item actions
            #subsetdef = subsetdef.copy()
            subsetdef.update(form.defaultSetItemAction)
            form.subsets[subset] = subsetdef

        form.Setup(subset=subset, addTypeField=True)
        form.use_ajax = True
        if headeronly:
            return self.SendResponse(data=form.HTMLHead(ignore=()))
        # process and render the form.
        result, data, action = form.Process(pool_type=typeconf.id)
        if IObject.providedBy(result):
            result = result.id
        head = u""
        if subsetdef.get("assets"):
            assets = subsetdef.get("assets")
            if not isinstance(assets, (tuple, list)):
                assets = ()
            head = form.HTMLHead(ignore=assets)
        return self.SendResponse(data=head+data, headers=(("XResult", str(result)),))
        #return {u"result": result, u"content": data, u"head": head}


    # workflow functions ------------------------------------------------------------

    def action(self):
        """
        Trigger a workflow action based on the contexts current state.
        
        Parameters: 
        - action: action name to be triggered
        - transition (optional): transition if multiple match action 
        - test (optional): if 'true' the action is not triggered but only
          tested if the current user is allowed to run the action in
          the current context.
          
        returns the action result and new state information
        
        {"result":true/false, "messages": [], "state": {}}
        """
        action = self.GetFormValue("action") or "newItem"
        if not action:
            return {"result": False, "messages": ["No action given"]}
        transition = self.GetFormValue("transition")
        test = self.GetFormValue("test")=="true"
        
        result = {"result": False, "messages": None}
        if test:
            result["result"] = self.context.WfAllow(action, self.user, transition)
            if result["result"]:
                result["messages"] = [u"Allowed"]
            else:
                result["messages"] = [u"Not allowed"]
        else:
            try:
                result["result"] = self.context.WfAction(action, self.user, transition)
                result["messages"] = [u"OK"]
                result["state"] = self.state()
            except WorkflowNotAllowed:
                result["result"] = False
                result["messages"] = [u"Not allowed"]
        return result
    

    def state(self):
        """
        Get the current contexts workflow state.
        
        returns state information
        
        - id: the state id
        - name: the state name
        - process: id and name of active workflow process
        - transistions: list of possible transitions for the current state
        
        each transition includes 

        - id: the id
        - name: the name
        - fromstate: the current state
        - tostate: new state after axcecution
        - actions: list of triggering actions for the transition
        
        """
        state = self.context.GetWfInfo(self.user)
        if not state:
            return {"result":False, "messages": [u"No workflow loaded for object"]}

        def _serI(info):
            return {"id":info.id, "name":info.name} 
        
        def _serT(transition):
            return {"id":transition.id, 
                    "name":transition.name, 
                    "fromstate":transition.fromstate,
                    "tostate":transition.tostate,
                    "actions":[_serI(a) for a in transition.actions]}
            
        
        return {"id": state["state"].id,
                "name": state["state"].name,
                "process": serI(state["process"]),
                "transitions": [_serT(t) for t in state["transitions"]],
                "result": True}


class ItemForm(ObjectForm):
    """
    Contains actions for object creation and updates.
    
    Supports sort form parameter *pepos*.
    """
    actions = [
        Conf(id=u"default",    method="StartFormRequest", name=u"Initialize", hidden=True,  css_class=u"",            html=u"", tag=u""),
        Conf(id=u"create",     method="CreateObj",        name=u"Create",     hidden=False, css_class=u"btn btn-primary",  html=u"", tag=u""),
        Conf(id=u"defaultEdit",method="StartObject",      name=u"Initialize", hidden=True,  css_class=u"",            html=u"", tag=u""),
        Conf(id=u"edit",       method="UpdateObj",        name=u"Save",       hidden=False, css_class=u"btn btn-primary",  html=u"", tag=u""),
        Conf(id=u"cancel",     method="Cancel",           name=u"Cancel",     hidden=False, css_class=u"buttonCancel",html=u"", tag=u"")
    ]
    defaultNewItemAction = {"actions": [u"create"],  "defaultAction": "default"}
    defaultSetItemAction = {"actions": [u"edit"],    "defaultAction": "defaultEdit"}
    subsets = None


