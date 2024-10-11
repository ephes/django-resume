from django import forms

from django_resume.plugins import SimplePlugin, plugin_registry


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
