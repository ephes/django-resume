from __future__ import annotations

import re
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, path
from django.views.decorators.http import require_http_methods

from .base import ResumePage, dispatch_page


# A page path is "" (the resume root) or nonempty slug segments, each ending
# in "/". Converters, regex syntax and leading slashes are not supported.
_PAGE_PATH = re.compile(r"(?:[A-Za-z0-9_-]+/)*")

# Fixed non-page routes in ``django_resume.urls`` take precedence over page
# routes, so a page under these would never be served.
RESERVED_PAGE_PATH_PREFIXES = ("delete/", "json-resume/")


# URL names of the fixed routes in ``django_resume.urls``. Page patterns come
# after them, so a page reusing one would take over its ``reverse()``.
RESERVED_PAGE_URL_NAMES = frozenset(
    {
        "list",
        "json-resume-import",
        "delete",
        "json-resume",
        "json-resume-themes",
        "json-resume-theme-install",
        "json-resume-theme-preview",
        "json-resume-theme-use",
        "json-resume-rendered",
        "cv-redirect",
    }
)


class PageRegistrationError(ValueError):
    """A page declares an invalid or conflicting route."""


class PageRegistry:
    """Registry of resume page classes, mirroring the plugin registry."""

    def __init__(self) -> None:
        self.pages: dict[str, ResumePage] = {}

    def register(self, page_class: type[ResumePage]) -> None:
        self.register_page_list([page_class])

    def register_page_list(self, page_classes: list[type[ResumePage]]) -> None:
        """Validate the whole batch, then publish it at once.

        Re-registering a ``url_name`` replaces that entry. A batch with an
        invalid ``url_name``/``path``, a reserved path, or a ``url_name`` or
        ``path`` that collides with another page leaves the registry unchanged.
        """
        pages = dict(self.pages)
        for page_class in page_classes:
            url_name = page_class.url_name
            page_path = page_class.path
            if not isinstance(url_name, str) or not url_name:
                raise PageRegistrationError(
                    f"Page {page_class.__name__} needs a nonempty url_name"
                )
            if url_name in RESERVED_PAGE_URL_NAMES:
                raise PageRegistrationError(
                    f"Page url_name {url_name!r} is reserved for a fixed route"
                )
            if not isinstance(page_path, str) or not _PAGE_PATH.fullmatch(page_path):
                raise PageRegistrationError(
                    f"Page {url_name!r} has an unsupported path {page_path!r}"
                )
            if page_path.startswith(RESERVED_PAGE_PATH_PREFIXES):
                raise PageRegistrationError(
                    f"Page {url_name!r} path {page_path!r} is reserved"
                )
            for other_name, other in pages.items():
                if other_name != url_name and other.path == page_path:
                    raise PageRegistrationError(
                        f"Page {url_name!r} path {page_path!r} is already "
                        f"served by page {other_name!r}"
                    )
            pages[url_name] = page_class()
        self.pages = pages

    def unregister(self, page_class: type[ResumePage]) -> None:
        self.pages.pop(page_class.url_name, None)

    def get_page(self, url_name: str) -> ResumePage | None:
        return self.pages.get(url_name)

    def get_all_pages(self) -> list[ResumePage]:
        return list(self.pages.values())

    def get_ordered_pages(self) -> list[ResumePage]:
        """Pages sorted by ``nav_order`` for navigation.

        The sort is stable, so pages with an equal ``nav_order`` keep their
        registration order (``self.pages`` is insertion-ordered). That makes
        navigation deterministic for built-ins plus any third-party pages
        regardless of how many share the same order value."""
        return sorted(self.get_all_pages(), key=lambda page: page.nav_order)

    def get_urls(self) -> list[URLPattern]:
        def make_view(page: ResumePage) -> Callable[[HttpRequest, str], HttpResponse]:
            @require_http_methods(["GET"])
            def view(request: HttpRequest, slug: str) -> HttpResponse:
                return dispatch_page(request, slug, page)

            return view

        # Sort so the bare "<slug:slug>/" catch-all (path == "") is emitted last.
        pages = sorted(self.get_all_pages(), key=lambda p: (p.path == "", p.path))
        return [
            path(f"<slug:slug>/{page.path}", make_view(page), name=page.url_name)
            for page in pages
        ]


# Module-level singleton (shared across the application).
page_registry = PageRegistry()
