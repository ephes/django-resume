from django.urls import reverse
from django.utils.html import format_html


class BasePlugin:
    name = "base_plugin"
    verbose_name = "Base Plugin"

    def get_data(self, person):
        return person.plugin_data.get(self.name, {})

    def set_data(self, person, data):
        if not person.plugin_data:
            person.plugin_data = {}
        person.plugin_data[self.name] = data
        person.save()

    def get_admin_form(self):
        return None

    def get_admin_url(self, person_id):
        return reverse("admin:person-plugin", args=[person_id, self.name])

    def get_admin_link(self, person_id):
        print("get admin link called for person: ", person_id)
        url = self.get_admin_url(person_id)
        return format_html('<a href="{}">{}</a>', url, f"Edit {self.verbose_name}")

    def get_list_display_field(self):
        def admin_link(obj):
            return self.get_admin_link(obj.id)

        admin_link.short_description = self.verbose_name
        return admin_link


class PluginRegistry:
    def __init__(self):
        self.plugins = {}

    def register(self, plugin_class):
        plugin = plugin_class()
        self.plugins[plugin.name] = plugin

    def get_plugin(self, name):
        return self.plugins.get(name)

    def get_all_plugins(self):
        return self.plugins.values()


plugin_registry = PluginRegistry()
