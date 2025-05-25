from django.contrib import admin
from django.http import HttpRequest

from .models import Resume, Plugin as PluginModel
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


class PluginAdmin(admin.ModelAdmin):
    list_display = ("name", "model", "is_active", "has_content")
    list_filter = ("is_active", "model")
    list_editable = ("is_active",)
    search_fields = ("name", "prompt")
    actions = ["activate_plugins", "deactivate_plugins"]

    fieldsets = (
        (
            "Basic Information",
            {
                "fields": ("name", "model", "is_active"),
                "description": "Basic plugin configuration. Toggle is_active to enable/disable the plugin.",
            },
        ),
        (
            "Plugin Code",
            {
                "fields": ("prompt", "module"),
                "classes": ("collapse",),
                "description": "Plugin source code and generation prompt.",
            },
        ),
        (
            "Templates",
            {
                "fields": ("content_template", "form_template"),
                "classes": ("collapse",),
                "description": "Django templates for rendering and editing plugin data.",
            },
        ),
        (
            "Metadata",
            {
                "fields": ("plugin_data",),
                "classes": ("collapse",),
                "description": "JSON data for plugin configuration.",
            },
        ),
    )

    def has_content(self, obj):
        """Check if plugin has both templates."""
        return bool(obj.content_template and obj.form_template)

    has_content.boolean = True  # type: ignore[attr-defined]
    has_content.short_description = "Has Templates"  # type: ignore[attr-defined]

    def activate_plugins(self, request, queryset):
        """Bulk action to activate selected plugins."""
        updated = queryset.update(is_active=True)
        self.message_user(request, f"{updated} plugin(s) activated.")

    activate_plugins.short_description = "Activate selected plugins"  # type: ignore[attr-defined]

    def deactivate_plugins(self, request, queryset):
        """Bulk action to deactivate selected plugins."""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"{updated} plugin(s) deactivated.")

    deactivate_plugins.short_description = "Deactivate selected plugins"  # type: ignore[attr-defined]


admin.site.register(Resume, ResumeAdmin)
admin.site.register(PluginModel, PluginAdmin)
