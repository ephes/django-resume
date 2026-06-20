from django.utils.module_loading import autodiscover_modules

from .base import ResumePage
from .builtins import register_builtin_pages
from .registry import PageRegistry, page_registry


def autodiscover_pages() -> None:
    """Import every installed app's ``resume_pages`` module.

    This is the third-party extension point: an installed app registers its own
    pages by defining a top-level ``resume_pages`` module that calls
    ``page_registry.register(...)`` at import time (mirroring how Django's admin
    discovers ``admin`` modules). It must run before ``django_resume.urls`` is
    imported, so the generated page routes include the discovered pages.
    """
    autodiscover_modules("resume_pages")


__all__ = [
    "ResumePage",
    "PageRegistry",
    "page_registry",
    "register_builtin_pages",
    "autodiscover_pages",
]
