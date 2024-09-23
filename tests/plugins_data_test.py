from django_resume.plugins import ListPlugin, SimplePlugin

# simple plugin data manipulation: create, update - there's no delete


def test_simple_plugin_create(person):
    # Given a person and a plugin with no data
    plugin = SimplePlugin()
    # When we create an item
    item = {"foo": "bar"}
    person = plugin.data.create(person, item)
    # Then the attribute should be set
    item = plugin.get_data(person)
    assert len(item) == 1
    assert item["foo"] == "bar"


def test_simple_plugin_update(person):
    # Given a person and a simple plugin with an item
    plugin = SimplePlugin()
    item = {"foo": "bar"}
    person = plugin.data.create(person, item)
    # When we update the item
    item["foo"] = "baz"
    person = plugin.data.update(person, item)
    # Then the attribute should be updated
    item = plugin.get_data(person)
    assert item["foo"] == "baz"


# list plugin data manipulation: create, update, delete


def test_list_plugin_create(person):
    # Given a person and a list plugin
    plugin = ListPlugin()
    # When we create an item
    item = {"foo": "bar"}
    person = plugin.data.create(person, item)
    # Then the item should be in the list
    items = plugin.get_data(person).get("items", [])
    assert len(items) == 1
    assert item in items


def test_list_plugin_update(person):
    # Given a person and a list plugin with an item
    plugin = ListPlugin()
    item = {"id": "123", "foo": "bar"}
    plugin.data.create(person, item)
    # When we update the item
    item["foo"] = "baz"
    person = plugin.data.update(person, item)
    # Then the item should be updated
    items = plugin.get_data(person).get("items", [])
    [updated_item] = [i for i in items if i["id"] == item["id"]]
    assert updated_item["foo"] == "baz"


def test_list_plugin_delete(person):
    # Given a person and a list plugin with an item
    plugin = ListPlugin()
    item = {"id": 123, "foo": "bar"}
    plugin.data.create(person, item)
    # When we delete the item
    person = plugin.data.delete(person, item)
    # Then the item should be removed
    items = plugin.get_data(person).get("items", [])
    assert len(items) == 0
    assert item not in items
