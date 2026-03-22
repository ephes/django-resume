import pytest
from django import forms
from django.urls import NoReverseMatch, reverse

from django_resume.urls import urlpatterns
from django_resume.plugins import SimplePlugin, plugin_registry


@pytest.fixture(autouse=True)
def cleanup_simple_plugin_registration():
    if plugin_registry.get_plugin(SimplePlugin.name) is not None:
        plugin_registry.unregister(SimplePlugin)
    yield
    if plugin_registry.get_plugin(SimplePlugin.name) is not None:
        plugin_registry.unregister(SimplePlugin)


def test_simple_plugin_get_context(resume):
    # Given a resume with a primary key and a plugin with some arbitrary data
    resume.pk = 1
    plugin = SimplePlugin()
    plugin_registry.register(SimplePlugin)
    plugin_data = {"foo": "bar"}

    # When we get the context
    context = plugin.get_context(None, plugin_data, resume.pk, context={"blub": "blub"})

    # Then the context should contain the plugin data and the additional context
    assert context["foo"] == "bar"
    assert context["blub"] == "blub"

    # And the inline edit url should be set
    assert context["edit_url"] == plugin.inline.get_edit_url(resume.pk)

    # And the templates should be set
    assert context["templates"] == plugin.templates


def test_simple_plugin_get_context_defaults_from_form(resume):
    class ExampleForm(forms.Form):
        foo = forms.CharField(initial="bar")

    # Given a resume with a primary key and a plugin with no data
    resume.pk = 1
    plugin = SimplePlugin()
    plugin.inline_form_class = ExampleForm
    plugin_registry.register(SimplePlugin)
    plugin_data = {}

    # When we get the context
    context = plugin.get_context(None, plugin_data, resume.pk, context={})

    # Then the context should contain default values for the plugin data
    assert context["foo"] == "bar"


def test_register_replaces_existing_inline_urls_without_duplicates():
    if plugin_registry.get_plugin(SimplePlugin.name) is not None:
        plugin_registry.unregister(SimplePlugin)

    initial_url_count = len(urlpatterns)
    expected_inline_url_count = len(SimplePlugin().get_inline_urls())

    plugin_registry.register(SimplePlugin)
    first_registration_count = len(urlpatterns)
    plugin_registry.register(SimplePlugin)

    assert first_registration_count == initial_url_count + expected_inline_url_count
    assert len(urlpatterns) == first_registration_count

    plugin_registry.unregister(SimplePlugin)
    assert len(urlpatterns) == initial_url_count


def test_unregister_removes_inline_urls():
    if plugin_registry.get_plugin(SimplePlugin.name) is not None:
        plugin_registry.unregister(SimplePlugin)

    plugin_registry.register(SimplePlugin)
    assert reverse("django_resume:simple_plugin-edit", kwargs={"resume_id": 1})

    plugin_registry.unregister(SimplePlugin)

    with pytest.raises(NoReverseMatch):
        reverse("django_resume:simple_plugin-edit", kwargs={"resume_id": 1})
