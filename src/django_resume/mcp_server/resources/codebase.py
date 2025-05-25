"""MCP resource for exposing django-resume codebase."""

from pydantic import AnyUrl
from mcp.types import Resource, TextResourceContents

from ..utils.django_setup import ensure_django_setup, get_project_root


class CodebaseResource:
    """Exposes the django-resume codebase as MCP resources."""

    def __init__(self):
        self.project_root = get_project_root()
        self.src_path = self.project_root / "src" / "django_resume"

    def list_resources(self) -> list[Resource]:
        """List all available codebase resources."""
        resources = []

        # Add plugin files
        plugins_path = self.src_path / "plugins"
        if plugins_path.exists():
            for plugin_file in plugins_path.glob("*.py"):
                if plugin_file.name != "__init__.py":
                    resources.append(
                        Resource(
                            uri=AnyUrl(f"codebase://plugins/{plugin_file.name}"),
                            name=f"Plugin: {plugin_file.stem}",
                            description=f"Source code for {plugin_file.stem} plugin",
                            mimeType="text/python",
                        )
                    )

        # Add key model files
        key_files = [
            ("models.py", "Django models for Resume and Plugin"),
            ("admin.py", "Django admin configuration"),
            ("views.py", "Django views"),
            ("forms.py", "Django forms"),
            ("plugin_generator.py", "Plugin generation utilities"),
            ("apps.py", "Django app configuration"),
        ]

        for filename, description in key_files:
            file_path = self.src_path / filename
            if file_path.exists():
                resources.append(
                    Resource(
                        uri=AnyUrl(f"codebase://core/{filename}"),
                        name=f"Core: {filename}",
                        description=description,
                        mimeType="text/python",
                    )
                )

        # Add base plugin file
        base_plugin_path = self.src_path / "plugins" / "base.py"
        if base_plugin_path.exists():
            resources.append(
                Resource(
                    uri=AnyUrl("codebase://plugins/base.py"),
                    name="Plugin Base Classes",
                    description="Base classes for SimplePlugin and ListPlugin",
                    mimeType="text/python",
                )
            )

        # Add registry file
        registry_path = self.src_path / "plugins" / "registry.py"
        if registry_path.exists():
            resources.append(
                Resource(
                    uri=AnyUrl("codebase://plugins/registry.py"),
                    name="Plugin Registry",
                    description="Plugin registration and discovery system",
                    mimeType="text/python",
                )
            )

        return resources

    def get_resource(self, uri: str) -> TextResourceContents:
        """Get content of a specific resource."""
        if not uri.startswith("codebase://"):
            raise ValueError(f"Invalid URI: {uri}")

        # Extract path from URI
        path_part = uri[12:]  # Remove "codebase://"

        if path_part.startswith("plugins/"):
            file_path = self.src_path / "plugins" / path_part[8:]
        elif path_part.startswith("core/"):
            file_path = self.src_path / path_part[5:]
        else:
            raise ValueError(f"Unknown resource path: {path_part}")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Fallback for binary files
            content = file_path.read_text(encoding="latin-1")

        return TextResourceContents(
            uri=AnyUrl(uri), text=content, mimeType="text/python"
        )

    def get_plugin_structure_overview(self) -> str:
        """Get an overview of the plugin structure."""
        ensure_django_setup()

        try:
            from django_resume.plugins.registry import plugin_registry

            overview = []
            overview.append("# Django-Resume Plugin Structure\n")

            # File-based plugins
            overview.append("## File-based Plugins")
            for plugin in plugin_registry.get_all_plugins():
                overview.append(f"- **{plugin.name}** ({plugin.verbose_name})")
                if hasattr(plugin, "prompt"):
                    overview.append("  - Has prompt for LLM generation")
                overview.append(f"  - Type: {plugin.__class__.__name__}")

            overview.append("\n## Plugin Base Classes")
            overview.append("- **SimplePlugin**: For single-form plugins")
            overview.append("- **ListPlugin**: For plugins with multiple items")

            overview.append("\n## Key Components")
            overview.append("- **Forms**: Django forms for data input")
            overview.append("- **Templates**: HTML templates for rendering")
            overview.append("- **Data Storage**: JSON fields in Resume model")
            overview.append("- **Inline Editing**: HTMX-powered live editing")

            return "\n".join(overview)

        except Exception as e:
            return f"Error generating overview: {e}"


# Global instance
codebase_resource = CodebaseResource()
