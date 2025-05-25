"""Django environment setup utilities for the MCP server."""

import os
import sys
import django
from django.conf import settings
from pathlib import Path


def ensure_django_setup():
    """Ensure Django is configured and ready."""
    if not settings.configured:
        # Add the example project to Python path so we can import its settings
        project_root = get_project_root()
        example_path = project_root / "example"
        if str(example_path) not in sys.path:
            sys.path.insert(0, str(example_path))

        # Set up Django settings if not already configured
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings")
        django.setup()


def get_project_root():
    """Get the django-resume project root directory."""

    # We're in src/django_resume/mcp_server/utils/django_setup.py
    # So project root is 4 levels up
    return Path(__file__).parent.parent.parent.parent.parent
