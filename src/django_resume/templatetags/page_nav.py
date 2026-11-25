from __future__ import annotations

from urllib.parse import urlencode

from django import template
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from ..models import Resume
from ..pages import page_registry
from ..pages.base import ResumePage
from ..pages.builtins import CvPage
from ..plugins.tokens import TokenPlugin, TokenViaGetForm

register = template.Library()


def _nav_url(page: ResumePage, resume: Resume, request: HttpRequest | None) -> str:
    url = page.nav_url(resume)
    # Custom pages (including CvPage subclasses) retain their existing URL
    # contract. Never attach a bearer capability to an arbitrary destination.
    if (
        type(page) is not CvPage
        or request is None
        or not resume.token_is_required
        or TokenPlugin.user_can_bypass_token(request, resume)
    ):
        return url
    form = TokenViaGetForm(request.GET)
    if not form.is_valid():
        return url
    try:
        TokenPlugin.check_permissions(
            request, resume.plugin_data.get("token", {}), resume
        )
    except PermissionDenied:
        return url
    return f"{url}?{urlencode({'token': form.cleaned_data['token']})}"


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
def page_nav_links(
    resume: Resume, request: HttpRequest | None = None
) -> list[dict[str, str]]:
    """Return ordered ``{"title", "url", "group"}`` nav entries for every
    registered page that is advertised (has a ``nav_title``) and visible for
    the resume and request.

    Entries are ordered by each page's ``nav_order`` (stable, so equal orders
    keep registration order). This is what lets new pages -- including
    third-party ones discovered from an installed app or an entry point --
    appear in navigation automatically and in a predictable place, without
    editing the template that renders the links.

    Pass ``request`` to show the appearance editor to the owner of a protected
    CV and to retain a validated token on the built-in protected CV link.
    """
    # A missing template variable resolves to "" (or string_if_invalid).
    if not isinstance(request, HttpRequest):
        request = None
    return [
        {
            "title": page.nav_title,
            "url": _nav_url(page, resume, request),
            "group": page.nav_group,
        }
        for page in page_registry.get_ordered_pages()
        if page.nav_title and page.is_visible_for_request(resume, request)
    ]


@register.simple_tag
def page_nav_groups(resume: Resume, request: HttpRequest | None = None) -> list[dict]:
    """Return navigation entries for ``resume`` grouped by ``nav_group``.

    Each item is ``{"title": <group label>, "links": [<nav link>, ...]}``.
    Links keep their global ``nav_order`` sequence; groups appear in the order
    their first link does. Templates iterate this to render grouped menus while
    :func:`page_nav_links` still serves callers that want a flat list.
    """
    return group_nav_links(page_nav_links(resume, request=request))
