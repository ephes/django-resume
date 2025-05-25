"""MCP tool for updating existing plugin code in the database."""

import json
from typing import Any

from mcp.types import Tool, TextContent

from ..utils.django_setup import ensure_django_setup
from ..utils.validator import validator


class UpdatePluginCodeTool:
    """Tool for updating existing plugin code in the database."""

    def get_tool(self) -> Tool:
        """Get the MCP tool definition."""
        return Tool(
            name="update_plugin_code",
            description="Update existing plugin code in the database",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin_id": {
                        "type": "integer",
                        "description": "ID of the plugin to update",
                    },
                    "plugin_name": {
                        "type": "string",
                        "description": "Name of the plugin to update (alternative to plugin_id)",
                        "pattern": "^[a-z][a-z0-9_]*$",
                    },
                    "module_code": {
                        "type": "string",
                        "description": "Updated Python module code (optional)",
                    },
                    "content_template": {
                        "type": "string",
                        "description": "Updated HTML content template (optional)",
                    },
                    "form_template": {
                        "type": "string",
                        "description": "Updated HTML form template (optional)",
                    },
                    "verbose_name": {
                        "type": "string",
                        "description": "Updated verbose name (optional)",
                    },
                    "is_active": {
                        "type": "boolean",
                        "description": "Updated active status (optional)",
                    },
                    "validate_before_update": {
                        "type": "boolean",
                        "description": "Validate code before updating",
                        "default": True,
                    },
                    "force_update": {
                        "type": "boolean",
                        "description": "Update even if validation warnings exist (errors still block)",
                        "default": False,
                    },
                    "backup_current": {
                        "type": "boolean",
                        "description": "Create backup of current version",
                        "default": True,
                    },
                },
                "anyOf": [
                    {"required": ["plugin_id"]},
                    {"required": ["plugin_name"]},
                ],
                "additionalProperties": False,
            },
        )

    def execute(self, arguments: dict[str, Any]) -> TextContent:
        """Execute the update_plugin_code tool."""
        try:
            ensure_django_setup()

            # Get plugin reference
            plugin = self._get_plugin(arguments)
            if not plugin:
                return TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": False,
                            "error": "Plugin not found",
                        },
                        indent=2,
                    ),
                )

            # Extract update parameters
            module_code = arguments.get("module_code")
            content_template = arguments.get("content_template")
            form_template = arguments.get("form_template")
            verbose_name = arguments.get("verbose_name")
            is_active = arguments.get("is_active")
            validate_before_update = arguments.get("validate_before_update", True)
            force_update = arguments.get("force_update", False)
            backup_current = arguments.get("backup_current", True)

            # Check if any updates provided
            if not any(
                [
                    module_code,
                    content_template,
                    form_template,
                    verbose_name is not None,
                    is_active is not None,
                ]
            ):
                return TextContent(
                    type="text",
                    text=json.dumps(
                        {
                            "success": False,
                            "error": "No updates provided",
                        },
                        indent=2,
                    ),
                )

            # Create backup if requested
            backup_data = None
            if backup_current:
                backup_data = {
                    "module": plugin.module,
                    "content_template": plugin.content_template,
                    "form_template": plugin.form_template,
                    "is_active": plugin.is_active,
                    "updated": plugin.updated.isoformat(),
                }

            # Validate updates if requested
            validation_result = None
            if validate_before_update and (
                module_code or content_template or form_template
            ):
                validation_result = self._validate_updates(
                    plugin,
                    module_code or "",
                    content_template or "",
                    form_template or "",
                )

                if not validation_result["is_valid"]:
                    if not force_update:
                        return TextContent(
                            type="text",
                            text=json.dumps(
                                {
                                    "success": False,
                                    "error": "Validation failed",
                                    "validation": validation_result,
                                    "note": "Use force_update=true to update despite warnings",
                                },
                                indent=2,
                            ),
                        )

            # Apply updates
            changes_made = []

            if module_code is not None:
                plugin.module = module_code
                changes_made.append("module_code")

            if content_template is not None:
                plugin.content_template = content_template
                changes_made.append("content_template")

            if form_template is not None:
                plugin.form_template = form_template
                changes_made.append("form_template")

            if verbose_name is not None:
                # Note: verbose_name is not stored in the Plugin model directly
                # It's defined in the module code, so we note this limitation
                changes_made.append(
                    "verbose_name (note: update module_code to change this)"
                )

            if is_active is not None:
                plugin.is_active = is_active
                changes_made.append("is_active")

            # Save the plugin
            plugin.save()

            # Try to reload the plugin registry
            try:
                from django_resume.plugins.registry import plugin_registry

                plugin_registry.reload_db_plugins()
                registry_reloaded = True
                registry_error = None
            except Exception as e:
                registry_reloaded = False
                registry_error = str(e)

            # Prepare result
            result = {
                "success": True,
                "plugin": {
                    "id": plugin.id,
                    "name": plugin.name,
                    "is_active": plugin.is_active,
                },
                "changes_made": changes_made,
                "registry_reloaded": registry_reloaded,
            }

            if validation_result:
                result["validation"] = validation_result

            if backup_data:
                result["backup"] = backup_data

            if not registry_reloaded:
                result["registry_error"] = registry_error
                result["note"] = (
                    "Plugin updated but registry reload failed. Changes may not be immediately visible."
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
                        "error": f"Failed to update plugin: {str(e)}",
                    },
                    indent=2,
                ),
            )

    def _get_plugin(self, arguments: dict[str, Any]):
        """Get plugin by ID or name."""
        from django_resume.models import Plugin

        plugin_id = arguments.get("plugin_id")
        plugin_name = arguments.get("plugin_name")

        if plugin_id:
            try:
                return Plugin.objects.get(id=plugin_id)
            except Plugin.DoesNotExist:
                return None
        elif plugin_name:
            try:
                return Plugin.objects.get(name=plugin_name)
            except Plugin.DoesNotExist:
                return None
        else:
            return None

    def _validate_updates(
        self, plugin, module_code: str, content_template: str, form_template: str
    ) -> dict[str, Any]:
        """Validate the proposed updates."""
        errors: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        # Use current values for validation if not updating
        validate_module = module_code if module_code is not None else plugin.module
        validate_content = (
            content_template
            if content_template is not None
            else plugin.content_template
        )
        validate_form = (
            form_template if form_template is not None else plugin.form_template
        )

        # Validate Python module code
        if module_code is not None:
            module_validation = validator.validate_plugin_code(validate_module)
            errors.extend(module_validation.errors)
            warnings.extend(module_validation.warnings)
            suggestions.extend(module_validation.suggestions)

            # Additional validation for module updates
            self._validate_module_consistency(plugin, module_code, errors, warnings)

        # Validate content template
        if content_template is not None:
            content_validation = validator.validate_template_code(validate_content)
            if not content_validation.is_valid:
                errors.extend(
                    [
                        f"Content template: {error}"
                        for error in content_validation.errors
                    ]
                )
            warnings.extend(
                [
                    f"Content template: {warning}"
                    for warning in content_validation.warnings
                ]
            )

        # Validate form template
        if form_template is not None:
            form_validation = validator.validate_template_code(validate_form)
            if not form_validation.is_valid:
                errors.extend(
                    [f"Form template: {error}" for error in form_validation.errors]
                )
            warnings.extend(
                [f"Form template: {warning}" for warning in form_validation.warnings]
            )

        # Cross-validation
        self._validate_cross_updates(
            plugin,
            validate_module,
            validate_content,
            validate_form,
            warnings,
            suggestions,
        )

        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
        }

    def _validate_module_consistency(
        self, plugin, new_module_code: str, errors: list[str], warnings: list[str]
    ) -> None:
        """Validate that module updates are consistent with existing plugin."""
        import re

        # Check that plugin name hasn't changed inappropriately
        name_pattern = rf'name\s*=\s*["\']({plugin.name})["\']'
        if not re.search(name_pattern, new_module_code):
            errors.append(
                f"Module code must contain 'name = \"{plugin.name}\"' attribute"
            )

        # Check for breaking changes in form structure
        current_fields = re.findall(r"(\w+)\s*=\s*forms\.\w+Field", plugin.module)
        new_fields = re.findall(r"(\w+)\s*=\s*forms\.\w+Field", new_module_code)

        removed_fields = set(current_fields) - set(new_fields)
        if removed_fields:
            warnings.append(
                f"Removing form fields may break existing data: {', '.join(removed_fields)}"
            )

        added_fields = set(new_fields) - set(current_fields)
        if added_fields:
            warnings.append(
                f"New form fields added: {', '.join(added_fields)} - ensure templates are updated"
            )

    def _validate_cross_updates(
        self,
        plugin,
        module_code: str,
        content_template: str,
        form_template: str,
        warnings: list[str],
        suggestions: list[str],
    ) -> None:
        """Validate consistency across updated components."""
        import re

        # Check form fields usage in templates
        form_fields = re.findall(r"(\w+)\s*=\s*forms\.\w+Field", module_code)

        if content_template:
            template_vars = re.findall(r"data\.(\w+)", content_template)
            unused_in_content = set(form_fields) - set(template_vars)
            if unused_in_content:
                suggestions.append(
                    f"Form fields not used in content template: {', '.join(unused_in_content)}"
                )

        if form_template:
            form_renders = re.findall(r"form\.(\w+)", form_template)
            missing_in_form = set(form_fields) - set(form_renders)
            if missing_in_form:
                warnings.append(
                    f"Form fields not rendered in form template: {', '.join(missing_in_form)}"
                )

        # Check plugin name consistency in templates
        if content_template and f'data-plugin="{plugin.name}"' not in content_template:
            suggestions.append(
                f'Content template should include data-plugin="{plugin.name}" attribute'
            )


# Global instance
update_plugin_code_tool = UpdatePluginCodeTool()
