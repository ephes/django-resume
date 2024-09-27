import pytest

from django.urls import path, include
from django_resume.plugins import SimplePlugin


class SimplePluginUrlpatterns:
    def __init__(self):
        self.urlpatterns = [
            path(
                "",
                include(
                    (SimplePlugin().get_inline_urls(), "django_resume"),
                    namespace="django_resume",
                ),
            )
        ]


@pytest.mark.urls(SimplePluginUrlpatterns())
def test_simple_plugin_get_context(person):
    # Given a person with a primary key and a plugin with some arbitrary data
    person.pk = 1
    plugin = SimplePlugin()
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
