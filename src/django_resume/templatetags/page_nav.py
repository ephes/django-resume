from __future__ import annotations

from django import template

from ..models import Resume
from ..pages import page_registry

register = template.Library()


def group_nav_links(links: list[dict[str, str]]) -> list[dict]:
    """Bucket already-ordered nav ``links`` by their ``group`` key.

    Pure helper (no registry/URL access) so grouping is unit-testable on its
    own. Group order follows the order in which each group first appears in
    ``links`` -- and because ``links`` arrives pre-sorted by ``nav_order``, that
    is the lowest ``nav_order`` of each group. Later links of an
    already-seen group merge back into that group's bucket rather than starting
    a new one, so a group stays a single contiguous menu section even if its
    members interleave with other groups by order.
    """
    groups: list[dict] = []
    index: dict[str, dict] = {}
    for link in links:
        group_title = link.get("group", "")
        bucket = index.get(group_title)
        if bucket is None:
            bucket = {"title": group_title, "links": []}
            index[group_title] = bucket
            groups.append(bucket)
        bucket["links"].append(link)
    return groups


@register.simple_tag
def page_nav_links(resume: Resume) -> list[dict[str, str]]:
    """Return ordered ``{"title", "url", "group"}`` nav entries for every
    registered page that is advertised (has a ``nav_title``) and visible for
    ``resume``.

    Entries are ordered by each page's ``nav_order`` (stable, so equal orders
    keep registration order). This is what lets new pages -- including
    third-party ones discovered from an installed app or an entry point --
    appear in navigation automatically and in a predictable place, without
    editing the template that renders the links.
    """
    return [
        {
            "title": page.nav_title,
            "url": page.nav_url(resume),
            "group": page.nav_group,
        }
        for page in page_registry.get_ordered_pages()
        if page.nav_title and page.is_visible(resume)
    ]


@register.simple_tag
def page_nav_groups(resume: Resume) -> list[dict]:
    """Return navigation entries for ``resume`` grouped by ``nav_group``.

    Each item is ``{"title": <group label>, "links": [<nav link>, ...]}``.
    Links keep their global ``nav_order`` sequence; groups appear in the order
    their first link does. Templates iterate this to render grouped menus while
    :func:`page_nav_links` still serves callers that want a flat list.
    """
    return group_nav_links(page_nav_links(resume))
