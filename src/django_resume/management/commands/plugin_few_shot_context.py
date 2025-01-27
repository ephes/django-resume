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
Example{{ index }}: {{ plugin.verbose_name }} Plugin

Prompt:

{{ prompt | safe }}

Generated Output:

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
    assert hasattr(template, "template")
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
Prompt for Generating a New Django-Resume Plugin

After reviewing the examples below, which are separated by --- markers, you should have a clear understanding of how to create a new plugin. Each plugin consists of multiple sections marked with ===, representing the plugin name, source code, and templates.

Please follow this format to generate a new plugin:
1. Plugin Name:
    - Format: ===plugin_name===
    - Example: ===education===
2. Python Plugin File:
    - Format: ===plugin_name.py===
    - Should include:
    - Django form definition with required fields and validations.
    - A SimplePlugin subclass with metadata such as name and verbose_name.
    - Validation logic to ensure all fields are properly handled.
3. Content Template:
    - Format: ===django_resume/plugins/plugin_name/plain/content.html===
    - Should define:
    - Proper rendering of the plugin data with field placeholders.
    - Support for conditional editing icons.
    - Appropriate HTML structure and alignment.
4. Form Template:
    - Format: ===django_resume/plugins/plugin_name/plain/form.html===
    - Should provide:
    - Editable fields using contenteditable="true".
    - A submit button with a visually appropriate layout.
    - When using the editable-form web component, input fields should only be in
      the form, not in the content section. In the content section editable fields
      are just those with the contenteditable attribute. There should be exactly
      the same number of editable fields in the form as in the content section.
5. Output:
    - Please dont output markdown. Just plain text between the === markers.
    - Please no content after the last Django template content.c

Task: Generate a New Plugin

Create a django-resume plugin to add details about a burial pyramid.
The plugin should be named "pyramid" with the verbose name "Burial Pyramid".
The plugin should include fields for the pyramid’s name, location, height,
and the year construction started. The pyramid name, location and height are
required fields. The height must be at least 50 meters. Otherwise, it should
raise a validation error saying “Your puny pyramid is pathetic!” The
construction year should default to -2500.

When displayed, the plugin should show the pyramid’s name as the headline.
Please try to make the rendered html look nice. The form’s cleaned data must
be JSON serializable.

Few-Shot Examples:
{% for plugin_context in plugin_contexts %}
{{ plugin_context | safe }}
{% if not forloop.last %}
---
{% endif %}
{% endfor %}
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
