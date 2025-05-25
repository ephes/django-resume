"""MCP tool for creating plugins directly in the database with provided code."""

import json
from typing import Any

from mcp.types import Tool, TextContent

from ..utils.django_setup import ensure_django_setup
from ..utils.validator import validator


class CreatePluginDirectTool:
    """Tool for creating plugins directly in the database with provided code."""

    def get_tool(self) -> Tool:
        """Get the MCP tool definition."""
        return Tool(
            name="create_plugin_direct",
            description="Create a plugin directly in the database with provided Python and template code",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Plugin name (lowercase with underscores, must be unique)",
                        "pattern": "^[a-z][a-z0-9_]*$",
                    },
                    "verbose_name": {
                        "type": "string",
                        "description": "Human-readable plugin title",
                        "maxLength": 200,
                    },
                    "module_code": {
                        "type": "string",
                        "description": "Complete Python module code for the plugin",
                    },
                    "content_template": {
                        "type": "string",
                        "description": "HTML template for displaying plugin content",
                    },
                    "form_template": {
                        "type": "string",
                        "description": "HTML template for the plugin edit form",
                    },
                    "prompt": {
                        "type": "string",
                        "description": "Optional: Original prompt that inspired this plugin",
                        "default": "",
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "Whether to activate the plugin immediately",
                        "default": True,
                    },
                    "model": {
                        "type": "string",
                        "description": "Model used for generation (for reference)",
                        "default": "claude-3.5-sonnet",
                    },
                    "validate_only": {
                        "type": "boolean",
                        "description": "Only validate the code without creating the plugin",
                        "default": False,
                    },
                },
                "required": [
                    "name",
                    "verbose_name",
                    "module_code",
                    "content_template",
                    "form_template",
                ],
            },
        )

    def execute(self, arguments: dict[str, Any]) -> TextContent:
        """Execute the create_plugin_direct tool."""
        try:
            ensure_django_setup()

            name = arguments["name"]
            verbose_name = arguments["verbose_name"]
            module_code = arguments["module_code"]
            content_template = arguments["content_template"]
            form_template = arguments["form_template"]
            prompt = arguments.get("prompt", "")
            is_active = arguments.get("is_active", True)
            model = arguments.get("model", "claude-3.5-sonnet")
            validate_only = arguments.get("validate_only", False)

            # Validate the plugin code
            validation_result = self._validate_plugin(
                name, module_code, content_template, form_template
            )

            if not validation_result["is_valid"]:
                return TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": False,
                            "error": "Plugin validation failed",
                            "validation": validation_result,
                        },
                        indent=2,
                    ),
                )

            # If only validating, return validation results
            if validate_only:
                return TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": True,
                            "message": "Plugin validation passed",
                            "validation": validation_result,
                        },
                        indent=2,
                    ),
                )

            # Check if plugin name already exists
            from django_resume.models import Plugin

            if Plugin.objects.filter(name=name).exists():
                return TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": False,
                            "error": f"Plugin with name '{name}' already exists",
                        },
                        indent=2,
                    ),
                )

            # Create the plugin in the database
            plugin = Plugin.objects.create(
                name=name,
                prompt=prompt,
                module=module_code,
                content_template=content_template,
                form_template=form_template,
                model=model,
                is_active=is_active,
            )

            # Try to reload the plugin registry to make it available immediately
            try:
                from django_resume.plugins.registry import plugin_registry

                plugin_registry.reload_db_plugins()
                registry_reloaded = True
            except Exception as e:
                registry_reloaded = False
                registry_error = str(e)

            result = {
                "success": True,
                "plugin": {
                    "id": plugin.id,
                    "name": plugin.name,
                    "verbose_name": verbose_name,
                    "is_active": plugin.is_active,
                },
                "validation": validation_result,
                "registry_reloaded": registry_reloaded,
            }

            if not registry_reloaded:
                result["registry_error"] = registry_error
                result["note"] = (
                    "Plugin created but registry reload failed. Plugin may not be immediately available."
                )

            return TextContent(
                type="text",
                text=json.dumps(result, indent=2),
            )

        except Exception as e:
            return TextContent(
                type="text",
                text=json.dumps(
                    {
                        "success": False,
                        "error": f"Failed to create plugin: {str(e)}",
                    },
                    indent=2,
                ),
            )

    def _validate_plugin(
        self, name: str, module_code: str, content_template: str, form_template: str
    ) -> dict[str, Any]:
        """Validate all aspects of the plugin."""
        errors: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        # Validate plugin name (relaxed)
        if not name.islower():
            warnings.append("Plugin name should be lowercase")
        if not name.replace("_", "").isalnum():
            warnings.append(
                "Plugin name should only contain lowercase letters, numbers, and underscores"
            )
        if name.startswith("_") or name.endswith("_"):
            warnings.append("Plugin name should not start or end with underscore")
        if len(name) < 1:
            errors.append("Plugin name cannot be empty")
        if len(name) > 100:
            errors.append("Plugin name is too long (over 100 characters)")

        # Validate Python module code
        module_validation = validator.validate_plugin_code(module_code)
        errors.extend(module_validation.errors)
        warnings.extend(module_validation.warnings)
        suggestions.extend(module_validation.suggestions)

        # Validate content template (very relaxed - only critical errors)
        content_validation = validator.validate_template_code(content_template)
        # Only include critical template errors (like script tags)
        critical_content_errors = [
            error for error in content_validation.errors if "script" in error.lower()
        ]
        errors.extend(
            [f"Content template: {error}" for error in critical_content_errors]
        )
        warnings.extend(
            [f"Content template: {warning}" for warning in content_validation.warnings]
        )

        # Validate form template (very relaxed)
        form_validation = validator.validate_template_code(form_template)
        critical_form_errors = [
            error for error in form_validation.errors if "script" in error.lower()
        ]
        errors.extend([f"Form template: {error}" for error in critical_form_errors])
        warnings.extend(
            [f"Form template: {warning}" for warning in form_validation.warnings]
        )

        # Additional plugin-specific validations
        self._validate_plugin_structure(
            name, module_code, errors, warnings, suggestions
        )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
        }

    def _validate_plugin_structure(
        self,
        name: str,
        module_code: str,
        errors: list[str],
        warnings: list[str],
        suggestions: list[str],
    ) -> None:
        """Validate plugin-specific structure requirements."""
        import re

        # Check for imports (as warnings, not errors)
        if "from django import forms" not in module_code:
            warnings.append("Consider adding: 'from django import forms'")

        if (
            "from .base import" not in module_code
            and "from django_resume.plugins.base import" not in module_code
        ):
            warnings.append(
                "Consider importing SimplePlugin or ListPlugin from .base or django_resume.plugins.base"
            )

        # Check for form class (relaxed)
        form_class_pattern = r"class\s+\w+Form\s*\("
        if not re.search(form_class_pattern, module_code):
            warnings.append(
                "No Form class found (consider creating one ending with 'Form')"
            )

        # Check for plugin class (relaxed)
        plugin_class_pattern = r"class\s+\w+Plugin\s*\("
        if not re.search(plugin_class_pattern, module_code):
            warnings.append(
                "No Plugin class found (consider creating one ending with 'Plugin')"
            )

        # Check for plugin attributes (relaxed)
        if (
            f'name = "{name}"' not in module_code
            and f"name = '{name}'" not in module_code
        ):
            suggestions.append(
                f"Consider adding name = '{name}' attribute to plugin class"
            )

        if "verbose_name" not in module_code:
            suggestions.append(
                "Consider adding a verbose_name attribute to plugin class"
            )

        if "form_class" not in module_code and "item_form_class" not in module_code:
            suggestions.append(
                "Consider referencing a form class (form_class or item_form_class) in plugin class"
            )

        # Check for critical security issues only
        critical_patterns = ["exec(", "eval(", "__import__("]
        for pattern in critical_patterns:
            if pattern in module_code:
                errors.append(f"Security issue: dangerous pattern '{pattern}' found")

        # Check for other patterns as warnings
        warning_patterns = ["open(", "file(", "subprocess", "os.system", "os.popen"]
        for pattern in warning_patterns:
            if pattern in module_code:
                warnings.append(
                    f"Potentially risky pattern '{pattern}' found - use with caution"
                )

        # Suggest improvements
        if "help_text" not in module_code:
            suggestions.append(
                "Consider adding help_text to form fields for better user experience"
            )

        if "required=False" not in module_code and "required=True" not in module_code:
            suggestions.append(
                "Consider explicitly setting required=True/False on form fields"
            )

        if len(module_code.split("\n")) > 200:
            suggestions.append(
                "Plugin module is quite long - consider breaking into smaller functions"
            )


# Global instance
create_plugin_direct_tool = CreatePluginDirectTool()
