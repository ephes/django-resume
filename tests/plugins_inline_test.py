import json

import pytest

from django_resume.plugins import SimplePlugin, plugin_registry


@pytest.mark.django_db
def test_get_edit_view(client, resume):
    # Given a resume in the database and a simple plugin in the registry
    resume.owner.save()
    resume.save()
    plugin_registry.register(SimplePlugin)
    client.force_login(resume.owner)

    # When we get the edit form
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    url = plugin.inline.get_edit_url(resume.pk)
    r = client.get(url)

    # Then the response should be successful and contain the form with the post link
    assert r.status_code == 200

    form = r.context["form"]
    assert "simple_plugin/edit/post" in form.post_url


@pytest.mark.django_db
def test_post_view_not_authenticated(client, resume):
    # Given a resume in the database and a simple plugin in the registry
    resume.owner.save()
    resume.save()
    plugin_registry.register(SimplePlugin)

    # When we post the form without being authenticated
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    url = plugin.inline.get_post_url(resume.pk)
    json_data = json.dumps({"foo": "bar"})
    r = client.post(url, {"plugin_data": json_data})

    # Then the response should be a redirect to the login page
    assert r.status_code == 302
    assert "login" in r.url


@pytest.mark.django_db
def test_post_view_not_authorized(client, resume, django_user_model):
    # Given a resume in the database and a simple plugin in the registry
    resume.owner.save()
    resume.save()
    plugin_registry.register(SimplePlugin)
    unauthorized_user = django_user_model.objects.create_user(
        username="unauthorized", password="password"
    )
    client.force_login(unauthorized_user)

    # When we post the form without being authenticated
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    url = plugin.inline.get_post_url(resume.pk)
    json_data = json.dumps({"foo": "bar"})
    r = client.post(url, {"plugin_data": json_data})

    # Then the response should be a 403 permission denied
    assert r.status_code == 403


@pytest.mark.django_db
def test_post_view_resume_not_found(client, resume):
    # Given a resume in the database and a simple plugin in the registry
    resume.owner.save()
    resume.save()
    plugin_registry.register(SimplePlugin)
    client.force_login(resume.owner)

    # When we post the form without being authenticated
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    url = plugin.inline.get_post_url(23)
    json_data = json.dumps({"foo": "bar"})
    r = client.post(url, {"plugin_data": json_data})

    # Then the response should be a 404 not found
    assert r.status_code == 404


@pytest.mark.django_db
def test_post_view(client, resume):
    # Given a resume in the database and a simple plugin in the registry
    # and the client is logged in
    resume.owner.save()
    resume.save()
    plugin_registry.register(SimplePlugin)
    client.force_login(resume.owner)

    # When we post the form
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    url = plugin.inline.get_post_url(resume.pk)
    json_data = json.dumps({"foo": "bar"})
    r = client.post(url, {"plugin_data": json_data})

    # Then the response should be successful
    assert r.status_code == 200
    resume.refresh_from_db()

    # And the edit_url should be set in the context for the plugin
    assert r.context[SimplePlugin.name]["edit_url"] == plugin.inline.get_edit_url(
        resume.pk
    )

    # And the plugin data should be saved
    assert resume.plugin_data[SimplePlugin.name]["plugin_data"] == {"foo": "bar"}


@pytest.mark.django_db
def test_post_view_invalid_data(client, resume):
    # Given a resume in the database and a simple plugin in the registry
    resume.owner.save()
    resume.save()
    plugin_registry.register(SimplePlugin)
    client.force_login(resume.owner)

    # When we post the form with invalid data
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    url = plugin.inline.get_post_url(resume.pk)
    r = client.post(url, {"plugin_data": "invalid"})

    # Then the response should be successful
    assert r.status_code == 200

    # And the form should contain the error
    form = r.context["form"]
    assert form.errors["plugin_data"] == ["Enter a valid JSON."]
