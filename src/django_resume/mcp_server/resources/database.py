"""MCP resource for exposing django-resume database content."""

from typing import List, Dict, Any
import json

from mcp.types import Resource, TextResourceContents

from ..utils.django_setup import ensure_django_setup


class DatabaseResource:
    """Exposes django-resume database content as MCP resources."""

    def __init__(self):
        # Django setup will be called when needed
        pass

    def list_resources(self) -> List[Resource]:
        """List all available database resources."""
        ensure_django_setup()
        resources = []

        # Database plugins
        resources.append(
            Resource(
                uri="database://plugins",
                name="Database Plugins",
                description="All plugins stored in the database",
                mimeType="application/json",
            )
        )

        # Individual plugin resources
        db_plugins = self._get_database_plugins()
        for plugin in db_plugins:
            if "error" not in plugin:
                resources.append(
                    Resource(
                        uri=f"database://plugin/{plugin['name']}",
                        name=f"Plugin: {plugin['name']}",
                        description=f"Database plugin: {plugin['name']}",
                        mimeType="application/json",
                    )
                )

        # Resume data
        resources.append(
            Resource(
                uri="database://resumes",
                name="Resume Data",
                description="All resumes and their plugin data",
                mimeType="application/json",
            )
        )

        # Resume list
        resumes = self._get_resumes()
        for resume in resumes:
            if "error" not in resume:
                resources.append(
                    Resource(
                        uri=f"database://resume/{resume['slug']}",
                        name=f"Resume: {resume['name']}",
                        description=f"Plugin data for resume '{resume['name']}'",
                        mimeType="application/json",
                    )
                )

        return resources

    def get_resource(self, uri: str) -> TextResourceContents:
        """Get content of a specific database resource."""
        ensure_django_setup()
        if not uri.startswith("database://"):
            raise ValueError(f"Invalid URI: {uri}")

        path_part = uri[11:]  # Remove "database://"

        if path_part == "plugins":
            content = self._get_database_plugins_json()
        elif path_part.startswith("plugin/"):
            plugin_name = path_part[7:]
            content = self._get_plugin_json(plugin_name)
        elif path_part == "resumes":
            content = self._get_resumes_json()
        elif path_part.startswith("resume/"):
            resume_slug = path_part[7:]
            content = self._get_resume_json(resume_slug)
        else:
            raise ValueError(f"Unknown resource path: {path_part}")

        return TextResourceContents(uri=uri, text=content, mimeType="application/json")

    def _get_database_plugins(self) -> List[Dict[str, Any]]:
        """Get all database plugins."""
        try:
            from django_resume.models import Plugin

            plugins = []
            for plugin in Plugin.objects.all():
                plugins.append(
                    {
                        "id": plugin.id,
                        "name": plugin.name,
                        "model": plugin.model,
                        "prompt": plugin.prompt,
                        "is_active": plugin.is_active,
                        "plugin_data": plugin.plugin_data,
                        "has_module": bool(plugin.module.strip()),
                        "has_content_template": bool(plugin.content_template.strip()),
                        "has_form_template": bool(plugin.form_template.strip()),
                    }
                )

            return plugins
        except Exception as e:
            return [{"error": f"Failed to load plugins: {e}"}]

    def _get_database_plugins_json(self) -> str:
        """Get database plugins as JSON."""
        plugins = self._get_database_plugins()
        return json.dumps(
            {
                "plugins": plugins,
                "count": len([p for p in plugins if "error" not in p]),
                "description": "All plugins stored in the database",
            },
            indent=2,
        )

    def _get_plugin_json(self, plugin_name: str) -> str:
        """Get specific plugin as JSON."""
        try:
            from django_resume.models import Plugin

            plugin = Plugin.objects.get(name=plugin_name)
            plugin_data = {
                "id": plugin.id,
                "name": plugin.name,
                "model": plugin.model,
                "prompt": plugin.prompt,
                "module": plugin.module,
                "content_template": plugin.content_template,
                "form_template": plugin.form_template,
                "plugin_data": plugin.plugin_data,
                "is_active": plugin.is_active,
            }

            return json.dumps(plugin_data, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Plugin not found: {e}"})

    def _get_resumes(self) -> List[Dict[str, Any]]:
        """Get all resumes."""
        try:
            from django_resume.models import Resume

            resumes = []
            for resume in Resume.objects.all():
                resumes.append(
                    {
                        "id": resume.id,
                        "name": resume.name,
                        "slug": resume.slug,
                        "owner": resume.owner.username if resume.owner else None,
                        "plugin_count": len(resume.plugin_data),
                        "plugins": list(resume.plugin_data.keys()),
                    }
                )

            return resumes
        except Exception as e:
            return [{"error": f"Failed to load resumes: {e}"}]

    def _get_resumes_json(self) -> str:
        """Get resumes as JSON."""
        resumes = self._get_resumes()
        return json.dumps(
            {
                "resumes": resumes,
                "count": len([r for r in resumes if "error" not in r]),
                "description": "All resumes in the database",
            },
            indent=2,
        )

    def _get_resume_json(self, resume_slug: str) -> str:
        """Get specific resume data as JSON."""
        try:
            from django_resume.models import Resume

            resume = Resume.objects.get(slug=resume_slug)
            resume_data = {
                "id": resume.id,
                "name": resume.name,
                "slug": resume.slug,
                "owner": resume.owner.username if resume.owner else None,
                "plugin_data": resume.plugin_data,
                "current_theme": resume.current_theme,
                "token_is_required": resume.token_is_required,
            }

            return json.dumps(resume_data, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Resume not found: {e}"})

    def get_database_overview(self) -> str:
        """Get an overview of the database content."""
        overview = []
        overview.append("# Django-Resume Database Overview\n")

        # Database plugins
        db_plugins = self._get_database_plugins()
        valid_plugins = [p for p in db_plugins if "error" not in p]
        overview.append(f"## Database Plugins ({len(valid_plugins)})")
        if valid_plugins:
            for plugin in valid_plugins:
                status = "Active" if plugin.get("is_active") else "Inactive"
                overview.append(f"- **{plugin['name']}** ({status})")
                overview.append(f"  - Model: {plugin.get('model', 'N/A')}")
                overview.append(f"  - Has code: {plugin.get('has_module', False)}")
                overview.append(
                    f"  - Has templates: {plugin.get('has_content_template', False)} / {plugin.get('has_form_template', False)}"
                )
        else:
            overview.append("No database plugins found or error loading.")

        # Resumes
        resumes = self._get_resumes()
        valid_resumes = [r for r in resumes if "error" not in r]
        overview.append(f"\n## Resumes ({len(valid_resumes)})")
        if valid_resumes:
            for resume in valid_resumes:
                overview.append(f"- **{resume['name']}** ({resume['slug']})")
                overview.append(f"  - Owner: {resume.get('owner', 'N/A')}")
                overview.append(
                    f"  - Plugins: {resume.get('plugin_count', 0)} ({', '.join(resume.get('plugins', []))})"
                )
        else:
            overview.append("No resumes found or error loading.")

        overview.append("\n## Database Schema")
        overview.append("- **Plugin**: Stores dynamically generated plugins")
        overview.append("  - Code (module), templates, metadata")
        overview.append("  - LLM model used for generation")
        overview.append("  - Activation status")
        overview.append("- **Resume**: Stores user resume data")
        overview.append("  - JSON field for all plugin data")
        overview.append("  - Owner relationship")
        overview.append("  - URL slug for public access")

        return "\n".join(overview)


# Global instance
database_resource = DatabaseResource()
