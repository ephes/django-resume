"""MCP resource for exposing django-resume templates."""

from typing import List

from mcp.types import Resource, TextResourceContents

from ..utils.django_setup import get_project_root


class TemplatesResource:
    """Exposes django-resume templates as MCP resources."""

    def __init__(self):
        self.project_root = get_project_root()
        self.templates_path = (
            self.project_root
            / "src"
            / "django_resume"
            / "templates"
            / "django_resume"
            / "plugins"
        )

    def list_resources(self) -> List[Resource]:
        """List all available template resources."""
        resources = []

        if not self.templates_path.exists():
            return resources

        # Traverse plugin template directories
        for plugin_dir in self.templates_path.iterdir():
            if plugin_dir.is_dir():
                plugin_name = plugin_dir.name

                # Look for theme directories (plain, headwind, etc.)
                for theme_dir in plugin_dir.iterdir():
                    if theme_dir.is_dir():
                        theme_name = theme_dir.name

                        # Add template files
                        for template_file in theme_dir.glob("*.html"):
                            uri = f"templates://{plugin_name}/{theme_name}/{template_file.name}"
                            resources.append(
                                Resource(
                                    uri=uri,
                                    name=f"{plugin_name} - {theme_name} - {template_file.stem}",
                                    description=f"Template for {plugin_name} plugin ({theme_name} theme)",
                                    mimeType="text/html",
                                )
                            )

        return resources

    def get_resource(self, uri: str) -> TextResourceContents:
        """Get content of a specific template resource."""
        if not uri.startswith("templates://"):
            raise ValueError(f"Invalid URI: {uri}")

        # Extract path from URI
        path_part = uri[12:]  # Remove "templates://"
        file_path = self.templates_path / path_part

        if not file_path.exists():
            raise FileNotFoundError(f"Template not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")

        return TextResourceContents(uri=uri, text=content, mimeType="text/html")

    def get_template_structure_overview(self) -> str:
        """Get an overview of the template structure."""
        overview = []
        overview.append("# Django-Resume Template Structure\n")

        if not self.templates_path.exists():
            overview.append("Templates directory not found.")
            return "\n".join(overview)

        overview.append("## Available Plugin Templates\n")

        # Group by plugin
        plugins = {}
        for plugin_dir in self.templates_path.iterdir():
            if plugin_dir.is_dir():
                plugin_name = plugin_dir.name
                plugins[plugin_name] = {}

                for theme_dir in plugin_dir.iterdir():
                    if theme_dir.is_dir():
                        theme_name = theme_dir.name
                        templates = [f.name for f in theme_dir.glob("*.html")]
                        plugins[plugin_name][theme_name] = templates

        for plugin_name, themes in plugins.items():
            overview.append(f"### {plugin_name}")
            for theme_name, templates in themes.items():
                overview.append(f"- **{theme_name}** theme:")
                for template in templates:
                    overview.append(f"  - {template}")
            overview.append("")

        overview.append("## Template Types")
        overview.append("- **content.html**: Main display template")
        overview.append("- **form.html**: Inline editing form template")
        overview.append(
            "- **flat.html**: List plugin flat data template (ListPlugin only)"
        )
        overview.append(
            "- **flat_form.html**: List plugin flat data form (ListPlugin only)"
        )
        overview.append("- **item.html**: List plugin item template (ListPlugin only)")
        overview.append("- **item_form.html**: List plugin item form (ListPlugin only)")

        overview.append("\n## Common Template Features")
        overview.append("- **Contenteditable elements**: For inline editing")
        overview.append("- **Edit buttons**: Conditional display based on permissions")
        overview.append("- **HTMX integration**: For dynamic form submissions")
        overview.append("- **Theme support**: Multiple visual themes per plugin")

        return "\n".join(overview)


# Global instance
templates_resource = TemplatesResource()
