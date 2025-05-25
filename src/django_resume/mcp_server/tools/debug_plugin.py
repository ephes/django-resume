"""MCP tool for debugging plugin issues and providing assistance."""

import json
import re
from typing import Any

from mcp.types import Tool, TextContent

from ..utils.django_setup import ensure_django_setup
from ..utils.validator import validator


class DebugPluginTool:
    """Tool for debugging plugin issues and providing targeted assistance."""

    def get_tool(self) -> Tool:
        """Get the MCP tool definition."""
        return Tool(
            name="debug_plugin",
            description="Debug plugin issues and get targeted assistance for fixes",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin_id": {
                        "type": "integer",
                        "description": "ID of the plugin to debug",
                    },
                    "plugin_name": {
                        "type": "string",
                        "description": "Name of the plugin to debug (alternative to plugin_id)",
                    },
                    "error_message": {
                        "type": "string",
                        "description": "Error message or description of the issue",
                    },
                    "error_type": {
                        "type": "string",
                        "enum": [
                            "syntax",
                            "runtime",
                            "template",
                            "form",
                            "display",
                            "save",
                            "validation",
                            "other",
                        ],
                        "description": "Type of error encountered",
                        "default": "other",
                    },
                    "browser_console_errors": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "JavaScript console errors from browser testing",
                        "default": [],
                    },
                    "expected_behavior": {
                        "type": "string",
                        "description": "What should happen vs what is happening",
                    },
                    "steps_to_reproduce": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Steps to reproduce the issue",
                        "default": [],
                    },
                    "include_suggestions": {
                        "type": "boolean",
                        "description": "Include specific code suggestions for fixes",
                        "default": True,
                    },
                },
                "anyOf": [
                    {"required": ["plugin_id"]},
                    {"required": ["plugin_name"]},
                    {"required": ["error_message"]},
                ],
            },
        )

    def execute(self, arguments: dict[str, Any]) -> TextContent:
        """Execute the debug_plugin tool."""
        try:
            ensure_django_setup()

            plugin = self._get_plugin(arguments)
            error_message = arguments.get("error_message", "")
            error_type = arguments.get("error_type", "other")
            console_errors = arguments.get("browser_console_errors", [])
            expected_behavior = arguments.get("expected_behavior", "")
            steps_to_reproduce = arguments.get("steps_to_reproduce", [])
            include_suggestions = arguments.get("include_suggestions", True)

            # Analyze the issue
            debug_result = self._analyze_plugin_issue(
                plugin=plugin,
                error_message=error_message,
                error_type=error_type,
                console_errors=console_errors,
                expected_behavior=expected_behavior,
                steps_to_reproduce=steps_to_reproduce,
                include_suggestions=include_suggestions,
            )

            return TextContent(
                type="text",
                text=json.dumps(debug_result, indent=2),
            )

        except Exception as e:
            return TextContent(
                type="text",
                text=json.dumps(
                    {
                        "success": False,
                        "error": f"Debug analysis failed: {str(e)}",
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

    def _analyze_plugin_issue(
        self,
        plugin,
        error_message: str,
        error_type: str,
        console_errors: list[str],
        expected_behavior: str,
        steps_to_reproduce: list[str],
        include_suggestions: bool,
    ) -> dict[str, Any]:
        """Analyze plugin issue and provide debugging assistance."""

        debug_result = {
            "success": True,
            "plugin_info": {},
            "issue_analysis": {},
            "potential_causes": [],
            "debugging_steps": [],
            "code_suggestions": [],
            "related_resources": [],
        }

        # Add plugin info if available
        if plugin:
            debug_result["plugin_info"] = {
                "id": plugin.id,
                "name": plugin.name,
                "is_active": plugin.is_active,
                "created": plugin.created.isoformat(),
                "updated": plugin.updated.isoformat(),
            }

        # Analyze the issue based on error type and message
        issue_analysis = self._categorize_issue(
            error_message, error_type, console_errors
        )
        debug_result["issue_analysis"] = issue_analysis

        # Generate potential causes
        debug_result["potential_causes"] = self._identify_potential_causes(
            plugin, error_message, error_type, console_errors, issue_analysis
        )

        # Generate debugging steps
        debug_result["debugging_steps"] = self._generate_debugging_steps(
            error_type, issue_analysis, steps_to_reproduce
        )

        # Generate code suggestions if requested
        if include_suggestions and plugin:
            debug_result["code_suggestions"] = self._generate_code_suggestions(
                plugin, error_message, error_type, issue_analysis
            )

        # Add related resources
        debug_result["related_resources"] = self._get_related_resources(
            error_type, issue_analysis
        )

        return debug_result

    def _categorize_issue(
        self, error_message: str, error_type: str, console_errors: list[str]
    ) -> dict[str, Any]:
        """Categorize and analyze the issue."""
        analysis = {
            "error_type": error_type,
            "severity": "medium",
            "category": "unknown",
            "keywords": [],
            "error_patterns": [],
        }

        # Extract keywords from error message
        if error_message:
            analysis["keywords"] = re.findall(r"\b\w+\b", error_message.lower())

        # Analyze error patterns
        error_patterns = []

        if "syntax" in error_message.lower() or error_type == "syntax":
            error_patterns.append("syntax_error")
            analysis["category"] = "code_syntax"
            analysis["severity"] = "high"

        if "template" in error_message.lower() or error_type == "template":
            error_patterns.append("template_error")
            analysis["category"] = "template_rendering"

        if "form" in error_message.lower() or error_type == "form":
            error_patterns.append("form_error")
            analysis["category"] = "form_handling"

        if "csrf" in error_message.lower():
            error_patterns.append("csrf_error")
            analysis["category"] = "security"
            analysis["severity"] = "high"

        if "404" in error_message or "not found" in error_message.lower():
            error_patterns.append("not_found")
            analysis["category"] = "routing"

        if "500" in error_message or "internal server" in error_message.lower():
            error_patterns.append("server_error")
            analysis["category"] = "server_error"
            analysis["severity"] = "high"

        # Analyze console errors
        for console_error in console_errors:
            if "uncaught" in console_error.lower():
                error_patterns.append("js_uncaught_error")
                analysis["category"] = "javascript"
            if "htmx" in console_error.lower():
                error_patterns.append("htmx_error")
                analysis["category"] = "htmx"

        analysis["error_patterns"] = error_patterns
        return analysis

    def _identify_potential_causes(
        self,
        plugin,
        error_message: str,
        error_type: str,
        console_errors: list[str],
        issue_analysis: dict,
    ) -> list[str]:
        """Identify potential causes of the issue."""
        causes = []

        # Plugin-specific checks
        if plugin:
            # Check plugin code for common issues
            if plugin.module:
                module_issues = self._check_module_issues(plugin.module)
                causes.extend(module_issues)

            if plugin.content_template:
                template_issues = self._check_template_issues(
                    plugin.content_template, "content"
                )
                causes.extend(template_issues)

            if plugin.form_template:
                form_issues = self._check_template_issues(plugin.form_template, "form")
                causes.extend(form_issues)

        # Error pattern-based causes
        for pattern in issue_analysis.get("error_patterns", []):
            pattern_causes = self._get_causes_for_pattern(pattern)
            causes.extend(pattern_causes)

        # Console error analysis
        for console_error in console_errors:
            console_causes = self._analyze_console_error(console_error)
            causes.extend(console_causes)

        return list(set(causes))  # Remove duplicates

    def _check_module_issues(self, module_code: str) -> list[str]:
        """Check for common issues in module code."""
        issues = []

        # Check for missing imports
        if "from django import forms" not in module_code:
            issues.append("Missing 'from django import forms' import")

        if "from .base import" not in module_code:
            issues.append("Missing base plugin import (SimplePlugin or ListPlugin)")

        # Check for missing form class
        if not re.search(r"class\s+\w+Form\s*\(", module_code):
            issues.append("No form class defined")

        # Check for missing plugin class
        if not re.search(r"class\s+\w+Plugin\s*\(", module_code):
            issues.append("No plugin class defined")

        # Check for missing required attributes
        if "name =" not in module_code:
            issues.append("Plugin class missing 'name' attribute")

        if "form_class" not in module_code and "item_form_class" not in module_code:
            issues.append("Plugin class missing form class reference")

        return issues

    def _check_template_issues(
        self, template_code: str, template_type: str
    ) -> list[str]:
        """Check for common issues in template code."""
        issues = []

        # Check for template syntax issues
        if "{{" in template_code and "}}" not in template_code:
            issues.append(f"{template_type} template has unclosed variable tags")

        if "{%" in template_code and "%}" not in template_code:
            issues.append(f"{template_type} template has unclosed template tags")

        # Check for required elements
        if template_type == "content":
            if "data-plugin" not in template_code:
                issues.append("Content template missing data-plugin attribute")

            if "edit_url" not in template_code:
                issues.append("Content template missing edit_url for editing")

        elif template_type == "form":
            if "hx-post" not in template_code and "method=" not in template_code:
                issues.append("Form template missing form submission method")

            if "csrf" not in template_code.lower():
                issues.append("Form template may be missing CSRF protection")

        return issues

    def _get_causes_for_pattern(self, pattern: str) -> list[str]:
        """Get potential causes for specific error patterns."""
        pattern_causes = {
            "syntax_error": [
                "Python syntax error in module code",
                "Missing colons, parentheses, or indentation issues",
                "Invalid variable names or reserved word usage",
            ],
            "template_error": [
                "Django template syntax error",
                "Missing template tags or variables",
                "Template not found or incorrect path",
            ],
            "form_error": [
                "Form field validation error",
                "Missing form class or incorrect inheritance",
                "Form field type mismatch",
            ],
            "csrf_error": [
                "Missing CSRF token in form",
                "CSRF middleware not configured",
                "AJAX request without CSRF header",
            ],
            "not_found": [
                "URL routing issue",
                "Template file not found",
                "Plugin not registered or active",
            ],
            "server_error": [
                "Python exception in plugin code",
                "Database connection issue",
                "Missing dependencies or imports",
            ],
            "js_uncaught_error": [
                "JavaScript syntax error",
                "Missing JavaScript dependencies",
                "DOM element not found",
            ],
            "htmx_error": [
                "HTMX target element not found",
                "Invalid HTMX attributes",
                "Server response format issue",
            ],
        }
        return pattern_causes.get(pattern, [])

    def _analyze_console_error(self, console_error: str) -> list[str]:
        """Analyze specific console error for causes."""
        causes = []

        if "404" in console_error:
            causes.append("Resource not found - check URLs and file paths")

        if "uncaught" in console_error.lower():
            causes.append("Unhandled JavaScript exception")

        if "undefined" in console_error.lower():
            causes.append("Undefined variable or function in JavaScript")

        if "htmx" in console_error.lower():
            causes.append("HTMX configuration or response issue")

        return causes

    def _generate_debugging_steps(
        self, error_type: str, issue_analysis: dict, steps_to_reproduce: list[str]
    ) -> list[str]:
        """Generate debugging steps based on the issue."""
        steps = []

        # General validation step
        steps.append("Run validate_plugin_code tool to check for basic issues")

        # Error type specific steps
        if error_type in ["syntax", "code"]:
            steps.extend(
                [
                    "Check Python syntax in module code",
                    "Verify all imports are correct",
                    "Ensure proper class inheritance",
                    "Check for missing required attributes",
                ]
            )

        elif error_type == "template":
            steps.extend(
                [
                    "Validate template syntax with Django template validator",
                    "Check for missing template variables",
                    "Verify template file paths",
                    "Test template rendering in isolation",
                ]
            )

        elif error_type == "form":
            steps.extend(
                [
                    "Check form field definitions",
                    "Verify form validation logic",
                    "Test form submission with valid data",
                    "Check CSRF token inclusion",
                ]
            )

        elif error_type in ["display", "runtime"]:
            steps.extend(
                [
                    "Test plugin in browser with test_plugin_in_browser tool",
                    "Check browser console for JavaScript errors",
                    "Verify plugin is active and registered",
                    "Test with minimal data first",
                ]
            )

        # Add reproduction steps if provided
        if steps_to_reproduce:
            steps.append("Reproduce the issue by following these steps:")
            steps.extend([f"  - {step}" for step in steps_to_reproduce])

        return steps

    def _generate_code_suggestions(
        self, plugin, error_message: str, error_type: str, issue_analysis: dict
    ) -> list[dict]:
        """Generate specific code suggestions for fixes."""
        suggestions = []

        # Check module code issues
        if plugin.module:
            validation = validator.validate_plugin_code(plugin.module)
            if validation.errors:
                for error in validation.errors:
                    suggestion = self._error_to_code_suggestion(error, plugin.module)
                    if suggestion:
                        suggestions.append(suggestion)

        # Template-specific suggestions
        if error_type == "template" or "template" in error_message.lower():
            if plugin.content_template:
                template_suggestion = self._suggest_template_fix(
                    plugin.content_template, "content"
                )
                if template_suggestion:
                    suggestions.append(template_suggestion)

        return suggestions

    def _error_to_code_suggestion(self, error: str, module_code: str) -> dict | None:
        """Convert validation error to code suggestion."""
        if "Missing required import" in error and "forms" in error:
            return {
                "issue": error,
                "fix": "Add import statement",
                "code": "from django import forms",
                "location": "Top of module",
            }

        if "No valid Form class found" in error:
            return {
                "issue": error,
                "fix": "Add form class",
                "code": """class YourPluginForm(forms.Form):
    field_name = forms.CharField(max_length=200, required=False)""",
                "location": "After imports",
            }

        return None

    def _suggest_template_fix(
        self, template_code: str, template_type: str
    ) -> dict | None:
        """Suggest template fixes."""
        if template_type == "content" and "data-plugin" not in template_code:
            return {
                "issue": "Missing data-plugin attribute",
                "fix": "Add data-plugin attribute to container",
                "code": '<div class="plugin-content" data-plugin="{{ plugin.name }}">',
                "location": "Container div",
            }
        return None

    def _get_related_resources(
        self, error_type: str, issue_analysis: dict
    ) -> list[str]:
        """Get related documentation and schema resources."""
        resources = []

        # Always useful
        resources.extend(
            [
                "docs://guide/creating-plugins",
                "schemas://validation/plugin-requirements",
            ]
        )

        # Error type specific resources
        if error_type in ["syntax", "form"]:
            resources.extend(
                [
                    "schemas://plugin-module/simple",
                    "schemas://forms/field-types",
                    "docs://best-practices/plugin-patterns",
                ]
            )

        if error_type == "template":
            resources.extend(
                [
                    "schemas://templates/content",
                    "schemas://templates/form",
                    "docs://best-practices/form-design",
                ]
            )

        if "javascript" in issue_analysis.get("category", ""):
            resources.append("docs://best-practices/htmx-integration")

        return resources


# Global instance
debug_plugin_tool = DebugPluginTool()
