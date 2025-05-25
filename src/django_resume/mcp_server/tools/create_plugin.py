"""MCP tool for creating new django-resume plugins."""

import json
from typing import Dict, Any

from mcp.types import Tool, TextContent

from ..utils.django_setup import ensure_django_setup
from ..utils.code_generator import code_generator
from ..utils.validator import validator

# For lazy loading - try to get the ensure_django function
try:
    from django_resume.entrypoints.mcp_server_lazy import ensure_django
except ImportError:
    # Fallback to the regular Django setup
    ensure_django = ensure_django_setup


class CreatePluginTool:
    """Tool for creating new django-resume plugins."""

    def get_tool(self) -> Tool:
        """Get the MCP tool definition."""
        return Tool(
            name="create_plugin",
            description="Create a new django-resume plugin with code generation",
            inputSchema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "Description of the desired plugin functionality",
                    },
                    "plugin_name": {
                        "type": "string",
                        "description": "Optional: Specific name for the plugin (lowercase with underscores)",
                        "pattern": "^[a-z][a-z0-9_]*$",
                    },
                    "model": {
                        "type": "string",
                        "description": "LLM model to use for generation",
                        "enum": [
                            "gpt-4o-mini",
                            "gpt-4o",
                            "gpt-4.1",
                            "gpt-4.1-mini",
                            "gpt-o1-mini",
                            "gpt-o1",
                            "gpt-o4-mini",
                            "claude-3.5-haiku",
                            "claude-3.7-sonnet-latest",
                            "claude-4-sonnet",
                        ],
                        "default": "gpt-4o-mini",
                    },
                    "validate_only": {
                        "type": "boolean",
                        "description": "Only validate the generated code without saving",
                        "default": False,
                    },
                    "save_to_database": {
                        "type": "boolean",
                        "description": "Save the plugin to the database",
                        "default": True,
                    },
                    "activate_plugin": {
                        "type": "boolean",
                        "description": "Activate the plugin after creation",
                        "default": False,
                    },
                },
                "required": ["prompt"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> TextContent:
        """Execute the create_plugin tool."""
        try:
            ensure_django_setup()

            prompt = arguments["prompt"]
            model = arguments.get("model", "gpt-4o-mini")
            validate_only = arguments.get("validate_only", False)
            save_to_database = arguments.get("save_to_database", True)
            activate_plugin = arguments.get("activate_plugin", False)
            plugin_name = arguments.get("plugin_name")

            # Generate the plugin
            result = code_generator.generate_plugin_from_prompt(prompt, model)

            if not result.get("success"):
                return TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": False,
                            "error": result.get("error", "Unknown generation error"),
                        },
                        indent=2,
                    ),
                )

            # Override plugin name if specified
            if plugin_name:
                result["name"] = plugin_name

            # Validate the generated plugin
            validation_result = validator.validate_plugin_code(result.get("module", ""))

            response = {
                "success": True,
                "plugin": {
                    "name": result["name"],
                    "prompt": result["prompt"],
                    "model": result["model"],
                    "has_module": bool(result.get("module", "").strip()),
                    "has_content_template": bool(
                        result.get("content_template", "").strip()
                    ),
                    "has_form_template": bool(result.get("form_template", "").strip()),
                },
                "validation": {
                    "is_valid": validation_result.is_valid,
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                    "suggestions": validation_result.suggestions,
                },
            }

            # Add generated code if validation passes or if explicitly requested
            if validation_result.is_valid or validate_only:
                response["generated_code"] = {
                    "module": result.get("module", ""),
                    "content_template": result.get("content_template", ""),
                    "form_template": result.get("form_template", ""),
                }

            # Save to database if requested and validation passes
            if save_to_database and validation_result.is_valid and not validate_only:
                save_result = self._save_to_database(result, activate_plugin)
                response["database"] = save_result

            return TextContent(type="text", text=json.dumps(response, indent=2))

        except Exception as e:
            return TextContent(
                type="text",
                text=json.dumps(
                    {"success": False, "error": f"Tool execution error: {str(e)}"},
                    indent=2,
                ),
            )

    def _save_to_database(
        self, plugin_data: Dict[str, Any], activate: bool = False
    ) -> Dict[str, Any]:
        """Save the plugin to the database."""
        try:
            from django_resume.models import Plugin

            # Check if plugin already exists
            existing = Plugin.objects.filter(name=plugin_data["name"]).first()
            if existing:
                return {
                    "success": False,
                    "error": f"Plugin '{plugin_data['name']}' already exists",
                    "existing_plugin_id": existing.id,
                }

            # Create new plugin
            plugin = Plugin.objects.create(
                name=plugin_data["name"],
                prompt=plugin_data["prompt"],
                module=plugin_data.get("module", ""),
                content_template=plugin_data.get("content_template", ""),
                form_template=plugin_data.get("form_template", ""),
                model=plugin_data.get("model", "gpt-4o-mini"),
                is_active=activate,
            )

            # Register the plugin if activated
            if activate:
                Plugin.objects.register_plugin_models()

            return {
                "success": True,
                "plugin_id": plugin.id,
                "is_active": plugin.is_active,
                "message": f"Plugin '{plugin.name}' created successfully",
            }

        except Exception as e:
            return {"success": False, "error": f"Database save error: {str(e)}"}

    def get_few_shot_context(self, prompt: str) -> str:
        """Get the few-shot learning context that will be used for generation."""
        return code_generator.get_few_shot_context(prompt)


# Global instance
create_plugin_tool = CreatePluginTool()
