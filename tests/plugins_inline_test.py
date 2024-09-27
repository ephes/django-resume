import json

import pytest

from django_resume.plugins import SimplePlugin, plugin_registry


@pytest.mark.django_db
def test_get_edit_view(client, person):
    # Given a person in the database and a simple plugin in the registry
    person.save()
    plugin_registry.register(SimplePlugin)

    # When we get the edit form
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    url = plugin.inline.get_edit_url(person.pk)
    r = client.get(url)

    # Then the response should be successful and contain the form with the post link
    assert r.status_code == 200

    form = r.context["form"]
    assert "simple_plugin/edit/post" in form.post_url


@pytest.mark.django_db
def test_post_view(client, person):
    # Given a person in the database and a simple plugin in the registry
    person.save()
    plugin_registry.register(SimplePlugin)

    # When we post the form
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    url = plugin.inline.get_post_url(person.pk)
    json_data = json.dumps({"foo": "bar"})
    r = client.post(url, {"plugin_data": json_data})

    # Then the response should be successful
    assert r.status_code == 200
    person.refresh_from_db()

    # And the edit_url should be set in the context for the plugin
    assert r.context[SimplePlugin.name]["edit_url"] == plugin.inline.get_edit_url(
        person.pk
    )

    # And the plugin data should be saved
    assert person.plugin_data[SimplePlugin.name]["plugin_data"] == {"foo": "bar"}


@pytest.mark.django_db
def test_post_view_invalid_data(client, person):
    # Given a person in the database and a simple plugin in the registry
    person.save()
    plugin_registry.register(SimplePlugin)

    # When we post the form with invalid data
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    url = plugin.inline.get_post_url(person.pk)
    r = client.post(url, {"plugin_data": "invalid"})

    # Then the response should be successful
    assert r.status_code == 200

    # And the form should contain the error
    form = r.context["form"]
    assert form.errors["plugin_data"] == ["Enter a valid JSON."]
