# Copyright 2012-2014 Arndt Droullier, Nive GmbH. All rights reserved.
# Released under GPL3. See license.txt

import time
import logging
import json
import copy

from pyramid.httpexceptions import HTTPForbidden
from pyramid.security import has_permission
from pyramid.renderers import render

from nive.definitions import ViewModuleConf, ViewConf, Conf, ModuleConf
from nive.definitions import IObject, IContainer
from nive.definitions import ConfigurationError

from nive.workflow import WorkflowNotAllowed
from nive.views import BaseView
from nive.forms import Form, ObjectForm
from nive.security import Allow, Everyone, Authenticated, ALL_PERMISSIONS
from nive.helper import JsonDataEncoder
from nive.helper import ResolveName

from nive_datastore.i18n import _

# view module definition ------------------------------------------------------------------

_io = "nive.definitions.IObject"

#@nive_module
configuration = ViewModuleConf(
    id = "DatastoreAPIv1",
    name = _(u"Data storage api"),
    containment = "nive_datastore.app.IDataStorage",
    view = "nive_datastore.webapi.view.APIv1",
    context = "nive.definitions.IContainer",   # by default views are applied to all containers
    views = (
        # container views ---------------------------------------------------------------------------
        # these views only apply to container like objects and root

        # add a new item
        ViewConf(name="newItem",    attr="newItem",    permission="api-newItem",     renderer="json"),
        # list and search
        ViewConf(name="list",       attr="listItems",  permission="api-list",        renderer="json"),
        ViewConf(name="search",     attr="searchItems",permission="api-search",      renderer="json"),
        # rendering
        ViewConf(name="subtree",    attr="subtree",    permission="api-subtree",     renderer="string"),
        ViewConf(name="render",     attr="renderTmpl", permission="api-render"),
        # forms
        ViewConf(name="newItemForm",attr="newItemForm",permission="api-newItemForm", renderer="string"),

        # object views ---------------------------------------------------------------------------
        # read
        ViewConf(name="getItem",    attr="getItem",    permission="api-getItem",     renderer="json",   context=_io),
        # update
        ViewConf(name="setItem",    attr="setContext", permission="api-setItem",     renderer="json",   context=_io),
        # delete
        ViewConf(name="deleteItem", attr="deleteItem", permission="api-deleteItem",  renderer="json"),
        # rendering
        ViewConf(name="subtree",    attr="subtree",    permission="api-subtree",     renderer="string", context=_io),
        ViewConf(name="render",     attr="renderTmpl", permission="api-render",                         context=_io),
        # forms
        ViewConf(name="setItemForm",attr="setItemForm",permission="api-setItemForm", renderer="string", context=_io),
        # workflow
        ViewConf(name="action",     attr="action",     permission="api-action",      renderer="json",   context=_io),
        ViewConf(name="state",      attr="state",      permission="api-state",       renderer="json",   context=_io),
    ),
    acl = (
        (Allow, Everyone,       "api-getItem"),
        (Allow, Everyone,       "api-subtree"),
        (Allow, Everyone,       "api-render"),
        (Allow, Everyone,       "api-list"),
        (Allow, Everyone,       "api-search"),

        (Allow, Authenticated,  "api-newItem"),
        (Allow, Authenticated,  "api-newItemForm"),

        (Allow, "group:owner",  "api-setItem"),
        (Allow, "group:owner",  "api-setItemForm"),
        (Allow, "group:owner",  "api-deleteItem"),
        (Allow, "group:owner",  "api-action"),
        (Allow, "group:owner",  "api-state"),

        (Allow, "group:editor", ALL_PERMISSIONS),
        (Allow, "group:admin",  ALL_PERMISSIONS),
    )
)

#@nive_module
localstorage_views = ViewModuleConf(
    id = "DatastoreAPIv1-Localstorage",
    name = _(u"Data storage Localstorage api"),
    containment = "nive_datastore.app.IDataStorage",
    view = "nive_datastore.webapi.view.APIv1",
    context = "nive.definitions.IContainer",
    views = (
        # container views ----------------------------------------------------------------
        # these views add a localstorage like api to root objects. might be useful for
        # compatibility reasons

        # read contained item
        ViewConf(name="getItem",    attr="getItem",    permission="api-getItem",     renderer="json"),
        # update contents
        ViewConf(name="setItem",    attr="setItem",    permission="api-setItem",     renderer="json"),
        ViewConf(name="setItemForm",attr="setItemForm",permission="api-setItemForm", renderer="string"),
        # delete
        ViewConf(name="deleteItem", attr="deleteItem", permission="api-deleteItem",  renderer="json"),

    ),
)

DefaultMaxStoreItems = 50
DefaultMaxBatchNumber = 100
jsUndefined = (u"", u"null", u"undefined", None)

# internal data processing ------------------------------------------------------------

def DeserializeItems(view, items, fields):
    # Convert item objects to dicts before returning to the user
    if not isinstance(items, (list,tuple)):
        items = [items]

    ff = fields
    values = []
    for item in items:
        data = {}
        # loop result fields
        if isinstance(fields, dict):
            ff = fields.get(item.GetTypeID())
            if ff is None:
                ff = fields.get("default__")
        elif fields is None:
            ff = item.configuration.get("toJson", ff)

        if ff is None:
            raise ConfigurationError, "toJson fields are not defined"

        for field in ff:
            data[field] = item.GetFld(field)

        values.append(data)
    return values


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
        Returns one or multiple items. This function either returns the current item if called without
        parameter or if `id` is passed as request form value one or multiple child items.

        - id (optional): the items' id or a list of multiple items. leave empty to get the current
          item

        returns json encoded data, child items are wapped in a list

        The data fields included in the result are rendered based on customized view options or the types'
        default settings ``toJson`` ::

        1) Customized `getItem` view ::

            bookmark = ViewConf(
                name="read-bookmark",
                attr="getItem",
                ...
                settings={"toJson": ("link", "share", "comment")}
            )

        To define the returned fields of multiple object types use a dict instead of a tuple and use the type id
        as key ::

            {"toJson": {"bookmark": ("link", "share", "comment")}}

        To mix defaults for multiple types and specific fields for other types use `default__` as key.

        2) The types' ObjectConf.forms settings for `newItem`  ::

            collection1 = ObjectConf(
                id = "bookmark",
                ...
                toJson = ("link", "share", "comment"),
            )

        In both cases each returned json bookmark item contains the values for link, share and comment.
        """
        fields = None
        viewconf = self.GetViewConf()
        if viewconf and viewconf.get("settings"):
            fields = viewconf.settings.get("toJson")

        # lookup the id in the current form submission. if not none try to load and update the
        # child with id=id
        id = self.GetFormValue("id")
        if id is None:
            # return only the single item and
            item = self.context
            return DeserializeItems(self, item, fields)[0]

        if not isinstance(id, (list,tuple)):
            try:
                id = [int(id)]
            except (ValueError, TypeError):
                # set http response code (invalid request)
                self.request.response.status = u"400 Invalid id"
                return {"error": u"Invalid id"}

        if isinstance(id, (list, tuple)) and len(id)==0:
            # set http response code (invalid request)
            self.request.response.status = u"400 Empty id"
            return {"error": u"Empty id"}

        items = []
        for obj in self.context.GetObjsBatch(id):
            if not self.Allowed(obj, "api-getItem"):
                # fails silently in list mode
                continue
            items.append(obj)
        # turn into json
        return DeserializeItems(self, items, fields)


    def newItem(self):
        """
        Creates a single item or a set of items as batch. Values are serialized and
        validated by the 'newItem' form subset.

        Request parameter:

        - type: the new type to be created. Must be set for each item.
        - <fields>: A single item can be passed directly as form values without wraping it as `items`
        - items (optional): One or multiple items to be stored. Multiple items have to be passed as
          array. Maximum number of 20 items allowed.

        Returns json encoded result: {"result": list of new item ids}

        Validation configuration lookup order :

        1) Customized `newItem` view ::

            bookmark = ViewConf(
                name="add-bookmark",
                attr="newItem",
                ...
                settings={"form": {"fields": ("link", "share", "comment")}
                          "type": "bookmark"}
            )

        2) The types' ObjectConf.forms settings for `newItem`  ::

            collection1 = ObjectConf(
                id = "bookmark",
                ...
                forms = {
                    "newItem": {"fields": ("link", "share", "comment"), "use_ajax": True},
                    "setItem": {"fields": ("link", "share", "comment"), "use_ajax": True}
                },
                ...
            )

        defines the `newItem` form in both cases with 3 form fields ::

            "link", "share", "comment"

        If you are using the default `newItem` view you have to pass the type id to be
        created by the function as form parameter ``type=bookmark``. If you are using a customized
        view the type can be part of the views options slot ``settings={"type": "bookmark"}``.
        """
        # lookup typename and subset
        typename = subset = ""
        # look up the new type and validation fields in custom view definition
        viewconf = self.GetViewConf()
        if viewconf and viewconf.get("settings"):
            typename = viewconf.settings.get("type")
            subset = viewconf.settings.get("subset")
        if not subset:
            subset = self.GetFormValue("subset") or "newItem"

        response = self.request.response
        items = self.GetFormValue("items")
        if not items:
            # create a single item
            values = self.GetFormValues()
            if not typename:
                typename = values.get("type") or values.get("pool_type")
                if not typename:
                    response.status = u"400 No type given"
                    return {"error": "No type given", "result":[]}
            typeconf = self.context.app.GetObjectConf(typename)
            if not typeconf:
                response.status = u"400 Unknown type"
                return {"error": "Unknown type", "result":[]}

            form, subset = self._loadForm(self.context, subset, typeconf, viewconf, "newItem")
            form.Setup(subset=subset)
            result, values, errors = form.ValidateSchema(values)
            if not result:
                response.status = u"400 Validation error"
                return {"error": str(errors), "result":[]}

            #values = SerializeItem(self, values, typeconf)
            item = self.context.Create(typename, data=values, user=self.User())
            if not item:
                response.status = u"400 Validation error"
                return {"error": "Validation error", "result":[]}
            return {"result": [item.id]}

        maxStoreItems = self.context.app.configuration.get("maxStoreItems") or DefaultMaxStoreItems
        if len(items) > maxStoreItems:
            response.status = u"413 Too many items"
            return {"error": u"Too many items.", "result":[]}

        validated = []
        errors = []
        cnt = 0
        for values in items:
            cnt += 1
            tn = typename or values.get("type") or values.get("pool_type")
            if not tn:
                errors.append("No type given: Item number "+str(cnt))
                continue

            typeconf = self.context.app.GetObjectConf(tn)
            if not typeconf:
                errors.append("Unknown type")
                continue

            form, subset = self._loadForm(self.context, subset, typeconf, viewconf, "newItem")
            form.Setup(subset=subset)
            result, values, err = form.ValidateSchema(values)
            if not result:
                if isinstance(err, list):
                    errors.extend(err)
                elif err is not None:
                    errors.append(str(err))
                continue

            item = self.context.Create(tn, data=values, user=self.User())
            if item:
                validated.append(item.id)

        return {"result": validated, "error": errors}


    def setItem(self):
        """
        Store a single item or a set of items as batch. Values are serialized and
        validated by 'setItem' form subset. If not set, all fields are allowed. 
        
        Request parameter:
        
        - <fields>: A single item can be passed as form values.
        - items (optional): One or multiple items to be stored. Multiple items have to be passed as 
          array. Maximum number of 20 items allowed.
          
        Returns json encoded result: {"result": list of stored item ids}

        Validation configuration lookup order :

        1) Customized `setItem` view ::

            bookmark = ViewConf(
                name="update-bookmark",
                attr="setItem",
                ...
                settings={"form": {"fields": ("link", "share", "comment")}
            )

        2) The types' ObjectConf.forms settings for `setItem`  ::

            collection1 = ObjectConf(
                id = "bookmark",
                ...
                forms = {
                    "newItem": {"fields": ("link", "share", "comment"), "use_ajax": True},
                    "setItem": {"fields": ("link", "share", "comment"), "use_ajax": True}
                },
                ...
            )

        defines the `setItem` form in both cases with 3 form fields ::

            "link", "share", "comment"

        """
        # lookup subset
        subset = ""
        # look up the new type in custom view definition
        viewconf = self.GetViewConf()
        if viewconf and viewconf.get("settings"):
            subset = viewconf.settings.get("subset")
        if not subset:
            subset = self.GetFormValue("subset") or "setItem"

        items = self.GetFormValue("items")
        if items is None:
            # lookup id in form values
            id = self.GetFormValue("id")
            if id:
                setObject = self.context.obj(id)
                if not setObject:
                    self.request.response.status = u"404 Not found"
                    return {"error": u"Not found", "result": []}
                if not self.Allowed("api-setItem", setObject):
                    self.request.response.status = u"403 Not allowed"
                    return {"error": u"Not allowed", "result": []}
            else:
                # store data in current context itself
                setObject = self.context

            typeconf = setObject.configuration
            form, subset = self._loadForm(setObject, subset, typeconf, viewconf, "setItem")
            form.Setup(subset=subset)
            result, values, errors = form.ValidateSchema(self.GetFormValues())
            if not result:
                self.request.response.status = u"400 Validation error"
                return {"error": errors, "result": []}

            result = setObject.Update(data=values, user=self.User())
            return {"result": result}

        response = self.request.response
        user = self.User()

        if not items or isinstance(items, dict):
            response.status = u"400 Validation error"
            return {"error": u"items: Not a list", "result": []}

        maxStoreItems = self.context.app.configuration.get("maxStoreItems") or DefaultMaxStoreItems
        if len(items) > maxStoreItems:
            response.status = u"413 Too many items"
            return {"error": u"Too many items.", "result": []}
        
        validated = []
        errors = []
        cnt = 0
        for values in items:
            cnt += 1
            id = values.get("id")
            if not id:
                errors.append("No id given: Item number "+str(cnt))
                continue
            item = self.context.GetObj(id)
            if not item:
                errors.append("Not found: Item id "+str(id))
                continue

            typeconf = item.configuration
            form, subset = self._loadForm(item, subset, typeconf, viewconf, "setItem")
            form.Setup(subset=subset)
            result, values, err = form.ValidateSchema(values)
            if not result:
                if isinstance(err, list):
                    errors.extend(err)
                else:
                    errors.append(str(err))
                continue

            if not self.Allowed("api-setItem", item):
                errors.append("Not allowed: Item id "+str(id))
            result = item.Update(data=values, user=user)
            if result:
                validated.append(id)

        return {"result": validated, "error": errors}

    
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
        for obj in self.context.GetObjsBatch(ids):
            if not self.Allowed("api-delete", obj):
                continue
            id = obj.id
            result = self.context.Delete(obj, user=user)
            del obj
            if result:
                deleted.append(id)

        return {"result": deleted}
            

    # list and search ----------------------------------------------------------------------------------

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

            # search profile values
            {
                "type": "profile",
                "container": True,
                "fields": ["id", "name", "slogan"],
                "parameter": {"public": True, "pool_state": True},
                "dynamic": {"start": 0},
                "operators": {},
                "sort": "pool_change",
                "order": "<",
                "size": 30,
                "start": 0,
                "advanced": {}
            }

        The system provides two options to configure search profiles. The first one uses the application configuration ::

            appconf.search = {
                # the default profile if no name is given
                "default": {
                    # profile values go here
                },
                "extended": {
                    # profile values go here
                },
            }

        To use the `extended` profile pass the profiles name as query parameter
        e.g. `http://myapp.com/storage/searchItems?profile=extended`. This way searchItems will always return json.

        The second option is to add a custom view based on `searchItems`. This way you can add a custom renderer,
        view name and permissions::

            ViewConf(
                name="list",
                attr="searchItems",
                context="nive_datastore.root.root",
                permission="view",
                renderer="myapp:templates/list.pt",
                settings={
                    # profile values go here
                }
            )

        See `application configuration` how to include the view.

        Options:

        If ``type`` is not empty this function uses `nive.search.SearchType`, if empty `nive.search.Search`.
        The data fields to be included in the result have to be assigned respectively. In other words
        if `type` is given the types data fields can be included in the result, otherwise not.

        ``container`` determines whether to search in the current container or search all items in the tree.

        ``fields`` a list of data fields to be included in the result set. See `nive.search`.

        ``parameter`` is a dictionary or callable of fixed query parameters used in the select statement. These values cannot
        be changed through request form values. The callback takes two parameters `context` and `request` and should return
        a dictionary. E.g. ::

            def makeParam(context, request):
                return {"id": context.id}

            {   ...
                # adds the contexts file as parameter
                "parameter": makeParam,
                ...
            }

        or as inline function definition ::

            {   ...
                # adds the contexts file as parameter
                "parameter": lambda context, request, view: {"id": context.id},
                ...
            }



        ``dynamic`` these values values are extracted from the request. The values listed here are the defaults
        if not found in the request. The `dynamic` values are mixed with the fixed parameters and passed to the query.

        ``operators`` fieldname:operator entries used for search conditions. See `nive.search`.

        ``sort`` is a field name and used to sort the result.
        ``order`` either '<','>' or empty. Orders the result list based on values ascending '<' or descending '>'
        ``size`` number of batched items.
        ``start`` start number of batched result sets.

        ``advanced`` search options like group restraints. See `nive.search` for details.

        Result:

        The return value is based on the linked renderer. By default the result is returned as json
        encoded result set: ::

            `{"items":[items], "start":number, "size":number, "total":number}`

        """
        response = self.request.response
        if not profile:
            # look up the profile in two places
            # 1) in custom view definition
            viewconf = self.GetViewConf()
            if viewconf and viewconf.get("settings"):
                profile = viewconf.settings
            else:
                # 2) in app.configuration.search
                profiles = self.context.app.configuration.get("search")
                if not profiles:
                    response.status = u"400 No search profiles found"
                    return {"error": "No search profiles found", "items":[]}

                profilename = self.GetFormValue("profile", u"default")
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
                #TODO check local groups
                if not user or not user.InGroups(grps):
                    raise HTTPForbidden, "Profile not allowed"

        # get dynamic values
        values = {}
        web = self.GetFormValues()
        dynamic = profile.get("dynamic", {})
        if dynamic:
            for dynfield, dynvalue in dynamic.items():
                values[dynfield] = web.get(dynfield, dynvalue)

        if u"start" in dynamic:
            try:
                start = ExtractJSValue(values, u"start", 0, "int")
            except ValueError:
                # set http response code (invalid request)
                response.status = u"400 Invalid parameter"
                return {"error": "Invalid parameter: start", "items":[]}
            del values[u"start"]
        else:
            start = profile.get("start",0)

        if u"size" in dynamic:
            try:
                size = ExtractJSValue(values, u"size", 50, "int")
                maxBatchNumber = self.context.app.configuration.get("maxBatchNumber") or DefaultMaxBatchNumber
                if size > maxBatchNumber:
                    size = maxBatchNumber
            except ValueError:
                # set http response code (invalid request)
                response.status = u"400 Invalid parameter"
                return {"error": "Invalid parameter: size", "items":[]}
            del values[u"size"]
        else:
            size = profile.get("size", self.context.app.configuration.get("maxBatchNumber") or DefaultMaxBatchNumber)

        if u"order" in dynamic:
            order = values.get("order",None)
            del values[u"order"]
        else:
            order = profile.get("order")
        if order == u"<":
            ascending = 1
        elif order == u">":
            ascending = 0
        else:
            ascending = None

        # fixed values
        typename = profile.get("type") or profile.get("pool_type")

        if u"sort" in dynamic:
            sort = values.get("sort",None)
            if not sort in [v["id"] for v in self.context.app.GetAllMetaFlds()]:
                if typename:
                    if not sort in [v["id"] for v in self.context.app.GetAllObjectFlds(typename)]:
                        sort = None
            del values[u"sort"]
        else:
            sort = profile.get("sort")

        # get the configured parameters. if it is a callable call it with current
        # request and context.
        p = profile.get("parameter", None)
        if callable(p):
            p = apply(p, (self.context, self.request))
        if p:
            values.update(p)

        if profile.get("container"):
            values["pool_unitref"] = self.context.id
        parameter = values
        operators = profile.get("operators")
        fields = profile.get("fields")

        # prepare keywords
        kws = {}
        if profile.get("advanced"):
            kws.update(profile["advanced"])

        if start is not None and start!=0:
            # Search Functions use 0 based index, searchItems 1 based index
            kws["start"] = start-1
        if size is not None:
            kws["max"] = size
        if ascending is not None:
            kws["ascending"] = ascending
        if sort is not None:
            kws["sort"] = sort

        # run the query and handle the result
        if typename:
            result = self.context.dataroot.SearchType(typename, parameter=parameter, fields=fields, operators=operators, **kws)
        else:
            result = self.context.dataroot.Search(parameter=parameter, fields=fields, operators=operators, **kws)
        values = {"items": result["items"],
                  "start": result["start"]+1,
                  "size": result["count"],
                  "total": result["total"]}
        return values


    # tree renderer ----------------------------------------------------------------------------------

    def subtree(self, profile=None):
        """
        Returns complex results like parts of a subtree including several levels. Contained items
        can be accessed through `items` in the result. `subtree` uses the items configuration
        `render` option to determine the result values rendered in a json document.
        If `render` is None the item will not be rendered at all.

            # subtree profile values
            {
                "levels": 0,
                "descent": (IContainer,),
                "toJson": {"bookmark": ("comment", share")},
                "parameter": {"pool_state": 1}
            }

        The system provides two options to configure subtree profiles. The first one uses the application configuration ::

            appconf.subtree = {
                # the default profile if no name is given
                "default": {
                    # profile values go here
                },
                "extended": {
                    # profile values go here
                },
            }

        To use the `extended` profile pass the profiles name as query parameter
        e.g. `http://myapp.com/storage/subtree?profile=extended`. In this case `subtree()` will always return json.

        The second option is to add a custom view based on `subtree`. This way you can add a custom renderer,
        view name and permissions::

            ViewConf(
                name="tree",
                attr="subtree",
                context="nive_datastore.root.root",
                permission="view",
                renderer="myapp:templates/tree.pt",
                settings={
                    # profile values go here
                }
            )

        See `application configuration` how to include the view.

        To define the returned fields of multiple object types use a dict and use the type id
        as key ::

            {"toJson": {"bookmark": ("link", "share", "comment")}}

        Options:

        ``levels`` (default 0) the number of levels to include, 0=include all

        ``descent`` e.g. `(IContainer,)` item types or interfaces to descent into subtree
        ``toJson`` dict or tuple: result values. If empty uses the types `toJson` defaults
        ``parameter`` query parameter for result selection e.g. `{"pool_state": 1}`

        Result:

        The return value is based on the linked renderer. By default the result is returned as json
        encoded result set: ::

            `{"items":{"items": {<values>}, <values>}, <values>}`

        """
        if not profile:
            # look up the profile in two places
            # 1) in custom view definition
            viewconf = self.GetViewConf()
            if viewconf and viewconf.get("settings"):
                profile = viewconf.settings
            else:
                # 2) in app.configuration.search
                def returnError(error, status):
                    #data = json.dumps(error)
                    #return self.SendResponse(data, mime="application/json", raiseException=False, status=status)
                    self.request.response.status = status
                    return error

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
        return values


    def _renderTree(self, context, profile):
        # cache field ids and types
        fields = {}
        for conf in context.app.GetAllObjectConfs():
            if isinstance(profile.get("toJson"), dict) and conf.id in profile.get("toJson"):
                # custom list of fields in profile for type 
                fields[conf.id] = profile.get("toJson")[conf.id]
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
        temp = profile.get("descent",[])
        descenttypes = []
        for t in temp:
            resolved = ResolveName(t)
            if resolved:
                descenttypes.append(resolved)
            elif t in parameter["pool_type"]:
                descenttypes.append(t)
        if "pool_type" in parameter and isinstance(parameter["pool_type"], (list,tuple)):
            operators={"pool_type":"IN"}
        else:
            operators = {}
        if profile.get("operators"):
            operators.update(profile.operators)
            
        # lookup levels
        levels = profile.get("levels")
        if levels is None:
            levels = 10000

        def itemValues(item):
            iv = {}
            if item.IsRoot():
                return iv
            name = item.GetTypeID()
            if profile.get("addContext"):
                iv["context"] = item
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
                lev -= 1
                current["items"] = []
                items = item.GetObjs(parameter=parameter, operators=operators)
                for i in items:
                    current["items"].append(itemSubtree(i, lev))
            return current

        return itemSubtree(context, levels, includeSubtree=True)
        
    
    # form rendering ------------------------------------------------------------

    def newItemForm(self):
        """
        Renders and executes a web form based on the items configuration values. 
        Form form setup `pool_type` and `subset` are required. If subset is not 
        given it defaults to `newItem`. `subset` is the form identifier used in
        the items configuration as `form`. 

        Form configuration lookup order :

        1) Customized `newItemForm` view ::

            bookmark = ViewConf(
                name="add-bookmark",
                attr="newItemForm",
                ...
                settings={"form": {"fields": ("link", "share", "comment"), "use_ajax": True}
                          "type": "bookmark"}
            )

        2) The types' ObjectConf.forms settings for `newItem`  ::

            collection1 = ObjectConf(
                id = "bookmark",
                ...
                forms = {
                    "newItem": {"fields": ("link", "share", "comment"), "use_ajax": True},
                    "setItem": {"fields": ("link", "share", "comment"), "use_ajax": True}
                },
                ...
            )

        defines the `newItem` form in both cases with 3 form fields and to use ajax submissions ::
        
            {"fields": ("link", "share", "comment"), "use_ajax": True}

        If you are using the default `newItemForm` view you have to pass the type id to be
        created by the function as form parameter ``type=bookmark``. If you are using a customized
        view the type can be part of the views options slot ``settings={"type": "bookmark"}``.
        
        The function returns rendered form html and the result as X-Result header:

        - X-Result: true or false
        - content: required html head includes like js and css files and rendered form html

        To get required assets in a seperate call use `?assets=only` as query parameter. This will
        return the required css and js assets for the specific form only.
        """
        typename = subset = ""
        # look up the new type in custom view definition
        viewconf = self.GetViewConf()
        if viewconf and viewconf.get("settings"):
            typename = viewconf.settings.get("type")
            subset = viewconf.settings.get("form")
        else:
            if not subset:
                subset = self.GetFormValue("subset") or "newItem"
                if not subset:
                    self.AddHeader("X-Result", "false")
                    return {"content": u"No subset"}

            if not typename:
                typename = self.GetFormValue("type") or self.GetFormValue("pool_type")
                if not typename:
                    self.AddHeader("X-Result", "false")
                    return {"content": u"Type is empty"}

        typeconf = self.context.app.GetObjectConf(typename)

        # set up the form
        form, subset = self._loadForm(self.context, subset, typeconf, viewconf, "newItem", ItemForm.defaultNewItemAction)
        form.Setup(subset=subset, addTypeField=True)

        if self.GetFormValue("assets")=="only":
            self.AddHeader("X-Result", "true")
            return {"content": form.HTMLHead(ignore=[a[0] for a in self.configuration.assets])}

        # process and render the form.
        result, data, action = form.Process(pool_type=typename)
        if IObject.providedBy(result):
            result = result.id

        self.AddHeader("X-Result", str(result).lower())
        subsetdef = form.subsets.get(subset)
        if subsetdef.get("assets"):
            # if assets are enabled add required js+css for form except those defined
            # in the view modules asset list
            head = form.HTMLHead(ignore=[a[0] for a in self.configuration.assets])
            return {"content": head+data}

        return {"content": data}


    def setItemForm(self):
        """
        Renders and executes a web form based on the items configuration values. 
        Form setup requires `subset` passed in the request. If subset is not 
        given it defaults to `setItem`. `subset` is the form identifier used in
        the items configuration as `form`.

        Form configuration lookup order :

        1) Customized `setItemForm` view ::

            bookmark = ViewConf(
                name="update-bookmark",
                attr="setItemForm",
                ...
                settings={"form": {"fields": ("link", "share", "comment"), "use_ajax": True}}
            )

        2) The types' ObjectConf.forms settings for `setItem`  ::

            collection1 = ObjectConf(
                id = "bookmark",
                ...
                forms = {
                    "newItem": {"fields": ("link", "share", "comment"), "use_ajax": True},
                    "setItem": {"fields": ("link", "share", "comment"), "use_ajax": True}
                },
                ...
            )

        defines the `setItem` form in both cases with 3 form fields and to use ajax submissions ::
        
            {"fields": ("link", "share", "comment"), "use_ajax": True}
        
        The function returns rendered form html and result as X-Result header:

        - X-Result: true or false
        - content: required html head includes like js and css files and rendered form html

        To get required assets in a seperate call use `?assets=only` as query parameter. This will
        return the required css and js assets for the specific form only.
        """
        subset = ""
        # look up the new type in custom view definition
        viewconf = self.GetViewConf()
        if viewconf and viewconf.get("settings"):
            subset = viewconf.settings.get("form")
        else:
            subset = self.GetFormValue("subset") or "setItem"

        setObject = self.context
        typeconf = setObject.configuration

        # set up the form
        form, subset = self._loadForm(setObject, subset, typeconf, viewconf, "setItem", ItemForm.defaultSetItemAction)
        form.Setup(subset=subset)

        if self.GetFormValue("assets")=="only":
            #return self.SendResponse(data=form.HTMLHead(ignore=()))
            self.AddHeader("X-Result", "true")
            return {"content": form.HTMLHead(ignore=())}

        # process and render the form.
        result, data, action = form.Process()
        if IObject.providedBy(result):
            result = result.id

        self.AddHeader("X-Result", str(result).lower())
        subsetdef = form.subsets.get(subset)
        if subsetdef.get("assets"):
            # if assets are enabled add required js+css for form except those defined
            # in the view modules asset list
            head = form.HTMLHead(ignore=[a[0] for a in self.configuration.assets])
            return {"content": head+data}

        return {"content": data}


    def _loadForm(self, forContext, subset, typeconf, viewconf, defaultsubset, defaultaction=None):
        # form rendering settings
        form = ItemForm(view=self, context=forContext, loadFromType=typeconf)

        # load subset
        if subset is None:
            subset = defaultsubset
        if isinstance(subset, basestring):
            # the subset is referenced as string -> look it up in typeconf.forms
            form.subsets = typeconf.forms
        else:
            form.subsets = {defaultsubset: subset}
            subset = defaultsubset

        # set up action
        if not "actions" in form.subsets[subset] and defaultaction:
            form.subsets[subset].update(defaultaction)

        # customize form widget. values are applied to form.widget
        form.widget.item_template = "field_onecolumn"
        form.widget.action_template = "form_actions_onecolumn"
        form.use_ajax = True
        form.action = self.request.url
        vm = self.viewModule
        if vm:
            formsettings = self.viewModule.get("form")
            if isinstance(formsettings, dict):
                form.ApplyOptions(formsettings)
        return form, subset


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
            return {"result": False, "messages": ["Action is empty"]}
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
        Get the current contexts' workflow state.
        
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
                "process": _serI(state["process"]),
                "transitions": [_serT(t) for t in state["transitions"]],
                "result": True}


    def renderTmpl(self, template=None):
        """
        Renders the items template defined in the configuration (`ObjectConf.template`). The template
        will be called with a dictionary containing the item, request and view. See `pyramid.renderers`
        for possible template engines. ::

            collection1 = ObjectConf(
                id = "bookmark",
                template="bookmark.pt",
                ...
            )


        For custom views you can use the template renderer as part of the view configuration directly and
        istead of this function `renderTmpl` use ``attr=tmpl``.

            bookmark = ViewConf(
                name="render-me",
                attr="tmpl",
                ...
            )

        """
        values = {}
        values[u"item"] = self.context
        values[u"view"] = self
        values[u"request"] = self.request
        return self.DefaultTemplateRenderer(values, template)


    def tmpl(self):
        """
        For view based template rendering. An instance of the view class is automatically
        passed to the template as `view`. The current context can be accessed as `context`.

        Configuration example ::

            bookmark = ViewConf(
                name="render-me",
                attr="tmpl",
                renderer="myapp:templates/bookmark.pt",
                ...
            )

        """
        return {}


    # list rendering ------------------------------------------------------------

    def renderListItem(self, values, typename=None, template=None):
        """
        This function renders data records (non object) returned by Select or Search
        functions with the object configuration defined `listing` renderer.

        Unlike the object renderer this function does not require full object loads like
        `renderTmpl` but works with simple dictionary lists.

        Make sure all values required to render the template are passed to `renderListItems`
        i.e. included as result in the select functions.

        E.g.

        Configuration ::

            ObjectConf(id="article", listing="article-list.pt", ...)

        Template ::

            <h2>${name}</h2>
            <p>${text}</p>
            <a href="${pool_filename}">read all</a>

        Usage ::

            <div tal:content="structure view.renderListItem(values, 'article')"
                 class="col-lg-12"></div>

        :values:
        :typename:
        :template:
        """
        if template:
            values["view"] = self
            return render(template, values, request=self.request)
        typename = typename or values.get("type")
        if not typename:
            return u"-no type-"
        if not hasattr(self, "_c_listing_"+typename):
            typeconf = self.context.app.GetObjectConf(typename)
            tmpl = typeconf.get("listing")
            setattr(self, "_c_listing_"+typename, tmpl)
        else:
            tmpl = getattr(self, "_c_listing_"+typename)
        values["view"] = self
        return render(tmpl, values, request=self.request)




class ItemForm(ObjectForm):
    """
    Contains actions for object creation and updates.
    
    Supports sort form parameter *pepos*.
    """
    actions = [
        Conf(id=u"default",    method="StartFormRequest", name=u"Initialize", hidden=True,  css_class=u""),
        Conf(id=u"create",     method="CreateObj",        name=u"Submit",     hidden=False, css_class=u"btn btn-primary"),
        Conf(id=u"defaultEdit",method="StartObject",      name=u"Initialize", hidden=True,  css_class=u""),
        Conf(id=u"edit",       method="UpdateObj",        name=u"Save",       hidden=False, css_class=u"btn btn-primary"),
        Conf(id=u"cancel",     method="Cancel",   name=u"Cancel and discard", hidden=False, css_class=u"btn btn-default")
    ]
    defaultNewItemAction = {"actions": [u"create"],  "defaultAction": "default"}
    defaultSetItemAction = {"actions": [u"edit"],    "defaultAction": "defaultEdit"}
    subsets = None



"""
A string renderer extension to support dictionaries for better compatibility with template renderer.
Return a single value 'content' to the renderer and the content will be returned as
the responses body. ::

    # view result
    {"content": "<h1>The response!</h1>"}
    # is returned as
    "<h1>The response!</h1>"

To activate the renderer add 'stringRendererConf' to the applications modules. ::

    configuration.modules.append("nive_datastore.webapi.view.stringRendererConf")

"""

def string_renderer_factory(info):
    def _render(value, system):
        if isinstance(value, dict) and "content" in value:
            value = value["content"]
        elif not isinstance(value, basestring):
            value = str(value)
        request = system.get('request')
        if request is not None:
            response = request.response
            ct = response.content_type
            if ct == response.default_content_type:
                response.content_type = 'text/plain'
        return value
    return _render

def SetupStringRenderer(app, pyramidConfig):
    if pyramidConfig:
        # pyramidConfig is None in tests
        pyramidConfig.add_renderer('string', string_renderer_factory)

stringRendererConf = ModuleConf(
    events = (Conf(event="startRegistration", callback=SetupStringRenderer),),
)

