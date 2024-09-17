import pytest

from django_resume.models import Person
from django_resume.plugins import ListPlugin, BasePlugin


@pytest.fixture
def person():
    return Person(name="John Doe", slug="john-doe")


def test_base_plugin_create(person):
    # Given a person and a base plugin
    plugin = BasePlugin()
    # When we create an item
    item = {"foo": "bar"}
    person = plugin.create(person, item)
    # Then the attribute should be set
    item = plugin.get_data(person)
    assert len(item) == 1
    assert item["foo"] == "bar"


def test_base_plugin_update(person):
    # Given a person and a base plugin with an item
    plugin = BasePlugin()
    item = {"foo": "bar"}
    person = plugin.create(person, item)
    # When we update the item
    item["foo"] = "baz"
    person = plugin.update(person, item)
    # Then the attribute should be updated
    item = plugin.get_data(person)
    assert item["foo"] == "baz"


def test_list_plugin_create(person):
    # Given a person and a list plugin
    plugin = ListPlugin()
    # When we create an item
    item = {"foo": "bar"}
    person = plugin.create(person, item)
    # Then the item should be in the list
    items = plugin.get_data(person).get("items", [])
    assert len(items) == 1
    assert item in items


def test_list_plugin_update(person):
    # Given a person and a list plugin with an item
    plugin = ListPlugin()
    item = {"foo": "bar"}
    plugin.create(person, item)
    # When we update the item
    item["foo"] = "baz"
    person = plugin.update(person, item)
    # Then the item should be updated
    items = plugin.get_data(person).get("items", [])
    [updated_item] = [i for i in items if i["id"] == item["id"]]
    assert updated_item["foo"] == "baz"


def test_list_plugin_delete(person):
    # Given a person and a list plugin with an item
    plugin = ListPlugin()
    item = {"foo": "bar"}
    plugin.create(person, item)
    # When we delete the item
    person = plugin.delete(person, item)
    # Then the item should be removed
    items = plugin.get_data(person).get("items", [])
    assert len(items) == 0
    assert item not in items
