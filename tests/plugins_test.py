from django.urls import clear_url_caches, path, include
from django_resume.urls import urlpatterns
from django_resume.plugins import SimplePlugin


# https://stackoverflow.com/questions/45173272/django-pytest-test-url-based-on-settings
def test_simple_plugin_get_context(person):
    # Given a plugin and some arbitrary data
    person.pk = 1
    plugin = SimplePlugin()
    plugin_urlpatterns = (plugin.get_inline_urls(), "django_resume")
    urlpatterns.append(path("", include(plugin_urlpatterns, namespace="django_resume")))

    clear_url_caches()
    # plugin_registry.register(SimplePlugin)
    # plugin = plugin_registry.get_plugin(SimplePlugin.name)
    plugin_data = {"foo": "bar"}
    # When we get the context
    context = plugin.get_context(plugin_data, person.pk, context={"blub": "blub"})
    # Then the context should contain the plugin data and the additional context
    assert context["foo"] == "bar"
    assert context["blub"] == "blub"

    # And the inline edit url should be set
    assert context["edit_url"] == plugin.inline.get_edit_url(person.pk)

    # And the templates should be set
    assert context["templates"] == plugin.templates
