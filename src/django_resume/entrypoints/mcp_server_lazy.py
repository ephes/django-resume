"""MCP server entry point with lazy Django initialization."""

import asyncio
import os
import sys
from pathlib import Path

# Create a lazy-loading MCP server
import mcp.server.stdio
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions
import mcp.types as types
from pydantic import AnyUrl


def setup_paths():
    """Set up Python paths without initializing Django."""
    # Find the project root
    current_path = Path.cwd()
    project_root = None

    # Look for pyproject.toml starting from current directory going up
    for path in [current_path] + list(current_path.parents):
        if (path / "pyproject.toml").exists():
            pyproject_content = (path / "pyproject.toml").read_text()
            if 'name = "django-resume"' in pyproject_content:
                project_root = path
                break

    if project_root is None:
        # Fallback: assume we're in the project somewhere
        if "django-resume" in str(current_path):
            parts = current_path.parts
            for i, part in enumerate(parts):
                if part == "django-resume":
                    project_root = Path(*parts[: i + 1])
                    break

    if project_root is None:
        raise RuntimeError("Could not find django-resume project root")

    # Add the example directory to Python path for settings
    example_dir = project_root / "example"
    if example_dir.exists() and str(example_dir) not in sys.path:
        sys.path.insert(0, str(example_dir))

    # Set Django settings but don't initialize yet
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        os.environ["DJANGO_SETTINGS_MODULE"] = "example.settings"

    return project_root


# Global flag to track Django initialization
_django_initialized = False


def ensure_django():
    """Initialize Django only when needed."""
    global _django_initialized
    if not _django_initialized:
        import django
        from django.conf import settings

        if not settings.configured:
            django.setup()

        # Test database connection and ensure plugin models are registered
        try:
            from django_resume.models import Plugin

            # Test database access
            _ = Plugin.objects.count()
            # Register dynamic plugins
            Plugin.objects.register_plugin_models()
        except Exception as e:
            print(f"Warning: Database setup issue: {e}", file=sys.stderr)

        _django_initialized = True


server: Server = Server("django-resume-mcp-server")


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List all available resources (lazy Django init)."""
    ensure_django()

    from django_resume.mcp_server.resources.codebase import codebase_resource
    from django_resume.mcp_server.resources.templates import templates_resource
    from django_resume.mcp_server.resources.database import database_resource

    resources = []

    try:
        resources.extend(codebase_resource.list_resources())
    except Exception:
        pass  # Skip if error

    try:
        resources.extend(templates_resource.list_resources())
    except Exception:
        pass

    try:
        resources.extend(database_resource.list_resources())
    except Exception:
        pass

    # Add overview resources
    resources.extend(
        [
            types.Resource(
                uri=AnyUrl("overview://codebase"),
                name="Codebase Overview",
                description="Overview of the django-resume codebase structure",
                mimeType="text/markdown",
            ),
            types.Resource(
                uri=AnyUrl("overview://templates"),
                name="Templates Overview",
                description="Overview of the django-resume template system",
                mimeType="text/markdown",
            ),
            types.Resource(
                uri=AnyUrl("overview://database"),
                name="Database Overview",
                description="Overview of the django-resume database content",
                mimeType="text/markdown",
            ),
        ]
    )

    return resources


@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read a specific resource (lazy Django init)."""
    ensure_django()

    try:
        if uri.startswith("codebase://"):
            from django_resume.mcp_server.resources.codebase import codebase_resource

            content = codebase_resource.get_resource(uri)
            return content.text
        elif uri.startswith("templates://"):
            from django_resume.mcp_server.resources.templates import templates_resource

            content = templates_resource.get_resource(uri)
            return content.text
        elif uri.startswith("database://"):
            from django_resume.mcp_server.resources.database import database_resource

            content = database_resource.get_resource(uri)
            return content.text
        elif uri == "overview://codebase":
            from django_resume.mcp_server.resources.codebase import codebase_resource

            return codebase_resource.get_plugin_structure_overview()
        elif uri == "overview://templates":
            from django_resume.mcp_server.resources.templates import templates_resource

            return templates_resource.get_template_structure_overview()
        elif uri == "overview://database":
            from django_resume.mcp_server.resources.database import database_resource

            return database_resource.get_database_overview()
        else:
            raise ValueError(f"Unknown resource URI: {uri}")
    except Exception as e:
        return f"Error reading resource {uri}: {e}"


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available tools (lazy Django init)."""
    ensure_django()

    from django_resume.mcp_server.tools.create_plugin import create_plugin_tool
    from django_resume.mcp_server.tools.list_plugins import list_plugins_tool
    from django_resume.mcp_server.tools.analyze_plugin import analyze_plugin_tool

    return [
        create_plugin_tool.get_tool(),
        list_plugins_tool.get_tool(),
        analyze_plugin_tool.get_tool(),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Handle tool calls (lazy Django init)."""
    ensure_django()

    try:
        if name == "create_plugin":
            from django_resume.mcp_server.tools.create_plugin import create_plugin_tool

            result = create_plugin_tool.execute(arguments or {})
            return [result]
        elif name == "list_plugins":
            from django_resume.mcp_server.tools.list_plugins import list_plugins_tool

            result = list_plugins_tool.execute(arguments or {})
            return [result]
        elif name == "analyze_plugin":
            from django_resume.mcp_server.tools.analyze_plugin import (
                analyze_plugin_tool,
            )

            result = analyze_plugin_tool.execute(arguments or {})
            return [result]
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Main entry point for the lazy MCP server."""
    print("Starting lazy django-resume MCP server...", file=sys.stderr)

    options = InitializationOptions(
        server_name="django-resume-mcp-server",
        server_version="0.1.0",
        capabilities=server.get_capabilities(
            notification_options=NotificationOptions(),
            experimental_capabilities={},
        ),
    )

    try:
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            print(
                "Lazy server started, Django will initialize on first request...",
                file=sys.stderr,
            )
            await server.run(read_stream, write_stream, options)
    except Exception as e:
        print(f"Server error: {e}", file=sys.stderr)
        import traceback

        print(traceback.format_exc(), file=sys.stderr)
        raise


def main_entry():
    """Entry point that sets up paths first."""
    try:
        # Setup paths without Django
        setup_paths()
        print("Paths configured, starting server...", file=sys.stderr)

        # Run the server
        asyncio.run(main())

    except Exception as e:
        print(f"Failed to start server: {e}", file=sys.stderr)
        import traceback

        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main_entry()
