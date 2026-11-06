"""Synthetic local/CI PostgreSQL fixture; no production credentials."""

from .settings import *  # noqa: F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "resume_test",
        "USER": "resume",
        "PASSWORD": "synthetic-only",
        "HOST": "127.0.0.1",
        "PORT": "5432",
    }
}
