"""Entry point for the django-resume MCP server."""

import asyncio
import os
import sys
from pathlib import Path


def setup_django_environment():
    """Set up Django environment with proper path handling."""
    # Find the project root (where pyproject.toml is)
    current_path = Path.cwd()
    project_root = None

    # Look for pyproject.toml starting from current directory going up
    for path in [current_path] + list(current_path.parents):
        if (path / "pyproject.toml").exists():
            # Check if this is the django-resume project
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
        raise RuntimeError(
            "Could not find django-resume project root. Please run from within the project directory."
        )

    # Add the example directory to Python path for settings
    example_dir = project_root / "example"
    if example_dir.exists() and str(example_dir) not in sys.path:
        sys.path.insert(0, str(example_dir))

    # Set Django settings
    if not os.environ.get("DJANGO_SETTINGS_MODULE"):
        os.environ["DJANGO_SETTINGS_MODULE"] = "example.settings"

    return project_root


def main():
    """Main entry point for the MCP server script."""
    try:
        # Setup paths and Django environment
        _project_root = setup_django_environment()

        import django
        from django.conf import settings

        # Set up Django if not already configured
        if not settings.configured:
            django.setup()

        # Import and run the server
        from django_resume.mcp_server.server import main as server_main

        asyncio.run(server_main())

    except ImportError as e:
        print(f"Failed to import Django or django-resume: {e}", file=sys.stderr)
        print(
            "Make sure you're in the correct virtual environment and django-resume is installed.",
            file=sys.stderr,
        )
        print(f"Current working directory: {Path.cwd()}", file=sys.stderr)
        print(f"Python path: {sys.path[:3]}...", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to start MCP server: {e}", file=sys.stderr)
        import traceback

        print(traceback.format_exc(), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
