"""Debug version of MCP server entry point with extensive logging."""

import asyncio
import os
import sys
import logging
from pathlib import Path
from datetime import datetime


def setup_logging():
    """Set up comprehensive logging for debugging."""
    log_file = Path.home() / "mcp_server_debug.log"

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # File handler
    file_handler = logging.FileHandler(log_file, mode="a")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG)

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # MCP specific logger
    mcp_logger = logging.getLogger("django-resume-mcp-server")
    mcp_logger.setLevel(logging.DEBUG)

    return logging.getLogger("debug-entrypoint")


def setup_django_environment():
    """Set up Django environment with proper path handling."""
    logger = logging.getLogger("debug-entrypoint")
    logger.info("Setting up Django environment...")

    # Find the project root (where pyproject.toml is)
    current_path = Path.cwd()
    project_root = None

    logger.info(f"Current working directory: {current_path}")

    # Look for pyproject.toml starting from current directory going up
    for path in [current_path] + list(current_path.parents):
        logger.debug(f"Checking for pyproject.toml in: {path}")
        if (path / "pyproject.toml").exists():
            # Check if this is the django-resume project
            pyproject_content = (path / "pyproject.toml").read_text()
            if 'name = "django-resume"' in pyproject_content:
                project_root = path
                logger.info(f"Found django-resume project root: {project_root}")
                break

    if project_root is None:
        # Fallback: assume we're in the project somewhere
        if "django-resume" in str(current_path):
            parts = current_path.parts
            for i, part in enumerate(parts):
                if part == "django-resume":
                    project_root = Path(*parts[: i + 1])
                    logger.info(f"Found project root via fallback: {project_root}")
                    break

    if project_root is None:
        error_msg = f"Could not find django-resume project root. CWD: {current_path}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    # Add the example directory to Python path for settings
    example_dir = project_root / "example"
    if example_dir.exists():
        if str(example_dir) not in sys.path:
            sys.path.insert(0, str(example_dir))
            logger.info(f"Added to Python path: {example_dir}")
        else:
            logger.info(f"Already in Python path: {example_dir}")
    else:
        logger.warning(f"Example directory not found: {example_dir}")

    # Set Django settings
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        os.environ["DJANGO_SETTINGS_MODULE"] = "example.settings"
        logger.info("Set DJANGO_SETTINGS_MODULE to example.settings")
    else:
        logger.info(
            f"DJANGO_SETTINGS_MODULE already set: {os.environ['DJANGO_SETTINGS_MODULE']}"
        )

    logger.info(f"Python path (first 5): {sys.path[:5]}")
    return project_root


def main():
    """Main entry point for the debug MCP server."""
    logger = setup_logging()
    logger.info("=" * 60)
    logger.info(f"Starting DEBUG MCP server at {datetime.now()}")
    logger.info("=" * 60)

    try:
        # Setup paths and Django environment
        logger.info("Phase 1: Setting up environment...")
        project_root = setup_django_environment()
        logger.info(f"Project root: {project_root}")

        # Test Django import
        logger.info("Phase 2: Importing Django...")
        import django
        from django.conf import settings

        logger.info(f"Django version: {django.VERSION}")

        # Set up Django if not already configured
        if not settings.configured:
            logger.info("Phase 3: Configuring Django...")
            django.setup()
            logger.info("Django setup complete")
        else:
            logger.info("Django already configured")

        # Test django-resume imports
        logger.info("Phase 4: Testing django-resume imports...")
        try:
            from django_resume.models import Plugin, Resume

            logger.info("Successfully imported django-resume models")

            plugin_count = Plugin.objects.count()
            resume_count = Resume.objects.count()
            logger.info(
                f"Database accessible - Plugins: {plugin_count}, Resumes: {resume_count}"
            )
        except Exception as e:
            logger.error(f"Failed to access django-resume models: {e}")
            raise

        # Import MCP server components
        logger.info("Phase 5: Importing MCP server components...")
        from django_resume.mcp_server.server import main as server_main

        logger.info("MCP server components imported successfully")

        # Test resource availability
        logger.info("Phase 6: Testing MCP resources...")
        from django_resume.mcp_server.resources.codebase import codebase_resource
        from django_resume.mcp_server.resources.templates import templates_resource
        from django_resume.mcp_server.resources.database import database_resource

        try:
            resources = codebase_resource.list_resources()
            logger.info(f"Codebase resources available: {len(resources)}")

            resources = templates_resource.list_resources()
            logger.info(f"Template resources available: {len(resources)}")

            resources = database_resource.list_resources()
            logger.info(f"Database resources available: {len(resources)}")
        except Exception as e:
            logger.error(f"Error testing resources: {e}")
            raise

        # Test tools
        logger.info("Phase 7: Testing MCP tools...")
        from django_resume.mcp_server.tools.list_plugins import list_plugins_tool
        from django_resume.mcp_server.tools.create_plugin import create_plugin_tool
        from django_resume.mcp_server.tools.analyze_plugin import analyze_plugin_tool

        try:
            tool = list_plugins_tool.get_tool()
            logger.info(f"List plugins tool: {tool.name}")

            tool = create_plugin_tool.get_tool()
            logger.info(f"Create plugin tool: {tool.name}")

            tool = analyze_plugin_tool.get_tool()
            logger.info(f"Analyze plugin tool: {tool.name}")
        except Exception as e:
            logger.error(f"Error testing tools: {e}")
            raise

        # Start the actual server
        logger.info("Phase 8: Starting MCP server...")
        logger.info("Server initialization complete, starting async event loop...")

        # Add signal handlers for graceful shutdown
        import signal

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down...")
            sys.exit(0)

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)

        asyncio.run(server_main())

    except KeyboardInterrupt:
        logger.info("Server stopped by user (KeyboardInterrupt)")
        sys.exit(0)
    except Exception as e:
        logger.error(f"FATAL: Failed to start MCP server: {e}")
        import traceback

        logger.error("Full traceback:")
        logger.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
