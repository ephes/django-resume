import inspect
import re

from django.template import Template, Context
from django.utils.safestring import mark_safe
from django.template.loader import get_template
from django.core.management.base import BaseCommand

from ...plugins.base import SimplePlugin
from ...plugins.registry import plugin_registry, PluginRegistry


def get_simple_plugins(registry: PluginRegistry) -> list[SimplePlugin]:
    return [
        plugin
        for plugin in registry.get_all_plugins()
        if isinstance(plugin, SimplePlugin)
    ]


simple_plugin_template = Template("""
This is the prompt for the plugin:

{{ prompt | safe }}

This is the source code for the plugin itself:

{{ plugin_source | safe }}

This is the source code for the form class:

{{ form_source | safe }}

This is the main template for the plugin:

{{ content_template | safe }}

This is the form template for the plugin:

{{ form_template | safe }}
""")


def source_from_template_path(template_path: str) -> str:
    template = get_template(template_path)
    return template.template.source


def get_source_from_plugin(plugin: SimplePlugin) -> str:
    source = inspect.getsource(plugin.__class__)
    attribute_to_exclude = "prompt"
    pattern = rf'^\s*{attribute_to_exclude}\s*=\s*(""".*?""")\s*?$'
    modified_source = re.sub(pattern, "", source, flags=re.DOTALL | re.MULTILINE)
    return modified_source


def render_plugin_context_template(plugin: SimplePlugin) -> str:
    """
    This function takes a SimplePlugin instance and returns a string that is a
    rendered Django template rendered with the plugin's context.
    """
    context = {
        "plugin": plugin,
        "plugin_source": get_source_from_plugin(plugin),
        "form_source": inspect.getsource(plugin.inline.form_class),
        "prompt": mark_safe(plugin.get_prompt()),
        "content_template": source_from_template_path(
            plugin.templates.get_template_path("main")
        ),
        "form_template": source_from_template_path(
            plugin.templates.get_template_path("form")
        ),
    }
    return simple_plugin_template.render(Context(context))


complete_simple_context_template = Template("""
{% for plugin_context in plugin_contexts %}
{{ plugin_context | safe }}
---
{% endfor %}

After reviewing the examples above, which are separated by the --- markers, you should
have a clear understanding of how to create a new plugin.

Could you generate a new plugin, including the templates and form, following the same
format as the provided examples—meaning as plain text—for the following prompt:

Create a django-resume plugin that allows users to add details about the current state
of their burial pyramid. The plugin should include fields for the pyramid’s name,
location, and height. The name and location should be required fields, while the
height should be optional. Additionally, there should be a field for the year construction
started.
""")


def render_few_shot_context(plugin_contexts: list[str]) -> str:
    context = {
        "plugin_contexts": plugin_contexts,
    }
    return complete_simple_context_template.render(Context(context))


class Command(BaseCommand):
    help = "Create a few-shot context for a new plugin"

    def handle(self, *args, **options):
        plugins = get_simple_plugins(plugin_registry)
        plugin_contexts = []
        for plugin in plugins:
            plugin_contexts.append(render_plugin_context_template(plugin))
        print(render_few_shot_context(plugin_contexts))
