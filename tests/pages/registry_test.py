import pytest

from django_resume.pages.base import ResumePage
from django_resume.pages.registry import PageRegistrationError, PageRegistry


class DummyPage(ResumePage):
    url_name = "dummy"
    path = "dummy/"
    template_name = "dummy.html"
    section_names: list[str] = []


def test_register_and_get_page():
    registry = PageRegistry()
    registry.register(DummyPage)

    page = registry.get_page("dummy")
    assert isinstance(page, DummyPage)
    assert registry.get_page("missing") is None
    assert [type(p) for p in registry.get_all_pages()] == [DummyPage]


def test_register_page_list_and_unregister():
    registry = PageRegistry()
    registry.register_page_list([DummyPage])
    assert registry.get_page("dummy") is not None

    registry.unregister(DummyPage)
    assert registry.get_page("dummy") is None
    assert registry.get_all_pages() == []


class RootPage(ResumePage):
    url_name = "root"
    path = ""
    template_name = "root.html"
    section_names: list[str] = []


class CvLikePage(ResumePage):
    url_name = "cv-like"
    path = "cv/"
    template_name = "cv.html"
    section_names: list[str] = []


def test_get_urls_emits_bare_catch_all_last():
    registry = PageRegistry()
    # Register root first to prove ordering is structural, not registration order.
    registry.register_page_list([RootPage, CvLikePage])

    patterns = registry.get_urls()
    routes = [str(p.pattern) for p in patterns]
    names = [p.name for p in patterns]

    assert routes[-1] == "<slug:slug>/"
    assert names[-1] == "root"
    assert "<slug:slug>/cv/" in routes


def _page(url_name, page_path):
    return type(
        f"Page_{url_name or 'blank'}",
        (ResumePage,),
        {
            "url_name": url_name,
            "path": page_path,
            "template_name": "x.html",
            "section_names": [],
        },
    )


@pytest.mark.parametrize(
    "page_path",
    [
        "/cv/",
        "cv",
        "cv//",
        "<int:pk>/",
        "a b/",
        "cv/../",
        "delete/",
        "json-resume/",
        "json-resume/extra/",
        None,
    ],
)
def test_register_rejects_unsupported_or_reserved_paths(page_path):
    registry = PageRegistry()
    registry.register(DummyPage)
    with pytest.raises(PageRegistrationError):
        registry.register(_page("bad", page_path))
    assert list(registry.pages) == ["dummy"]


@pytest.mark.parametrize("url_name", ["", None])
def test_register_rejects_missing_url_name(url_name):
    registry = PageRegistry()
    with pytest.raises(PageRegistrationError, match="url_name"):
        registry.register(_page(url_name, "x/"))
    assert registry.pages == {}


def test_register_rejects_duplicate_path_under_another_name():
    registry = PageRegistry()
    registry.register(DummyPage)
    with pytest.raises(PageRegistrationError, match="already served by page 'dummy'"):
        registry.register(_page("other", "dummy/"))
    assert [type(p) for p in registry.get_all_pages()] == [DummyPage]


def test_failed_batch_publishes_nothing():
    registry = PageRegistry()
    registry.register(DummyPage)
    original = registry.get_page("dummy")
    with pytest.raises(PageRegistrationError):
        registry.register_page_list(
            [
                _page("first", "first/"),
                _page("dummy", "replaced/"),
                _page("x", "first/"),
            ]
        )
    assert list(registry.pages) == ["dummy"]
    assert registry.get_page("dummy") is original


def test_batch_rejects_internal_duplicate_paths():
    registry = PageRegistry()
    with pytest.raises(PageRegistrationError, match="already served by page 'one'"):
        registry.register_page_list([_page("one", "same/"), _page("two", "same/")])
    assert registry.pages == {}


def test_replacing_a_url_name_keeps_its_position_and_may_move_path():
    registry = PageRegistry()
    registry.register_page_list([DummyPage, CvLikePage, RootPage])
    replacement = _page("dummy", "moved/")
    registry.register(replacement)
    assert list(registry.pages) == ["dummy", "cv-like", "root"]
    assert isinstance(registry.get_page("dummy"), replacement)
    # The old path is free again after the replacement.
    registry.register(_page("reuse", "dummy/"))
    assert registry.get_page("reuse").path == "dummy/"


def test_builtin_page_paths_pass_preflight():
    from django_resume.pages.builtins import (
        CoverLetterPage,
        CvPage,
        PermissionDeniedPage,
    )

    registry = PageRegistry()
    registry.register_page_list([CoverLetterPage, CvPage, PermissionDeniedPage])
    assert len(registry.get_all_pages()) == 3


def test_reserved_url_names_cover_every_fixed_route():
    from django_resume import urls
    from django_resume.pages import page_registry
    from django_resume.pages.registry import RESERVED_PAGE_URL_NAMES

    fixed = []
    for pattern in urls.urlpatterns:
        if pattern.name in page_registry.pages:
            break  # page routes follow the fixed routes
        fixed.append(pattern.name)
    assert set(fixed) == RESERVED_PAGE_URL_NAMES


@pytest.mark.parametrize("url_name", ["delete", "list", "json-resume", "cv-redirect"])
def test_register_rejects_fixed_route_url_names(url_name):
    registry = PageRegistry()
    with pytest.raises(PageRegistrationError, match="reserved for a fixed route"):
        registry.register(_page(url_name, "elsewhere/"))
    assert registry.pages == {}
