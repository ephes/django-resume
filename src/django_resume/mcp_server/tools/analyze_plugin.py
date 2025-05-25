"""MCP tool for analyzing django-resume plugins."""

import json
from typing import Dict, Any, List
import re

from mcp.types import Tool, TextContent

from ..utils.django_setup import ensure_django_setup
from ..utils.code_generator import plugin_analyzer
from ..utils.validator import validator

# For lazy loading - try to get the ensure_django function
try:
    from django_resume.entrypoints.mcp_server_lazy import ensure_django
except ImportError:
    # Fallback to the regular Django setup
    ensure_django = ensure_django_setup


class AnalyzePluginTool:
    """Tool for analyzing django-resume plugins."""

    def get_tool(self) -> Tool:
        """Get the MCP tool definition."""
        return Tool(
            name="analyze_plugin",
            description="Analyze a specific django-resume plugin structure and code",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin_name": {
                        "type": "string",
                        "description": "Name of the plugin to analyze",
                    },
                    "plugin_type": {
                        "type": "string",
                        "description": "Type of plugin to analyze",
                        "enum": ["file_based", "database", "auto"],
                        "default": "auto",
                    },
                    "include_validation": {
                        "type": "boolean",
                        "description": "Include code validation results",
                        "default": True,
                    },
                    "include_suggestions": {
                        "type": "boolean",
                        "description": "Include improvement suggestions",
                        "default": True,
                    },
                    "include_templates": {
                        "type": "boolean",
                        "description": "Include template analysis",
                        "default": True,
                    },
                    "compare_with": {
                        "type": "string",
                        "description": "Optional: Compare with another plugin",
                        "default": "",
                    },
                },
                "required": ["plugin_name"],
            },
        )

    def execute(self, arguments: Dict[str, Any]) -> TextContent:
        """Execute the analyze_plugin tool."""
        try:
            ensure_django_setup()

            plugin_name = arguments["plugin_name"]
            plugin_type = arguments.get("plugin_type", "auto")
            include_validation = arguments.get("include_validation", True)
            include_suggestions = arguments.get("include_suggestions", True)
            include_templates = arguments.get("include_templates", True)
            compare_with = arguments.get("compare_with", "")

            # Try to find and analyze the plugin
            analysis_result = self._analyze_plugin(
                plugin_name,
                plugin_type,
                include_validation,
                include_suggestions,
                include_templates,
            )

            if not analysis_result["success"]:
                return TextContent(
                    type="text", text=json.dumps(analysis_result, indent=2)
                )

            # Add comparison if requested
            if compare_with:
                comparison_result = self._compare_plugins(plugin_name, compare_with)
                analysis_result["comparison"] = comparison_result

            return TextContent(type="text", text=json.dumps(analysis_result, indent=2))

        except Exception as e:
            return TextContent(
                type="text",
                text=json.dumps(
                    {"success": False, "error": f"Tool execution error: {str(e)}"},
                    indent=2,
                ),
            )

    def _analyze_plugin(
        self,
        plugin_name: str,
        plugin_type: str,
        include_validation: bool,
        include_suggestions: bool,
        include_templates: bool,
    ) -> Dict[str, Any]:
        """Analyze a specific plugin."""

        # Try file-based first
        file_based_analysis = None
        database_analysis = None

        if plugin_type in ["file_based", "auto"]:
            file_based_analysis = plugin_analyzer.analyze_plugin_by_name(plugin_name)

        if plugin_type in ["database", "auto"]:
            database_analysis = self._analyze_database_plugin(plugin_name)

        # Determine which analysis to use
        analysis_data = None
        source_type = None

        if file_based_analysis and "error" not in file_based_analysis:
            analysis_data = file_based_analysis
            source_type = "file_based"
        elif database_analysis and "error" not in database_analysis:
            analysis_data = database_analysis
            source_type = "database"
        else:
            return {
                "success": False,
                "error": f"Plugin '{plugin_name}' not found in file system or database",
                "file_based_error": file_based_analysis.get("error")
                if file_based_analysis
                else "Not checked",
                "database_error": database_analysis.get("error")
                if database_analysis
                else "Not checked",
            }

        # Build analysis result
        result = {
            "success": True,
            "plugin_name": plugin_name,
            "source_type": source_type,
            "basic_info": {
                "name": analysis_data.get("name", plugin_name),
                "verbose_name": analysis_data.get("verbose_name", ""),
                "has_prompt": bool(analysis_data.get("prompt", "")),
                "has_module": bool(analysis_data.get("module_source", "")),
                "has_form": bool(analysis_data.get("form_source", "")),
            },
        }

        # Add code structure analysis
        if analysis_data.get("module_source"):
            result["code_structure"] = self._analyze_code_structure(
                analysis_data["module_source"]
            )

        # Add validation results
        if include_validation and analysis_data.get("module_source"):
            validation = validator.validate_plugin_code(analysis_data["module_source"])
            result["validation"] = {
                "is_valid": validation.is_valid,
                "errors": validation.errors,
                "warnings": validation.warnings,
                "suggestions": validation.suggestions,
            }

        # Add template analysis
        if include_templates and analysis_data.get("templates"):
            result["templates"] = self._analyze_templates(analysis_data["templates"])

        # Add improvement suggestions
        if include_suggestions:
            result["suggestions"] = self._generate_suggestions(analysis_data)

        # Add database-specific info
        if source_type == "database":
            result["database_info"] = {
                "id": analysis_data.get("id"),
                "model": analysis_data.get("model"),
                "is_active": analysis_data.get("is_active"),
                "plugin_data": analysis_data.get("plugin_data", {}),
            }

        return result

    def _analyze_database_plugin(self, plugin_name: str) -> Dict[str, Any]:
        """Analyze a database plugin."""
        try:
            from django_resume.models import Plugin

            plugin = Plugin.objects.get(name=plugin_name)
            return {
                "id": plugin.id,
                "name": plugin.name,
                "verbose_name": plugin.name.replace("_", " ").title(),
                "prompt": plugin.prompt,
                "module_source": plugin.module,
                "form_source": "",  # Extract from module if needed
                "templates": {
                    "main_content": plugin.content_template,
                    "form_content": plugin.form_template,
                },
                "model": plugin.model,
                "is_active": plugin.is_active,
                "plugin_data": plugin.plugin_data,
            }
        except Exception as e:
            return {"error": f"Database plugin not found: {str(e)}"}

    def _analyze_code_structure(self, code: str) -> Dict[str, Any]:
        """Analyze the structure of plugin code."""
        import ast

        try:
            tree = ast.parse(code)

            # Find classes
            classes = [
                node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)
            ]
            form_classes = [cls.name for cls in classes if cls.name.endswith("Form")]
            plugin_classes = [
                cls.name for cls in classes if cls.name.endswith("Plugin")
            ]

            # Find form fields
            form_fields = re.findall(r"(\w+)\s*=\s*forms\.(\w+Field)", code)

            # Find imports
            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(
                            f"from {node.module} import {', '.join(alias.name for alias in node.names)}"
                        )
                elif isinstance(node, ast.Import):
                    imports.append(
                        f"import {', '.join(alias.name for alias in node.names)}"
                    )

            return {
                "classes": {
                    "form_classes": form_classes,
                    "plugin_classes": plugin_classes,
                    "total_classes": len(classes),
                },
                "form_fields": [
                    {"name": name, "type": field_type}
                    for name, field_type in form_fields
                ],
                "imports": imports,
                "lines_of_code": len(code.split("\n")),
                "has_inheritance": any(
                    "SimplePlugin" in line for line in code.split("\n")
                ),
            }
        except Exception as e:
            return {"error": f"Code analysis failed: {str(e)}"}

    def _analyze_templates(self, templates: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze plugin templates."""
        analysis = {}

        for template_type, content in templates.items():
            if content and isinstance(content, str):
                template_analysis = {
                    "length": len(content),
                    "has_edit_button": "edit_url" in content,
                    "has_contenteditable": "contenteditable" in content.lower(),
                    "has_form_elements": any(
                        tag in content.lower()
                        for tag in ["<form", "<input", "<textarea"]
                    ),
                    "has_htmx": "hx-" in content.lower(),
                    "template_tags": len(re.findall(r"\{\%.*?\%\}", content)),
                    "variables": len(re.findall(r"\{\{.*?\}\}", content)),
                }

                # Validate template
                validation = validator.validate_template_code(content)
                template_analysis["validation"] = {
                    "is_valid": validation.is_valid,
                    "errors": validation.errors,
                    "warnings": validation.warnings,
                }

                analysis[template_type] = template_analysis

        return analysis

    def _generate_suggestions(self, analysis_data: Dict[str, Any]) -> List[str]:
        """Generate improvement suggestions for the plugin."""
        suggestions = []

        # Check for prompt
        if not analysis_data.get("prompt"):
            suggestions.append(
                "Consider adding a prompt to help with LLM-based regeneration"
            )

        # Check module code
        module_source = analysis_data.get("module_source", "")
        if module_source:
            if "initial=" not in module_source:
                suggestions.append(
                    "Consider adding initial values to form fields for better UX"
                )

            if "verbose_name" not in module_source:
                suggestions.append("Consider adding a verbose_name to the plugin class")

            if not re.search(r"max_length=\d+", module_source):
                suggestions.append("Consider adding max_length to CharField fields")

        # Check templates
        templates = analysis_data.get("templates", {})
        for template_type, content in templates.items():
            if isinstance(content, str) and content:
                if "contenteditable" not in content.lower():
                    suggestions.append(
                        f"{template_type} template: Add contenteditable for inline editing"
                    )

                if "hx-" not in content.lower():
                    suggestions.append(
                        f"{template_type} template: Consider adding HTMX for dynamic updates"
                    )

        return suggestions

    def _compare_plugins(self, plugin1_name: str, plugin2_name: str) -> Dict[str, Any]:
        """Compare two plugins."""
        try:
            # Analyze both plugins
            plugin1_analysis = self._analyze_plugin(
                plugin1_name, "auto", True, False, True
            )
            plugin2_analysis = self._analyze_plugin(
                plugin2_name, "auto", True, False, True
            )

            if not plugin1_analysis["success"] or not plugin2_analysis["success"]:
                return {
                    "success": False,
                    "error": "One or both plugins could not be analyzed",
                }

            # Compare structures
            comparison = {
                "success": True,
                "similarities": [],
                "differences": [],
                "recommendations": [],
            }

            # Compare form fields
            fields1 = plugin1_analysis.get("code_structure", {}).get("form_fields", [])
            fields2 = plugin2_analysis.get("code_structure", {}).get("form_fields", [])

            field_names1 = {f["name"] for f in fields1}
            field_names2 = {f["name"] for f in fields2}

            common_fields = field_names1.intersection(field_names2)
            if common_fields:
                comparison["similarities"].append(
                    f"Common form fields: {', '.join(common_fields)}"
                )

            unique1 = field_names1 - field_names2
            unique2 = field_names2 - field_names1

            if unique1:
                comparison["differences"].append(
                    f"{plugin1_name} has unique fields: {', '.join(unique1)}"
                )
            if unique2:
                comparison["differences"].append(
                    f"{plugin2_name} has unique fields: {', '.join(unique2)}"
                )

            # Compare validation results
            val1 = plugin1_analysis.get("validation", {})
            val2 = plugin2_analysis.get("validation", {})

            if val1.get("is_valid") and not val2.get("is_valid"):
                comparison["recommendations"].append(
                    f"{plugin2_name} could benefit from fixing validation errors like {plugin1_name}"
                )
            elif val2.get("is_valid") and not val1.get("is_valid"):
                comparison["recommendations"].append(
                    f"{plugin1_name} could benefit from fixing validation errors like {plugin2_name}"
                )

            return comparison

        except Exception as e:
            return {"success": False, "error": f"Comparison failed: {str(e)}"}


# Global instance
analyze_plugin_tool = AnalyzePluginTool()
