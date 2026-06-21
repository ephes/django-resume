"""Entry-point page discovery.

A separately distributed package (not an installed Django app) registers its
pages through ``django_resume.pages`` entry points. These tests cover the
loader contract with fake entry points; end-to-end discovery of a really
installed distribution is proven by the live-server e2e test
(``e2e_tests/entrypoint_page_test.py``).
"""

import pytest

import django_resume.pages as pages_pkg
from django_resume.pages import (
    ENTRY_POINT_GROUP,
    ResumePage,
    load_entry_point_pages,
    page_registry,
)


@pytest.fixture(autouse=True)
def _isolate_entry_point_guard(monkeypatch):
    # Give each test a fresh idempotency guard so loads are deterministic and do
    # not leak across tests (monkeypatch restores the real set afterwards).
    monkeypatch.setattr(pages_pkg, "_loaded_entry_points", set())


class _FakeEntryPoint:
    def __init__(self, target, name="fake", value="fake.module:target"):
        self._target = target
        self.name = name
        self.value = value
        self.group = ENTRY_POINT_GROUP

    def load(self):
        return self._target


def _patch_entry_points(monkeypatch, entry_points):
    monkeypatch.setattr(
        pages_pkg,
        "entry_points",
        lambda group=None: entry_points if group == ENTRY_POINT_GROUP else [],
    )


def test_loads_resumepage_subclass(monkeypatch):
    class EpPage(ResumePage):
        url_name = "ep-demo"
        path = "ep-demo/"

    _patch_entry_points(monkeypatch, [_FakeEntryPoint(EpPage)])
    try:
        load_entry_point_pages()
        assert isinstance(page_registry.get_page("ep-demo"), EpPage)
    finally:
        page_registry.unregister(EpPage)


def test_invokes_callable_target(monkeypatch):
    calls = []

    def register_my_pages():
        calls.append(True)

    _patch_entry_points(monkeypatch, [_FakeEntryPoint(register_my_pages)])
    load_entry_point_pages()
    assert calls == [True]


def test_loading_is_idempotent_across_repeated_calls(monkeypatch):
    # A registering callable runs at most once even if discovery runs again
    # (e.g. AppConfig.ready re-runs), so pages are not double-registered.
    calls = []
    _patch_entry_points(
        monkeypatch, [_FakeEntryPoint(lambda: calls.append(1), name="once")]
    )

    load_entry_point_pages()
    load_entry_point_pages()

    assert calls == [1]


def test_rejects_non_page_non_callable_target(monkeypatch):
    _patch_entry_points(monkeypatch, [_FakeEntryPoint(42)])
    with pytest.raises(TypeError):
        load_entry_point_pages()


def test_rejects_class_target_that_is_not_a_resumepage(monkeypatch):
    # A class is callable, so it must be rejected explicitly -- otherwise it
    # would be instantiated by the callable path and register no page.
    class NotAPage:
        pass

    _patch_entry_points(monkeypatch, [_FakeEntryPoint(NotAPage)])
    with pytest.raises(TypeError):
        load_entry_point_pages()
    assert page_registry.get_page(getattr(NotAPage, "url_name", "")) is None


def test_no_entry_points_is_a_noop(monkeypatch):
    _patch_entry_points(monkeypatch, [])
    before = {p.url_name for p in page_registry.get_all_pages()}
    load_entry_point_pages()
    assert {p.url_name for p in page_registry.get_all_pages()} == before


def test_autodiscover_runs_modules_then_entry_points(monkeypatch):
    """``autodiscover_pages`` imports ``resume_pages`` modules *and* loads entry
    points -- the public contract third-party packages rely on."""
    seen = []
    monkeypatch.setattr(
        pages_pkg, "autodiscover_modules", lambda name: seen.append(("modules", name))
    )
    monkeypatch.setattr(
        pages_pkg, "load_entry_point_pages", lambda: seen.append(("entry_points",))
    )

    pages_pkg.autodiscover_pages()

    assert seen == [("modules", "resume_pages"), ("entry_points",)]
