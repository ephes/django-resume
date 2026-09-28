from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.urls import URLPattern, path
from django.views.decorators.http import require_http_methods

from .base import ResumePage, dispatch_page


class PageRegistry:
    """Registry of resume page classes, mirroring the plugin registry."""

    def __init__(self) -> None:
        self.pages: dict[str, ResumePage] = {}

    def register(self, page_class: type[ResumePage]) -> None:
        self.pages[page_class.url_name] = page_class()

    def register_page_list(self, page_classes: list[type[ResumePage]]) -> None:
        for page_class in page_classes:
            self.register(page_class)

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
