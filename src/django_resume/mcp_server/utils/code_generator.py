"""Code generation utilities for creating django-resume plugins."""

from typing import Dict, Any, List

from .django_setup import ensure_django_setup


class PluginCodeGenerator:
    """Generates code for django-resume plugins using existing patterns."""

    def __init__(self):
        # Django setup will be called when needed
        pass

    def generate_plugin_from_prompt(
        self, prompt: str, model_name: str = "gpt-4o-mini"
    ) -> Dict[str, Any]:
        """Generate a plugin using the existing LLM-based approach."""
        ensure_django_setup()
        try:
            from django_resume.plugin_generator import generate_simple_plugin

            plugin = generate_simple_plugin(prompt, model_name)
            return {
                "name": plugin.name,
                "prompt": plugin.prompt,
                "module": plugin.module,
                "content_template": plugin.content_template,
                "form_template": plugin.form_template,
                "model": model_name,
                "success": True,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_few_shot_context(self, prompt: str) -> str:
        """Get the few-shot learning context for a prompt."""
        ensure_django_setup()
        from django_resume.plugin_generator import get_simple_plugin_context

        return get_simple_plugin_context(prompt)

    def parse_generated_output(self, llm_output: str) -> Dict[str, Any]:
        """Parse LLM output into plugin components."""
        ensure_django_setup()
        try:
            from django_resume.plugin_generator import parse_llm_output_as_simple_plugin

            parsed = parse_llm_output_as_simple_plugin(llm_output)
            return {"success": True, **parsed}
        except Exception as e:
            return {"success": False, "error": str(e)}


class PluginAnalyzer:
    """Analyzes existing plugins to understand patterns and structure."""

    def __init__(self):
        # Django setup will be called when needed
        pass

    def analyze_existing_plugins(self) -> List[Dict[str, Any]]:
        """Analyze all existing file-based plugins."""
        ensure_django_setup()
        from django_resume.plugins.registry import plugin_registry

        plugins_info = []
        for plugin in plugin_registry.get_all_plugins():
            try:
                # Determine plugin type more reliably
                # SimplePlugin has get_inline_form_class, ListPlugin has get_form_classes
                plugin_type = (
                    "SimplePlugin"
                    if hasattr(plugin, "get_inline_form_class")
                    else "ListPlugin"
                )

                plugin_info = {
                    "name": plugin.name,
                    "verbose_name": plugin.verbose_name,
                    "type": plugin_type,
                    "has_prompt": hasattr(plugin, "prompt"),
                    "template_paths": {},
                }

                # Get template information
                if hasattr(plugin, "templates"):
                    try:
                        plugin_info["template_paths"]["main"] = plugin.templates.main
                        plugin_info["template_paths"]["form"] = plugin.templates.form
                    except:  # noqa: E722
                        pass

                plugins_info.append(plugin_info)
            except Exception as e:
                plugins_info.append(
                    {"name": getattr(plugin, "name", "unknown"), "error": str(e)}
                )

        return plugins_info

    def analyze_plugin_by_name(self, plugin_name: str) -> Dict[str, Any]:
        """Analyze a specific plugin by name."""
        ensure_django_setup()
        from django_resume.plugins.registry import plugin_registry

        plugin = plugin_registry.get_plugin(plugin_name)
        if not plugin:
            return {"error": f"Plugin '{plugin_name}' not found"}

        try:
            # Get plugin source code
            import inspect

            module_source = inspect.getsource(plugin.__class__)

            # Get form class information (different methods for different plugin types)
            form_class = None
            form_source = None

            if hasattr(plugin, "get_inline_form_class"):
                # SimplePlugin
                form_class = plugin.get_inline_form_class()
                form_source = inspect.getsource(form_class) if form_class else None
            elif hasattr(plugin, "get_form_classes"):
                # ListPlugin
                form_classes = plugin.get_form_classes()
                if form_classes:
                    # Get the first form class as representative
                    first_form_name = next(iter(form_classes.keys()), None)
                    if first_form_name:
                        form_class = form_classes[first_form_name]
                        form_source = (
                            inspect.getsource(form_class) if form_class else None
                        )

            # Get template information
            templates_info = {}
            if hasattr(plugin, "templates"):
                try:
                    templates_info["main_path"] = plugin.templates.main
                    templates_info["form_path"] = plugin.templates.form

                    # Try to read template contents
                    from django.template.loader import get_template

                    try:
                        main_template = get_template(plugin.templates.main)
                        templates_info["main_content"] = main_template.template.source
                    except:  # noqa: E722
                        pass

                    try:
                        form_template = get_template(plugin.templates.form)
                        templates_info["form_content"] = form_template.template.source
                    except:  # noqa: E722
                        pass
                except:  # noqa: E722
                    pass

            return {
                "name": plugin.name,
                "verbose_name": plugin.verbose_name,
                "module_source": module_source,
                "form_source": form_source,
                "templates": templates_info,
                "prompt": getattr(plugin, "prompt", None),
            }

        except Exception as e:
            return {"error": f"Failed to analyze plugin: {e}"}


# Global instances
code_generator = PluginCodeGenerator()
plugin_analyzer = PluginAnalyzer()
