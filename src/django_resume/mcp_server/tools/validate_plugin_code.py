"""MCP tool for validating plugin code without creating it."""

import json
import ast
import re
from typing import Any

from mcp.types import Tool, TextContent

from ..utils.django_setup import ensure_django_setup
from ..utils.validator import validator


class ValidatePluginCodeTool:
    """Tool for validating plugin code without creating it in the database."""

    def get_tool(self) -> Tool:
        """Get the MCP tool definition."""
        return Tool(
            name="validate_plugin_code",
            description="Validate plugin code for security, syntax, and structure without creating it",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Plugin name to validate",
                        "pattern": "^[a-z][a-z0-9_]*$",
                    },
                    "module_code": {
                        "type": "string",
                        "description": "Python module code to validate",
                    },
                    "content_template": {
                        "type": "string",
                        "description": "HTML content template to validate",
                        "default": "",
                    },
                    "form_template": {
                        "type": "string",
                        "description": "HTML form template to validate",
                        "default": "",
                    },
                    "verbose": {
                        "type": "boolean",
                        "description": "Include detailed analysis and suggestions",
                        "default": True,
                    },
                    "check_name_availability": {
                        "type": "boolean",
                        "description": "Check if plugin name is available in database",
                        "default": False,
                    },
                },
                "required": ["module_code"],
            },
        )

    def execute(self, arguments: dict[str, Any]) -> TextContent:
        """Execute the validate_plugin_code tool."""
        try:
            ensure_django_setup()

            name = arguments.get("name", "")
            module_code = arguments["module_code"]
            content_template = arguments.get("content_template", "")
            form_template = arguments.get("form_template", "")
            verbose = arguments.get("verbose", True)
            check_name_availability = arguments.get("check_name_availability", False)

            # Perform comprehensive validation
            result = self._comprehensive_validation(
                name,
                module_code,
                content_template,
                form_template,
                verbose,
                check_name_availability,
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
                        "error": f"Validation failed: {str(e)}",
                    },
                    indent=2,
                ),
            )

    def _comprehensive_validation(
        self,
        name: str,
        module_code: str,
        content_template: str,
        form_template: str,
        verbose: bool,
        check_name_availability: bool,
    ) -> dict[str, Any]:
        """Perform comprehensive validation of all plugin components."""

        validation_result: dict[str, Any] = {
            "success": True,
            "overall_valid": True,
            "components": {},
            "summary": {
                "total_errors": 0,
                "total_warnings": 0,
                "total_suggestions": 0,
            },
        }

        # Validate plugin name if provided
        if name:
            name_validation = self._validate_plugin_name(name, check_name_availability)
            validation_result["components"]["name"] = name_validation
            validation_result["summary"]["total_errors"] += len(
                name_validation["errors"]
            )
            validation_result["summary"]["total_warnings"] += len(
                name_validation["warnings"]
            )

        # Validate Python module code
        module_validation = self._validate_module_code(module_code, name, verbose)
        validation_result["components"]["module"] = module_validation
        validation_result["summary"]["total_errors"] += len(module_validation["errors"])
        validation_result["summary"]["total_warnings"] += len(
            module_validation["warnings"]
        )
        validation_result["summary"]["total_suggestions"] += len(
            module_validation["suggestions"]
        )

        # Validate templates if provided
        if content_template:
            content_validation = self._validate_template(
                content_template, "content", verbose
            )
            validation_result["components"]["content_template"] = content_validation
            validation_result["summary"]["total_errors"] += len(
                content_validation["errors"]
            )
            validation_result["summary"]["total_warnings"] += len(
                content_validation["warnings"]
            )

        if form_template:
            form_validation = self._validate_template(form_template, "form", verbose)
            validation_result["components"]["form_template"] = form_validation
            validation_result["summary"]["total_errors"] += len(
                form_validation["errors"]
            )
            validation_result["summary"]["total_warnings"] += len(
                form_validation["warnings"]
            )

        # Cross-component validation
        if verbose:
            cross_validation = self._cross_component_validation(
                name, module_code, content_template, form_template
            )
            validation_result["components"]["cross_validation"] = cross_validation
            validation_result["summary"]["total_warnings"] += len(
                cross_validation["warnings"]
            )
            validation_result["summary"]["total_suggestions"] += len(
                cross_validation["suggestions"]
            )

        # Determine overall validity
        validation_result["overall_valid"] = (
            validation_result["summary"]["total_errors"] == 0
        )

        # Add recommendations if verbose
        if verbose:
            validation_result["recommendations"] = self._generate_recommendations(
                validation_result
            )

        return validation_result

    def _validate_plugin_name(
        self, name: str, check_availability: bool
    ) -> dict[str, Any]:
        """Validate plugin name."""
        errors: list[str] = []
        warnings: list[str] = []

        # Basic name validation
        if not name:
            errors.append("Plugin name is required")
            return {"valid": False, "errors": errors, "warnings": warnings}

        if not re.match(r"^[a-z][a-z0-9_]*$", name):
            errors.append(
                "Plugin name must start with lowercase letter and contain only lowercase letters, numbers, and underscores"
            )

        if len(name) < 2:
            errors.append("Plugin name must be at least 2 characters long")
        elif len(name) > 50:
            errors.append("Plugin name must be 50 characters or less")

        if name.startswith("_") or name.endswith("_"):
            errors.append("Plugin name cannot start or end with underscore")

        # Check for reserved words
        python_keywords = [
            "and",
            "as",
            "assert",
            "break",
            "class",
            "continue",
            "def",
            "del",
            "elif",
            "else",
            "except",
            "exec",
            "finally",
            "for",
            "from",
            "global",
            "if",
            "import",
            "in",
            "is",
            "lambda",
            "not",
            "or",
            "pass",
            "print",
            "raise",
            "return",
            "try",
            "while",
            "with",
            "yield",
        ]

        if name in python_keywords:
            errors.append(f"Plugin name '{name}' is a Python keyword")

        # Check availability in database
        if check_availability and not errors:
            try:
                from django_resume.models import Plugin

                if Plugin.objects.filter(name=name).exists():
                    errors.append(
                        f"Plugin with name '{name}' already exists in database"
                    )
            except Exception as e:
                warnings.append(f"Could not check name availability: {str(e)}")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_module_code(
        self, module_code: str, name: str, verbose: bool
    ) -> dict[str, Any]:
        """Validate Python module code."""
        errors: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        # Basic syntax validation
        try:
            ast.parse(module_code)
        except SyntaxError as e:
            errors.append(f"Syntax error: {str(e)}")
            return {
                "valid": False,
                "errors": errors,
                "warnings": warnings,
                "suggestions": suggestions,
            }

        # Use the existing validator
        validation = validator.validate_plugin_code(module_code)
        errors.extend(validation.errors)
        warnings.extend(validation.warnings)
        suggestions.extend(validation.suggestions)

        # Additional detailed analysis if verbose
        if verbose:
            detailed_analysis = self._detailed_module_analysis(module_code, name)
            warnings.extend(detailed_analysis["warnings"])
            suggestions.extend(detailed_analysis["suggestions"])

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
        }

    def _validate_template(
        self, template_code: str, template_type: str, verbose: bool
    ) -> dict[str, Any]:
        """Validate HTML template code."""
        errors: list[str] = []
        warnings: list[str] = []
        suggestions: list[str] = []

        # Use the existing template validator
        validation = validator.validate_template_code(template_code)
        errors.extend(validation.errors)
        warnings.extend(validation.warnings)

        # Additional template-specific analysis
        if verbose:
            template_analysis = self._detailed_template_analysis(
                template_code, template_type
            )
            warnings.extend(template_analysis["warnings"])
            suggestions.extend(template_analysis["suggestions"])

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "suggestions": suggestions,
        }

    def _detailed_module_analysis(self, module_code: str, name: str) -> dict[str, Any]:
        """Perform detailed analysis of module code."""
        warnings: list[str] = []
        suggestions: list[str] = []

        lines = module_code.split("\n")

        # Analyze imports
        imports = [
            line.strip()
            for line in lines
            if line.strip().startswith(("import ", "from "))
        ]
        if len(imports) < 2:
            suggestions.append(
                "Consider adding more specific imports for better code clarity"
            )

        # Analyze docstrings
        if '"""' not in module_code and "'''" not in module_code:
            suggestions.append(
                "Consider adding docstrings to classes and methods for better documentation"
            )

        # Analyze form fields
        form_fields = re.findall(r"(\w+)\s*=\s*forms\.(\w+Field)", module_code)
        if not form_fields:
            warnings.append("No form fields detected - plugin may not be functional")
        else:
            # Check for help_text usage
            help_text_count = module_code.count("help_text")
            if help_text_count < len(form_fields) / 2:
                suggestions.append(
                    "Consider adding help_text to more form fields for better user experience"
                )

        # Check for proper class naming
        class_matches = re.findall(r"class\s+(\w+)", module_code)
        for class_name in class_matches:
            if not class_name.endswith(("Form", "Plugin")):
                warnings.append(
                    f"Class '{class_name}' doesn't follow naming convention (should end with 'Form' or 'Plugin')"
                )

        # Check for proper plugin name attribute
        if (
            name
            and f'name = "{name}"' not in module_code
            and f"name = '{name}'" not in module_code
        ):
            warnings.append(f"Plugin class should have name = '{name}' attribute")

        return {"warnings": warnings, "suggestions": suggestions}

    def _detailed_template_analysis(
        self, template_code: str, template_type: str
    ) -> dict[str, Any]:
        """Perform detailed analysis of template code."""
        warnings: list[str] = []
        suggestions: list[str] = []

        # Check for accessibility features
        if "aria-" not in template_code.lower():
            suggestions.append(
                "Consider adding ARIA attributes for better accessibility"
            )

        if "alt=" not in template_code.lower() and "<img" in template_code.lower():
            warnings.append("Images should have alt attributes for accessibility")

        # Check for responsive design
        if "class=" in template_code and "col-" not in template_code:
            suggestions.append(
                "Consider using responsive grid classes for better mobile experience"
            )

        # Template-specific checks
        if template_type == "content":
            if "contenteditable" not in template_code.lower():
                suggestions.append(
                    "Content templates should support contenteditable for inline editing"
                )

            if "show_edit_button" not in template_code:
                suggestions.append(
                    "Content templates should conditionally show edit buttons"
                )

        elif template_type == "form":
            if "hx-" not in template_code.lower():
                suggestions.append(
                    "Form templates should use HTMX for dynamic interactions"
                )

            if (
                "csrf_token" not in template_code
                and "csrfmiddlewaretoken" not in template_code
            ):
                warnings.append("Forms should include CSRF protection")

        # Check for template variables
        variables = re.findall(r"\{\{\s*(\w+(?:\.\w+)*)", template_code)
        if not variables:
            warnings.append(
                "Template doesn't appear to use any variables - may be static content"
            )

        return {"warnings": warnings, "suggestions": suggestions}

    def _cross_component_validation(
        self, name: str, module_code: str, content_template: str, form_template: str
    ) -> dict[str, Any]:
        """Validate consistency across all components."""
        warnings: list[str] = []
        suggestions: list[str] = []

        # Check consistency between form fields and templates
        if module_code and content_template:
            form_fields = re.findall(r"(\w+)\s*=\s*forms\.\w+Field", module_code)
            template_variables = re.findall(r"data\.(\w+)", content_template)

            # Check if form fields are used in template
            unused_fields = set(form_fields) - set(template_variables)
            if unused_fields:
                suggestions.append(
                    f"Form fields not used in content template: {', '.join(unused_fields)}"
                )

        # Check for plugin name consistency
        if name and module_code:
            if (
                f'data-plugin="{name}"' not in content_template
                and f"data-plugin='{name}'" not in content_template
            ):
                suggestions.append(
                    "Content template should include data-plugin attribute for JavaScript targeting"
                )

        # Check form-template consistency
        if module_code and form_template:
            form_fields = re.findall(r"(\w+)\s*=\s*forms\.\w+Field", module_code)
            form_renders = re.findall(r"form\.(\w+)", form_template)

            missing_renders = set(form_fields) - set(form_renders)
            if missing_renders:
                warnings.append(
                    f"Form fields not rendered in form template: {', '.join(missing_renders)}"
                )

        return {"warnings": warnings, "suggestions": suggestions}

    def _generate_recommendations(self, validation_result: dict[str, Any]) -> list[str]:
        """Generate high-level recommendations based on validation results."""
        recommendations: list[str] = []

        total_errors = validation_result["summary"]["total_errors"]
        total_warnings = validation_result["summary"]["total_warnings"]

        if total_errors > 0:
            recommendations.append(
                f"Fix {total_errors} error(s) before creating the plugin"
            )

        if total_warnings > 5:
            recommendations.append(
                "Consider addressing warnings to improve plugin quality"
            )

        # Component-specific recommendations
        components = validation_result["components"]

        if "module" in components and not components["module"]["valid"]:
            recommendations.append(
                "Focus on fixing Python module errors first - these are critical"
            )

        if (
            "content_template" in components
            and components["content_template"]["warnings"]
        ):
            recommendations.append(
                "Improve content template for better user experience"
            )

        if "form_template" in components and components["form_template"]["warnings"]:
            recommendations.append("Enhance form template for better functionality")

        if not recommendations:
            recommendations.append("Plugin validation passed! Ready for creation.")

        return recommendations


# Global instance
validate_plugin_code_tool = ValidatePluginCodeTool()
