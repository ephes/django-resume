from .base import ResumePage
from .builtins import register_builtin_pages
from .registry import PageRegistry, page_registry

__all__ = [
    "ResumePage",
    "PageRegistry",
    "page_registry",
    "register_builtin_pages",
]
