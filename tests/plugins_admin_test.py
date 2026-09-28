import importlib

import pytest
from django import forms
from django.conf import settings
from django.contrib import admin
from django.test import RequestFactory
from django.urls import clear_url_caches, reverse

from django_resume.plugins import (
    SimplePlugin,
)
from django_resume.models import Resume
from django_resume.plugins import plugin_registry as global_plugin_registry


def _rebuild_admin_urls() -> None:
    """
    Force the ROOT_URLCONF to be rebuilt so the per-plugin admin URLs reflect the
    plugins currently in the registry.

    Why this is needed: ``tests/urls.py`` contains ``path("admin/", admin.site.urls)``.
    ``admin.site.urls`` is a property that calls ``ResumeAdmin.get_urls()``, which
    materialises one admin URL pattern per registered plugin (e.g.
    ``example_plugin-admin-change``). That evaluation happens *once*, when the
    ROOT_URLCONF module is first imported, and the resulting ``urlpatterns`` list is
    frozen from then on. ``plugin_registry`` calls ``clear_url_caches()`` on
    register/unregister, but that only drops the resolver's cache -- it cannot add
    patterns to an already-materialised ``urlpatterns`` list.

    Whether the freeze captured our plugin therefore depends on collection order: if
    any earlier test reverses a URL (importing the ROOT_URLCONF) before these fixtures
    run, the admin patterns are frozen *without* our plugin and the reverse lookups in
    these tests raise ``NoReverseMatch``. Reloading the ROOT_URLCONF module re-evaluates
    ``admin.site.urls`` against the current registry, making these fixtures robust to
    collection order. (Production is unaffected: ``AppConfig.ready()`` registers every
    plugin before any request, so the freeze always captures the full set.)
    """
    root_urlconf = importlib.import_module(settings.ROOT_URLCONF)
    importlib.reload(root_urlconf)
    clear_url_caches()


# fixtures


class ExampleForm(forms.Form):
    """Different form for the integration test below."""

    foo = forms.CharField()


class IntegrationPlugin(SimplePlugin):
    """Use a custom form to cover the cases where the form is not the default SimpleAdminForm"""

    name = "example_plugin"
    verbose_name = "Example Plugin"
    admin_form_class = ExampleForm


class MethodCollisionPlugin(SimplePlugin):
    name = "save"
    verbose_name = "Method Collision Plugin"


@pytest.fixture
def plugin_registry():
    """
    Register all plugins in the global plugin registry. This has to be done here because
    if done in the test function, the reverse url lookup will fail when running multiple
    tests. This is probably because the plugin urls are added to the admin urls only once.
    """
    global_plugin_registry.register(IntegrationPlugin)
    global_plugin_registry.register(SimplePlugin)
    # Rebuild the (possibly already frozen) admin URL patterns so they include the
    # plugins just registered, regardless of test collection order. See
    # ``_rebuild_admin_urls`` for the full explanation.
    _rebuild_admin_urls()
    yield global_plugin_registry
    global_plugin_registry.unregister(IntegrationPlugin)
    global_plugin_registry.unregister(SimplePlugin)
    # Restore the admin URL patterns to the registry state after unregistering so
    # later tests are not affected by the plugins registered above.
    _rebuild_admin_urls()


@pytest.fixture
def collision_plugin_registry():
    global_plugin_registry.register(MethodCollisionPlugin)
    _rebuild_admin_urls()
    yield global_plugin_registry
    global_plugin_registry.unregister(MethodCollisionPlugin)
    _rebuild_admin_urls()


# test all views in the admin in isolation


@pytest.mark.django_db
def test_resume_change_contains_simple_plugin_link(
    admin_client, resume, plugin_registry
):
    # Given a resume in the database and a simple plugin in the registry
    resume.owner.save()
    resume.save()

    # When we visit the admin page of the associated resume
    url = reverse("admin:django_resume_resume_change", args=[resume.pk])
    r = admin_client.get(url)

    # Then the plugin should be there
    assert r.status_code == 200
    content = r.content.decode()
    assert f"Edit {SimplePlugin.verbose_name}" in content


def test_resume_admin_uses_prefixed_readonly_field_names_for_plugins(
    collision_plugin_registry,
):
    request = RequestFactory().get("/admin/")
    model_admin = admin.site._registry[Resume]

    readonly_fields = model_admin.get_readonly_fields(request)
    plugin_field_name = model_admin.get_plugin_readonly_field_name("save")

    assert plugin_field_name in readonly_fields
    assert "save" not in readonly_fields
    assert callable(getattr(model_admin, plugin_field_name))


@pytest.mark.django_db
def test_simple_plugin_change_view_contains_form(admin_client, resume, plugin_registry):
    # Given a resume in the database and a simple plugin in the registry
    # and the user is staff and logged in
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    admin_client.force_login(resume.owner)

    # When we visit the edit page of the plugin
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    change_url = plugin.admin.get_change_url(resume.pk)
    r = admin_client.get(change_url)

    # Then the form should be there
    assert r.status_code == 200
    assert "form" in r.context

    content = r.content.decode()
    assert (
        'textarea name="plugin_data"' in content
    )  # the form should have a textarea for the plugin data


@pytest.mark.django_db
def test_simple_plugin_post_data_changes_data(admin_client, resume, plugin_registry):
    # Given a resume in the database and a simple plugin in the registry
    # and the user is staff and logged in
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    admin_client.force_login(resume.owner)

    # When we post data to the plugin
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    post_url = plugin.admin.get_change_post_url(resume.pk)
    data = {"plugin_data": '{"foo": "bar"}'}
    r = admin_client.post(post_url, data)

    # Then the data should be updated
    assert r.status_code == 200

    resume.refresh_from_db()
    plugin_data = plugin.get_data(resume)
    assert plugin_data == {"foo": "bar"}


@pytest.mark.django_db
def test_simple_plugin_post_data_invalid(admin_client, resume, plugin_registry):
    # Given a resume in the database and a simple plugin in the registry
    # and the user is staff and logged in
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    admin_client.force_login(resume.owner)

    # When we post data to the plugin
    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    post_url = plugin.admin.get_change_post_url(resume.pk)
    data = {"plugin_data": "invalid"}
    r = admin_client.post(post_url, data)

    # Then the error message should be shown
    assert r.status_code == 200
    form = r.context["form"]
    [error] = form.errors["plugin_data"]
    assert error == "Enter a valid JSON."


@pytest.mark.django_db
def test_simple_plugin_post_data_checks_permissions_before_validation(
    admin_client, resume, plugin_registry, django_user_model
):
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    other_staff_user = django_user_model.objects.create_user(
        username="other-staff", password="password", is_staff=True
    )
    admin_client.force_login(other_staff_user)

    plugin = plugin_registry.get_plugin(SimplePlugin.name)
    post_url = plugin.admin.get_change_post_url(resume.pk)
    response = admin_client.post(post_url, {"plugin_data": "invalid"})

    assert response.status_code == 403


# integration test: click on the edit button, change the data, save, check the data


@pytest.mark.django_db
def test_simple_plugin_integration(admin_client, resume, plugin_registry):
    # Given a resume in the database and a simple plugin in the registry
    # and the user is staff
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()

    # When we visit the edit page of the plugin
    resume_change_url = reverse("admin:django_resume_resume_change", args=[resume.pk])
    r = admin_client.get(resume_change_url)

    # Then the change link should be there
    assert r.status_code == 200
    content = r.content.decode()
    lines = content.split("\n")
    [link_line] = [line for line in lines if "Edit Example Plugin" in line]
    change_url = link_line.split("href=")[1].split('"')[1]

    # When we visit the change page being logged in
    admin_client.force_login(resume.owner)
    r = admin_client.get(change_url)
    assert r.status_code == 200

    # Then the form should be there and it should have a post url
    form = r.context["form"]
    post_url = form.post_url

    # When we post data to the plugin
    data = {"foo": "bar"}
    r = admin_client.post(post_url, data)
    assert r.status_code == 200

    # Then the data should be updated in the content (foo field value should be "bar")
    content = r.content.decode()
    assert 'value="bar"' in content

    # And the data should have been updated in the database
    resume.refresh_from_db()
    plugin = IntegrationPlugin()
    plugin_data = plugin.get_data(resume)

    assert plugin_data == {"foo": "bar"}
