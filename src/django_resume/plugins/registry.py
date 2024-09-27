from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Plugin


class PluginRegistry:
    """
    A registry for plugins. This is used to register and unregister plugins.
    """

    def __init__(self):
        self.plugins = {}

    def register(self, plugin_class: type["Plugin"]):
        """
        Register a plugin class. This will instantiate the plugin and add it to the registry.

        It will also add the plugin's inline URLs to the urlpatterns list.
        """
        plugin = plugin_class()
        self.plugins[plugin.name] = plugin
        from ..urls import urlpatterns

        urlpatterns.extend(plugin.get_inline_urls())

    def unregister(self, plugin_class: type["Plugin"]):
        del self.plugins[plugin_class.name]

    def get_plugin(self, name):
        return self.plugins.get(name)

    def get_all_plugins(self):
        return self.plugins.values()


# The global plugin registry - this is a singleton since module level variables are shared across the application.
plugin_registry = PluginRegistry()
