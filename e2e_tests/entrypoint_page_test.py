"""Live-server browser test for a page registered via an ``importlib.metadata``
entry point.

This exercises the *separately distributed package* path end to end: the
``resume-entrypoint-demo`` distribution (installed editable, but **not** in the
example project's ``INSTALLED_APPS``) contributes ``ContactPage`` purely through
its ``django_resume.pages`` entry point. ``django_resume`` loads it on startup,
before the URLconf is built, so the page has a real route and renders in a real
browser -- no test client, no direct view call.

The demo distribution lives in the ``e2e`` dependency group (kept out of
``dev``), so install it first::

    uv sync --group e2e
    uv run pytest --ds=e2e_tests.settings e2e_tests/entrypoint_page_test.py
"""

import pytest
from django.urls import resolve, reverse
from playwright.sync_api import Browser, expect

CONTACT_PATH = "/resume/jochen/contact/"


@pytest.fixture
def seed(transactional_db, django_user_model):
    from django_resume.models import Resume

    owner = django_user_model.objects.create_superuser(
        username="jochen", email="jochen@example.com", password="entrypoint-pw"
    )
    resume = Resume.objects.create(name="Jochen", slug="jochen", owner=owner)
    return {"owner": owner, "resume": resume}


def test_entry_point_page_is_discovered_without_being_an_installed_app():
    from django.conf import settings

    # The contributing distribution is not a Django app ...
    assert "resume_entrypoint_demo" not in settings.INSTALLED_APPS
    # ... yet its page has a route, discovered purely via the entry point.
    assert (
        reverse("resume:entrypoint_contact", kwargs={"slug": "jochen"}) == CONTACT_PATH
    )
    # And it does not shadow (or get shadowed by) the bare detail catch-all.
    assert resolve(CONTACT_PATH).url_name == "entrypoint_contact"
    assert resolve("/resume/jochen/").url_name == "detail"


def test_entry_point_page_renders_in_the_browser(browser: Browser, live_server, seed):
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}{CONTACT_PATH}")
        # Visible content proves the entry-point page actually rendered with the
        # real resume context, not just that the route returned 200.
        expect(page.locator("h1", has_text="Contact Jochen")).to_be_visible()
        expect(page.locator("#entrypoint-marker")).to_have_text(
            "Served by an entry-point page."
        )
    finally:
        page.close()
        context.close()
