

from nive.definitions import ModuleConf

# Meta package definition to include item views and container views at once
#@nive_module
configuration = ModuleConf(
    id="webapi", 
    modules=(
        "nive_datastore.webapi.view.item_views", 
        "nive_datastore.webapi.view.container_views"
    )
)