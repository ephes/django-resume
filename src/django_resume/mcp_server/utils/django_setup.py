"""Django environment setup utilities for the MCP server."""

import os
import django
from django.conf import settings


def ensure_django_setup():
    """Ensure Django is configured and ready."""
    if not settings.configured:
        # Set up Django settings if not already configured
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "example.settings")
        django.setup()


def get_project_root():
    """Get the django-resume project root directory."""
    from pathlib import Path

    # We're in src/django_resume/mcp_server/utils/django_setup.py
    # So project root is 4 levels up
    return Path(__file__).parent.parent.parent.parent.parent
