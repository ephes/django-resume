"""Navigation ordering and grouping semantics for the page registry.

Ordering is explicit (``nav_order``) and deterministic: equal ``nav_order``
values fall back to registration order via a stable sort, so built-ins plus
third-party pages always render in a predictable sequence. Grouping
(``nav_group``) buckets the ordered links by group, preserving the order in
which each group first appears.
"""

import pytest

from django_resume.pages.base import ResumePage
from django_resume.pages.registry import PageRegistry
from django_resume.templatetags.page_nav import (
    group_nav_links,
    page_nav_groups,
    page_nav_links,
)


class _Page(ResumePage):
    section_names: list[str] = []


def _make(url_name, *, order=0, group=""):
    return type(
        f"Page_{url_name}",
        (_Page,),
        {
            "url_name": url_name,
            "path": f"{url_name}/",
            "template_name": f"{url_name}.html",
            "nav_title": url_name.title(),
            "nav_order": order,
            "nav_group": group,
        },
    )


def test_get_ordered_pages_sorts_by_nav_order():
    registry = PageRegistry()
    # Register out of nav order to prove the registry sorts, not registration.
    registry.register_page_list([_make("c", order=30), _make("a", order=10)])
    registry.register(_make("b", order=20))

    assert [p.url_name for p in registry.get_ordered_pages()] == ["a", "b", "c"]


def test_get_ordered_pages_is_stable_for_equal_order():
    registry = PageRegistry()
    # Equal nav_order -> registration order is the deterministic tiebreaker.
    registry.register_page_list(
        [_make("x", order=5), _make("y", order=5), _make("z", order=5)]
    )

    assert [p.url_name for p in registry.get_ordered_pages()] == ["x", "y", "z"]


def test_group_nav_links_preserves_first_appearance_and_merges():
    # Pure grouping over already-ordered links: a group keeps the position of its
    # first member and later members of the same group merge back into it.
    links = [
        {"title": "A1", "url": "/a1", "group": "A"},
        {"title": "B1", "url": "/b1", "group": "B"},
        {"title": "A2", "url": "/a2", "group": "A"},
    ]

    groups = group_nav_links(links)

    assert [g["title"] for g in groups] == ["A", "B"]
    assert [link["title"] for link in groups[0]["links"]] == ["A1", "A2"]
    assert [link["title"] for link in groups[1]["links"]] == ["B1"]


def test_group_nav_links_empty_group_title_is_kept_distinct():
    links = [
        {"title": "Ungrouped", "url": "/u", "group": ""},
        {"title": "Grouped", "url": "/g", "group": "G"},
    ]

    groups = group_nav_links(links)

    assert [g["title"] for g in groups] == ["", "G"]


@pytest.mark.django_db
def test_page_nav_links_ordered_by_nav_order(resume):
    resume.owner.save()
    resume.save()

    titles = [link["title"] for link in page_nav_links(resume)]

    # Built-ins: Cover (10), CV (20), 403 (30) -> explicit nav_order, not
    # registration order. 403 shows because a token is required by default.
    assert titles == ["Cover", "CV", "403"]
    # The group is exposed on each link for grouped rendering.
    assert {"title", "url", "group"} <= set(page_nav_links(resume)[0])


@pytest.mark.django_db
def test_page_nav_groups_groups_builtins(resume):
    resume.owner.save()
    resume.save()

    groups = page_nav_groups(resume)
    titles = [g["title"] for g in groups]

    # Cover/CV are the public "Resume" group; the owner-only 403 editor is its
    # own group. Group order follows the first group's lowest nav_order.
    assert titles == ["Resume", "Owner tools"]
    assert [link["title"] for link in groups[0]["links"]] == ["Cover", "CV"]
    assert [link["title"] for link in groups[1]["links"]] == ["403"]
