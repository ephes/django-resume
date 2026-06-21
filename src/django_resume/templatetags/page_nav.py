from __future__ import annotations

from django import template

from ..models import Resume
from ..pages import page_registry

register = template.Library()


@register.simple_tag
def page_nav_links(resume: Resume) -> list[dict[str, str]]:
    """Return ``{"title", "url"}`` nav entries for every registered page that is
    advertised (has a ``nav_title``) and visible for ``resume``.

    This is what lets new pages -- including third-party ones discovered from an
    installed app -- appear in navigation automatically, without editing the
    template that renders the links.
    """
    return [
        {"title": page.nav_title, "url": page.nav_url(resume)}
        for page in page_registry.get_all_pages()
        if page.nav_title and page.is_visible(resume)
    ]
