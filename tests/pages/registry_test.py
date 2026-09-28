from django_resume.pages.base import ResumePage
from django_resume.pages.registry import PageRegistry


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
