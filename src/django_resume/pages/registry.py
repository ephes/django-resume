from __future__ import annotations

from .base import ResumePage


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


# Module-level singleton (shared across the application).
page_registry = PageRegistry()
