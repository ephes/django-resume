import inspect
import re

from django.template import Template, Context
from django.utils.safestring import mark_safe
from django.template.loader import get_template
from django.core.management.base import BaseCommand

from ...plugins.base import SimplePlugin
from ...plugins.registry import plugin_registry, PluginRegistry


def get_simple_plugins(registry: PluginRegistry) -> list[SimplePlugin]:
    allowed_plugin_names = {
        "education",
        "permission_denied",
        "about",
        "skills",
        "theme",
        "identity",
    }
    return [
        plugin
        for plugin in registry.get_all_plugins()
        if isinstance(plugin, SimplePlugin) and plugin.name in allowed_plugin_names
    ]


simple_plugin_template = Template("""
This is the prompt for the plugin:

{{ prompt | safe }}

This is the source code for the implemented plugin using ===name=== markers. The
first marker just contains the name of the plugin. The rest paths for the files that
need to be created:

==={{ plugin.name }}===
 
==={{ plugin.name }}.py===

{{ module_source | safe }}

===django_resume/plugins/{{ plugin.name }}/plain/content.html===

{{ content_template | safe }}

===django_resume/plugins/{{ plugin.name }}/plain/form.html===

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


def get_module_source(plugin: SimplePlugin) -> str:
    # Get the class of the instance
    cls = type(plugin)
    # Find the module the class belongs to
    module = inspect.getmodule(cls)
    if module is None:
        raise ValueError("Module could not be determined for the given instance.")
    # Get the full source code of the module
    source = inspect.getsource(module)
    # Replace relative imports with absolute imports
    source = source.replace(
        "from .base import SimplePlugin",
        "from django_resume.plugins import SimplePlugin",
    )
    # Exclude the prompt attribute from the source code
    attribute_to_exclude = "prompt"
    pattern = rf'^\s*{attribute_to_exclude}\s*=\s*(""".*?""")\s*?$'
    source = re.sub(pattern, "", source, flags=re.DOTALL | re.MULTILINE)
    return source


def render_plugin_context_template(plugin: SimplePlugin) -> str:
    """
    This function takes a SimplePlugin instance and returns a string that is a
    rendered Django template rendered with the plugin's context.
    """

    context = {
        "plugin": plugin,
        "module_source": get_module_source(plugin),
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

Create a django-resume plugin named "pyramid" that allows users to add details about
the current state of their burial pyramid. The headline for the plugin is the name
of the pyramid. The plugin should include fields for the pyramid’s name, location,
and height. The name and location should be required fields, while the height should be optional.
But if a height is given, it should be invalid if it is below 50 meters raising a ValidationError 
that says: Your puny pyramid is pathetic! Additionally, there should be a field for the
year construction started. The construction year should have a default value of -2500 and be left
aligned while the location should be left aligned and the height centered. And make sure
that the forms cleaned_data attribute is really json serializable.
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
