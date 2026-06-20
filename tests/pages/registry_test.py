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
