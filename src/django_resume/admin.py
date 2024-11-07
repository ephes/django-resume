from django.contrib import admin
from django.http import HttpRequest

from .models import Resume
from .plugins import plugin_registry
from .plugins.base import Plugin, URLPatterns


class ResumeAdmin(admin.ModelAdmin):
    # fields = ("name", "slug", "plugin_data")

    def get_urls(self) -> URLPatterns:
        urls = super().get_urls()
        custom_urls = []
        for plugin in plugin_registry.get_all_plugins():
            custom_urls.extend(plugin.get_admin_urls(self.admin_site.admin_view))
        return custom_urls + urls

    def add_plugin_method(self, plugin: Plugin) -> None:
        """
        Add a method to the admin class that will return a link to the plugin admin view.
        This is used to have the plugins show up as readonly fields in the resume change view.
        """

        def plugin_method(_self, obj: Resume) -> str:
            admin_link = plugin.get_admin_link(obj.id)
            return admin_link

        plugin_method.__name__ = plugin.name
        setattr(self.__class__, plugin.name, plugin_method)

    def get_readonly_fields(self, request: HttpRequest, obj=None) -> list[str]:
        """Add a readonly field for each plugin."""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        # Filter out all plugins already in readonly_fields - somehow this method is getting called multiple times
        readonly_fields_lookup = set(readonly_fields)
        new_plugins = [
            p
            for p in plugin_registry.get_all_plugins()
            if p.name not in readonly_fields_lookup
        ]
        for plugin in new_plugins:
            readonly_fields.append(plugin.name)
            self.add_plugin_method(plugin)
        return readonly_fields


admin.site.register(Resume, ResumeAdmin)
