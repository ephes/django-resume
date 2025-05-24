from typing import TYPE_CHECKING, Union

if TYPE_CHECKING:
    from .base import Plugin

PluginStore = dict[str, "Plugin"]


class PluginRegistry:
    """
    A registry for plugins. This is used to register and unregister plugins.
    """

    def __init__(self) -> None:
        self.plugins: PluginStore = {}
        self.db_plugins: PluginStore = {}  # dynamic plugins from the database

    @staticmethod
    def _register(store: PluginStore, plugin_class: type["Plugin"]) -> None:
        """
        Register a plugin class. This will instantiate the plugin and add it to the registry.

        It will also add the plugin's inline URLs to the urlpatterns list.
        """
        plugin = plugin_class()
        store[plugin.name] = plugin
        from ..urls import urlpatterns

        urlpatterns.extend(plugin.get_inline_urls())

    def register(self, plugin_class: type["Plugin"]) -> None:
        self._register(self.plugins, plugin_class)

    def register_db_plugin(self, plugin_class: type["Plugin"]) -> None:
        self._register(self.db_plugins, plugin_class)

    def register_plugin_list(self, plugin_classes: list) -> None:
        for plugin_class in plugin_classes:
            self.register(plugin_class)

    def register_db_plugin_list(self, plugin_classes: list) -> None:
        for plugin_class in plugin_classes:
            self.register_db_plugin(plugin_class)

    def unregister(self, plugin_class: type["Plugin"]) -> None:
        del self.plugins[plugin_class.name]

    def get_plugin(self, name) -> Union["Plugin", None]:
        return self.plugins.get(name)

    def get_all_plugins(self) -> list["Plugin"]:
        return list(self.plugins.values()) + list(self.db_plugins.values())

    def get_all_db_plugins(self) -> list["Plugin"]:
        return list(self.db_plugins.values())

    def clear_db_plugins(self) -> None:
        """
        Clear all DB plugins from the registry and remove their URLs.
        """
        # Remove URLs for DB plugins
        from ..urls import urlpatterns

        # Get all inline URLs from current DB plugins
        urls_to_remove = []
        for plugin in self.db_plugins.values():
            urls_to_remove.extend(plugin.get_inline_urls())

        # Remove the URLs from urlpatterns
        for url_to_remove in urls_to_remove:
            if url_to_remove in urlpatterns:
                urlpatterns.remove(url_to_remove)

        # Clear Django's URL resolver cache
        from django.urls import clear_url_caches

        clear_url_caches()

        # Clear the DB plugins store
        self.db_plugins.clear()

    def reload_db_plugins(self) -> None:
        """
        Reload all active DB plugins from the database.
        """
        # Clear existing DB plugins
        self.clear_db_plugins()

        # Reload from database
        from ..models import Plugin

        Plugin.objects.register_plugin_models()

        # Clear URL caches again after adding new URLs
        from django.urls import clear_url_caches

        clear_url_caches()


# The global plugin registry - this is a singleton since module level variables are shared across the application.
plugin_registry = PluginRegistry()
