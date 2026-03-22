from typing import TYPE_CHECKING, Union

from django.urls import URLPattern, clear_url_caches

if TYPE_CHECKING:
    from .base import Plugin

PluginStore = dict[str, "Plugin"]


class PluginRegistry:
    """
    A registry for plugins. This is used to register and unregister plugins.
    """

    def __init__(self) -> None:
        self.plugins: PluginStore = {}
        self.inline_urls: dict[str, list[URLPattern]] = {}

    def _remove_inline_urls(self, plugin_name: str) -> None:
        patterns_to_remove = self.inline_urls.pop(plugin_name, [])
        if not patterns_to_remove:
            return
        from ..urls import urlpatterns

        urlpatterns[:] = [
            pattern for pattern in urlpatterns if pattern not in patterns_to_remove
        ]

    def _register(self, plugin_class: type["Plugin"]) -> None:
        """
        Register a plugin class. This will instantiate the plugin and add it to the registry.

        It will also add the plugin's inline URLs to the urlpatterns list.
        """
        plugin = plugin_class()
        self._remove_inline_urls(plugin.name)
        self.plugins[plugin.name] = plugin
        from ..urls import urlpatterns

        inline_urls = plugin.get_inline_urls()
        urlpatterns.extend(inline_urls)
        self.inline_urls[plugin.name] = inline_urls

    def register(self, plugin_class: type["Plugin"]) -> None:
        self._register(plugin_class)
        clear_url_caches()

    def register_plugin_list(self, plugin_classes: list) -> None:
        for plugin_class in plugin_classes:
            self.register(plugin_class)

    def unregister(self, plugin_class: type["Plugin"]) -> None:
        del self.plugins[plugin_class.name]
        self._remove_inline_urls(plugin_class.name)
        clear_url_caches()

    def get_plugin(self, name) -> Union["Plugin", None]:
        return self.plugins.get(name)

    def get_all_plugins(self) -> list["Plugin"]:
        return list(self.plugins.values())


# The global plugin registry - this is a singleton since module level variables are shared across the application.
plugin_registry = PluginRegistry()
