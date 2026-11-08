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
        from ..urls import urlpatterns

        from ..i18n import with_resume_language

        # Prepare owned patterns without modifying routes a plugin may reuse.
        # Fragments swapped into a page must use the resume's language too.
        inline_urls = [
            URLPattern(
                pattern.pattern,
                with_resume_language(pattern.callback),
                pattern.default_args,
                pattern.name,
            )
            for pattern in plugin.get_inline_urls()
        ]
        self._remove_inline_urls(plugin.name)
        self.plugins[plugin.name] = plugin
        urlpatterns.extend(inline_urls)
        self.inline_urls[plugin.name] = inline_urls

    def register(self, plugin_class: type["Plugin"]) -> None:
        self.register_plugin_list([plugin_class])

    def register_plugin_list(self, plugin_classes: list) -> None:
        from ..urls import urlpatterns

        plugins = self.plugins.copy()
        inline_urls = self.inline_urls.copy()
        patterns = urlpatterns[:]
        try:
            for plugin_class in plugin_classes:
                self._register(plugin_class)
        except BaseException:
            self.plugins.clear()
            self.plugins.update(plugins)
            self.inline_urls.clear()
            self.inline_urls.update(inline_urls)
            urlpatterns[:] = patterns
            raise
        finally:
            # Invalidate only after publishing or restoring a coherent state.
            clear_url_caches()

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
