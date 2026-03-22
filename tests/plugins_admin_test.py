import pytest
from django import forms
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from django_resume.plugins import (
    SimplePlugin,
)
from django_resume.models import Resume
from django_resume.plugins import plugin_registry as global_plugin_registry


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
    yield global_plugin_registry
    global_plugin_registry.unregister(IntegrationPlugin)
    global_plugin_registry.unregister(SimplePlugin)


@pytest.fixture
def collision_plugin_registry():
    global_plugin_registry.register(MethodCollisionPlugin)
    yield global_plugin_registry
    global_plugin_registry.unregister(MethodCollisionPlugin)


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
