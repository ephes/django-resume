from uuid import uuid4


class BasePlugin:
    name = "base_plugin"
    verbose_name = "Base Plugin"

    def get_data(self, person):
        return person.plugin_data.get(self.name, {})

    def set_data(self, person, data):
        if not person.plugin_data:
            person.plugin_data = {}
        person.plugin_data[self.name] = data
        print("setting data: ", data, "on person: ", person)
        return person

    def get_admin_form(self):
        return None

    def get_list_display_field(self):
        def admin_link(obj):
            return self.get_admin_link(obj.id)

        admin_link.short_description = self.verbose_name
        return admin_link

    def create(self, person, data):
        return self.set_data(person, data)

    def update(self, person, data):
        return self.set_data(person, data)

    def delete(self, person, data):
        return self.set_data(person, data)


class ListPlugin(BasePlugin):
    """
    A plugin that displays a list of items. Simple crud operations are supported.
    Each item in the list is a json serializable dict and should have an "id" field.
    """

    name = "list_plugin"

    def get_data(self, person):
        """Returns an empty list if no data is found."""
        return person.plugin_data.get(self.name, [])

    def create(self, person, data):
        data["id"] = str(uuid4())
        items = self.get_data(person)
        items.append(data)
        print("create items: ", items)
        person = self.set_data(person, items)
        print("create for person: ", person)
        return person

    def update(self, person, data):
        items = self.get_data(person)
        for i, item in enumerate(items):
            if item["id"] == data["id"]:
                item.update(data)
                break
        return self.set_data(person, items)

    def delete(self, person, data):
        items = self.get_data(person)
        for i, item in enumerate(items):
            if item["id"] == data["id"]:
                items.pop(i)
                break
        return self.set_data(person, items)


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
