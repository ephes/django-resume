"""Main MCP server for django-resume plugin development."""

import asyncio
import logging
from typing import Any

import mcp.server.stdio
from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import mcp.types as types
from pydantic import AnyUrl

from .resources.codebase import codebase_resource
from .resources.templates import templates_resource
from .resources.database import database_resource
from .resources.documentation import documentation_resource
from .resources.schemas import schema_resource

# from .tools.create_plugin import create_plugin_tool  # DEPRECATED: Use Django admin + Playwright workflow instead
from .tools.create_plugin_direct import create_plugin_direct_tool
from .tools.validate_plugin_code import validate_plugin_code_tool
from .tools.update_plugin_code import update_plugin_code_tool
from .tools.test_plugin_browser import test_plugin_browser_tool
from .tools.debug_plugin import debug_plugin_tool
from .tools.list_plugins import list_plugins_tool
from .tools.analyze_plugin import analyze_plugin_tool

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("django-resume-mcp-server")

# Create the server
server: Server = Server("django-resume-mcp-server")


@server.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List all available resources."""
    resources = []

    # Add codebase resources
    try:
        resources.extend(codebase_resource.list_resources())
    except Exception as e:
        logger.error(f"Error listing codebase resources: {e}")

    # Add template resources
    try:
        resources.extend(templates_resource.list_resources())
    except Exception as e:
        logger.error(f"Error listing template resources: {e}")

    # Add database resources
    try:
        resources.extend(database_resource.list_resources())
    except Exception as e:
        logger.error(f"Error listing database resources: {e}")

    # Add documentation resources
    try:
        resources.extend(documentation_resource.list_resources())
    except Exception as e:
        logger.error(f"Error listing documentation resources: {e}")

    # Add schema resources
    try:
        resources.extend(schema_resource.list_resources())
    except Exception as e:
        logger.error(f"Error listing schema resources: {e}")

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
    """Read a specific resource."""
    try:
        if uri.startswith("codebase://"):
            content = codebase_resource.get_resource(uri)
            return content.text
        elif uri.startswith("templates://"):
            content = templates_resource.get_resource(uri)
            return content.text
        elif uri.startswith("database://"):
            content = database_resource.get_resource(uri)
            return content.text
        elif uri.startswith("docs://"):
            content = documentation_resource.get_resource(uri)
            return content.text
        elif uri.startswith("schemas://"):
            content = schema_resource.get_resource(uri)
            return content.text
        elif uri == "overview://codebase":
            return codebase_resource.get_plugin_structure_overview()
        elif uri == "overview://templates":
            return templates_resource.get_template_structure_overview()
        elif uri == "overview://database":
            return database_resource.get_database_overview()
        else:
            raise ValueError(f"Unknown resource URI: {uri}")
    except Exception as e:
        logger.error(f"Error reading resource {uri}: {e}")
        raise


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List all available tools."""
    return [
        # create_plugin_tool.get_tool(),  # DEPRECATED: Use Django admin + Playwright workflow instead
        create_plugin_direct_tool.get_tool(),
        validate_plugin_code_tool.get_tool(),
        update_plugin_code_tool.get_tool(),
        test_plugin_browser_tool.get_tool(),
        debug_plugin_tool.get_tool(),
        list_plugins_tool.get_tool(),
        analyze_plugin_tool.get_tool(),
    ]


@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict[str, Any] | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls."""
    try:
        if arguments is None:
            arguments = {}

        # if name == "create_plugin":  # DEPRECATED: Use Django admin + Playwright workflow instead
        #     result = create_plugin_tool.execute(arguments)
        #     return [result]
        if name == "create_plugin_direct":
            result = create_plugin_direct_tool.execute(arguments)
            return [result]
        elif name == "validate_plugin_code":
            result = validate_plugin_code_tool.execute(arguments)
            return [result]
        elif name == "update_plugin_code":
            result = update_plugin_code_tool.execute(arguments)
            return [result]
        elif name == "test_plugin_in_browser":
            result = test_plugin_browser_tool.execute(arguments)
            return [result]
        elif name == "debug_plugin":
            result = debug_plugin_tool.execute(arguments)
            return [result]
        elif name == "list_plugins":
            result = list_plugins_tool.execute(arguments)
            return [result]
        elif name == "analyze_plugin":
            result = analyze_plugin_tool.execute(arguments)
            return [result]
        else:
            raise ValueError(f"Unknown tool: {name}")
    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Main entry point for the MCP server."""
    try:
        logger.info("Initializing MCP server...")

        # Initialization options
        options = InitializationOptions(
            server_name="django-resume-mcp-server",
            server_version="0.1.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities={},
            ),
        )

        logger.info("Starting stdio server...")
        async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
            logger.info("Running MCP server...")
            await server.run(
                read_stream,
                write_stream,
                options,
            )
    except Exception as e:
        logger.error(f"Error in main server loop: {e}")
        import traceback

        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    asyncio.run(main())
