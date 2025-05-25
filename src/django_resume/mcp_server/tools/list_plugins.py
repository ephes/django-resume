"""MCP tool for listing django-resume plugins."""

import json
from typing import Any

from mcp.types import Tool, TextContent

from ..utils.django_setup import ensure_django_setup
from ..utils.code_generator import plugin_analyzer

# For lazy loading - try to get the ensure_django function
try:
    from django_resume.entrypoints.mcp_server_lazy import ensure_django
except ImportError:
    # Fallback to the regular Django setup
    ensure_django = ensure_django_setup


class ListPluginsTool:
    """Tool for listing django-resume plugins."""

    def get_tool(self) -> Tool:
        """Get the MCP tool definition."""
        return Tool(
            name="list_plugins",
            description="List all available django-resume plugins (file-based and database)",
            inputSchema={
                "type": "object",
                "properties": {
                    "plugin_type": {
                        "type": "string",
                        "description": "Filter by plugin type",
                        "enum": ["all", "file_based", "database", "active", "inactive"],
                        "default": "all",
                    },
                    "include_details": {
                        "type": "boolean",
                        "description": "Include detailed information about each plugin",
                        "default": False,
                    },
                    "include_code": {
                        "type": "boolean",
                        "description": "Include source code in the response (only with include_details=true)",
                        "default": False,
                    },
                },
                "required": [],
            },
        )

    def execute(self, arguments: dict[str, Any]) -> TextContent:
        """Execute the list_plugins tool."""
        try:
            ensure_django_setup()

            plugin_type = arguments.get("plugin_type", "all")
            include_details = arguments.get("include_details", False)
            include_code = arguments.get("include_code", False)

            response = {
                "success": True,
                "file_based_plugins": self._get_file_based_plugins(
                    include_details, include_code
                ),
                "database_plugins": self._get_database_plugins(
                    include_details, include_code
                ),
                "summary": {},
            }

            # Filter based on plugin_type
            if plugin_type == "file_based":
                response["database_plugins"] = []
            elif plugin_type == "database":
                response["file_based_plugins"] = []
            elif plugin_type in ["active", "inactive"]:
                # Filter database plugins by status
                db_plugins = response["database_plugins"]
                assert isinstance(db_plugins, list)
                filtered_db_plugins = [
                    p
                    for p in db_plugins
                    if p.get("is_active", False) == (plugin_type == "active")
                ]
                response["database_plugins"] = filtered_db_plugins

            # Generate summary
            file_plugins = response["file_based_plugins"]
            db_plugins = response["database_plugins"]
            assert isinstance(file_plugins, list)
            assert isinstance(db_plugins, list)

            response["summary"] = {
                "total_file_based": len(file_plugins),
                "total_database": len(db_plugins),
                "total_active_database": len(
                    [p for p in db_plugins if p.get("is_active", False)]
                ),
                "total_plugins": len(file_plugins) + len(db_plugins),
            }

            return TextContent(type="text", text=json.dumps(response, indent=2))

        except Exception as e:
            return TextContent(
                type="text",
                text=json.dumps(
                    {"success": False, "error": f"Tool execution error: {str(e)}"},
                    indent=2,
                ),
            )

    def _get_file_based_plugins(
        self, include_details: bool = False, include_code: bool = False
    ) -> list[dict[str, Any]]:
        """Get information about file-based plugins."""
        try:
            plugins_info = plugin_analyzer.analyze_existing_plugins()

            if not include_details:
                # Return minimal information with better error handling
                result = []
                for plugin in plugins_info:
                    if "error" in plugin:
                        result.append(
                            {
                                "name": plugin.get("name", "unknown"),
                                "error": plugin["error"],
                                "status": "error",
                            }
                        )
                    else:
                        result.append(
                            {
                                "name": plugin.get("name", "unknown"),
                                "verbose_name": plugin.get("verbose_name", ""),
                                "type": plugin.get("type", "unknown"),
                                "has_prompt": plugin.get("has_prompt", False),
                                "status": "working",
                            }
                        )
                return result

            # Return detailed information
            detailed_plugins = []
            for plugin_info in plugins_info:
                if "error" in plugin_info:
                    detailed_plugins.append(plugin_info)
                    continue

                plugin_name = plugin_info["name"]
                detailed_info = plugin_analyzer.analyze_plugin_by_name(plugin_name)

                if "error" not in detailed_info:
                    plugin_detail = {
                        "name": plugin_name,
                        "verbose_name": plugin_info.get("verbose_name", ""),
                        "type": plugin_info.get("type", "unknown"),
                        "has_prompt": plugin_info.get("has_prompt", False),
                        "templates": detailed_info.get("templates", {}),
                        "prompt": detailed_info.get("prompt", None),
                    }

                    if include_code:
                        plugin_detail["source_code"] = {
                            "module": detailed_info.get("module_source", ""),
                            "form": detailed_info.get("form_source", ""),
                        }
                        # Add template content if available
                        templates = detailed_info.get("templates", {})
                        if templates:
                            plugin_detail["template_content"] = {
                                "main": templates.get("main_content", ""),
                                "form": templates.get("form_content", ""),
                            }

                    detailed_plugins.append(plugin_detail)
                else:
                    detailed_plugins.append(
                        {"name": plugin_name, "error": detailed_info["error"]}
                    )

            return detailed_plugins

        except Exception as e:
            return [{"error": f"Failed to load file-based plugins: {str(e)}"}]

    def _get_database_plugins(
        self, include_details: bool = False, include_code: bool = False
    ) -> list[dict[str, Any]]:
        """Get information about database plugins."""
        try:
            # Ensure Django is properly set up
            ensure_django_setup()

            # Use threading to avoid async context issues
            import threading
            import queue

            result_queue: queue.Queue[dict[str, Any]] = queue.Queue()

            def get_plugins_in_thread():
                try:
                    from django_resume.models import Plugin

                    plugins = []
                    for plugin in Plugin.objects.all():
                        plugin_info = {
                            "id": plugin.id,
                            "name": plugin.name,
                            "model": plugin.model,
                            "is_active": plugin.is_active,
                            "has_prompt": bool(plugin.prompt.strip()),
                            "has_module": bool(plugin.module.strip()),
                            "has_content_template": bool(
                                plugin.content_template.strip()
                            ),
                            "has_form_template": bool(plugin.form_template.strip()),
                            "status": "active" if plugin.is_active else "inactive",
                        }

                        if include_details:
                            plugin_info.update(
                                {
                                    "prompt": plugin.prompt,
                                    "plugin_data": plugin.plugin_data,
                                    "created_fields": self._extract_form_fields(
                                        plugin.module
                                    ),
                                }
                            )

                            if include_code:
                                plugin_info["source_code"] = {
                                    "module": plugin.module,
                                    "content_template": plugin.content_template,
                                    "form_template": plugin.form_template,
                                }

                        plugins.append(plugin_info)

                    result_queue.put({"success": True, "plugins": plugins})

                except Exception as db_error:
                    result_queue.put(
                        {
                            "success": False,
                            "error": f"Database access failed: {str(db_error)}",
                        }
                    )

            # Run in thread to avoid async context issues
            thread = threading.Thread(target=get_plugins_in_thread)
            thread.start()
            thread.join(timeout=10)  # 10 second timeout

            if thread.is_alive():
                return [{"error": "Database query timed out", "status": "timeout"}]

            try:
                result = result_queue.get_nowait()
                if result["success"]:
                    return result["plugins"]
                else:
                    return [{"error": result["error"], "status": "db_error"}]
            except queue.Empty:
                return [
                    {
                        "error": "No result from database thread",
                        "status": "thread_error",
                    }
                ]

        except Exception as e:
            return [
                {
                    "error": f"Failed to setup Django for database access: {str(e)}",
                    "status": "setup_error",
                }
            ]

    def _extract_form_fields(self, module_code: str) -> list[str]:
        """Extract form field names from plugin module code."""
        import re

        try:
            # Quick regex extraction for form fields
            field_pattern = r"(\w+)\s*=\s*forms\.\w+Field"
            matches = re.findall(field_pattern, module_code)
            return matches
        except:  # noqa: E722
            return []


# Global instance
list_plugins_tool = ListPluginsTool()
