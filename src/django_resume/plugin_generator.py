import re
import inspect

from pathlib import Path

from django.template import Template, Context
from django.template.loader import get_template
from django.utils.safestring import mark_safe

from .models import Plugin
from .plugins import SimplePlugin
from .plugins.registry import PluginRegistry, plugin_registry


def get_simple_plugins(registry: PluginRegistry) -> list[SimplePlugin]:
    """Return a list of SimplePlugins from the registry with allowed names."""

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

Here's some CSS you can use to style your Django templates:

{{ plain_css | safe }}

And here's some additional CSS that might come in handy for the editing interface:

{{ plain_edit_css | safe }}

Prompt for Generating a New Django-Resume Plugin

After reviewing the examples below, which are separated by --- markers, you should have a clear understanding of how to create a new plugin. Each plugin consists of multiple sections marked with ===, representing the plugin name, source code, and templates.

Please follow this format to generate a new plugin:
1. Plugin Name:
    - Format: ===plugin_name===
    - Example: ===education===
2. Python Plugin File:
    - Format: ===plugin_name.py===
    - Should include:
    - Django form definition with required fields and validations. The form should not use fields that
      are not JSON serializable like DecimalField for example.
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
    - Please do not output markdown (no ```python, no ```html). Just plain text
      between the === markers.
    - Please no content after the last Django template content. 

Task: Generate a New Plugin

{{ prompt }}

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


def get_plain_css_context() -> dict:
    plain_css_path = (
        Path(__file__).parent / "static" / "django_resume" / "css" / "styles.css"
    )
    plain_edit_css_path = (
        Path(__file__).parent / "static" / "django_resume" / "css" / "edit.css"
    )
    return {
        "plain_css": plain_css_path.read_text(),
        "plain_edit_css": plain_edit_css_path.read_text(),
    }


def render_few_shot_context(prompt: str, plugin_contexts: list[str]) -> str:
    context = {
        "plugin_contexts": plugin_contexts,
        "prompt": prompt,
    } | get_plain_css_context()
    return complete_simple_context_template.render(Context(context))


def get_simple_plugin_context(prompt: str) -> str:
    plugin_contexts = []
    for plugin in get_simple_plugins(plugin_registry):
        plugin_contexts.append(render_plugin_context_template(plugin))
    return render_few_shot_context(prompt, plugin_contexts)


def context_to_output_via_llm(context: str, model_name: str = "gpt-4o-mini") -> str:
    import llm  # don't break Django application if llm is not installed

    model = llm.get_model(model_name)
    response = model.prompt(context)
    return response.text()


def parse_llm_output_as_simple_plugin(llm_output: str) -> dict:
    sections = re.split(r"===(.+?)===", llm_output.strip())
    if len(sections) < 3:
        raise ValueError("Invalid input format")
    plugin_name = sections[1].strip()
    plugin_data = dict(zip(sections[3::2], sections[4::2]))
    plugin_file_name = f"{plugin_name}.py"
    plugin_module = plugin_data[plugin_file_name]
    content_template_path = f"django_resume/plugins/{plugin_name}/plain/content.html"
    content_template_source = plugin_data[content_template_path]
    form_template_path = f"django_resume/plugins/{plugin_name}/plain/form.html"
    form_template_source = plugin_data[form_template_path]
    form_template_source = form_template_source.split("---")[0]
    return {
        "name": plugin_name,
        "module": plugin_module,
        "content_template": content_template_source,
        "form_template": form_template_source,
    }


def generate_simple_plugin(prompt: str, model_name: str = "gpt-4o-mini") -> Plugin:
    simple_plugin_context = get_simple_plugin_context(prompt)
    llm_output = context_to_output_via_llm(simple_plugin_context, model_name=model_name)
    parsed_output = parse_llm_output_as_simple_plugin(llm_output)
    plugin = Plugin(
        name=parsed_output["name"],
        prompt=prompt,
        module=parsed_output["module"],
        content_template=parsed_output["content_template"],
        form_template=parsed_output["form_template"],
    )
    return plugin
