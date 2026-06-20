"""Live-server browser tests for the example app's third-party ``PortfolioPage``.

These run against the *real* example project (``e2e_tests.settings`` reuses
``example.settings``), so they prove the full path: ``django_resume`` discovers
the ``core`` app's ``resume_pages`` module on startup, registers
``PortfolioPage`` before the URLconf is built, and the page renders and is
editable through the actual browser UI -- no test client, no direct view calls.

Run with::

    uv run pytest --ds=e2e_tests.settings e2e_tests/portfolio_test.py
"""

import pytest
from django.urls import resolve, reverse
from playwright.sync_api import Browser, Page, expect

PASSWORD = "portfolio-pw"
PORTFOLIO_PATH = "/resume/jochen/portfolio/"


@pytest.fixture
def seed(transactional_db, django_user_model):
    """Create the resume owner + a non-owner, plus the ``jochen`` resume.

    Owners log into the example project through the admin, so the users are
    superusers; ownership (not staff status) is what gates editing.
    Data is committed via ``transactional_db`` so the live server thread sees it.
    """
    from django_resume.models import Resume

    owner = django_user_model.objects.create_superuser(
        username="jochen", email="jochen@example.com", password=PASSWORD
    )
    django_user_model.objects.create_superuser(
        username="other", email="other@example.com", password=PASSWORD
    )
    resume = Resume.objects.create(name="Jochen", slug="jochen", owner=owner)
    return {"owner": owner, "resume": resume}


def _admin_login(page: Page, live_server, username: str) -> None:
    page.goto(f"{live_server.url}/admin/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", PASSWORD)
    page.click('input[type="submit"]')
    page.wait_for_url(f"{live_server.url}/admin/")


def test_portfolio_routes_resolve_without_shadowing():
    """PortfolioPage is discovered from the example app and its route coexists
    with the built-in routes (the bare ``<slug>/`` detail catch-all stays last).
    """
    slug = "jochen"
    assert reverse("resume:list") == "/resume/"
    assert reverse("resume:delete", kwargs={"slug": slug}) == "/resume/jochen/delete/"
    assert reverse("resume:cv-redirect", kwargs={"slug": slug}) == "/resume/cv/jochen/"
    assert reverse("resume:detail", kwargs={"slug": slug}) == "/resume/jochen/"
    assert reverse("resume:cv", kwargs={"slug": slug}) == "/resume/jochen/cv/"
    assert reverse("resume:403", kwargs={"slug": slug}) == "/resume/jochen/403/"
    assert (
        reverse("resume:portfolio", kwargs={"slug": slug})
        == "/resume/jochen/portfolio/"
    )
    # A plugin inline URL still resolves (page routes did not crowd it out).
    assert (
        reverse("resume:about-edit", kwargs={"resume_id": 1})
        == "/resume/1/plugin/about/edit/"
    )
    # Each path resolves to the intended view; portfolio does not shadow detail.
    assert resolve("/resume/jochen/").url_name == "detail"
    assert resolve("/resume/jochen/portfolio/").url_name == "portfolio"
    assert resolve("/resume/jochen/cv/").url_name == "cv"
    assert resolve("/resume/jochen/403/").url_name == "403"


def test_owner_can_edit_about_section_on_portfolio_page(page: Page, live_server, seed):
    unique = "PortfolioAboutPersisted12345"

    _admin_login(page, live_server, "jochen")

    # Open the portfolio page in edit mode as the owner.
    page.goto(f"{live_server.url}{PORTFOLIO_PATH}?edit=true")
    expect(page.locator("h1", has_text="Portfolio").first).to_be_visible()
    expect(page.locator("#edit-mode")).to_be_visible()

    # The about section exposes an inline edit control.
    about = page.locator("#about")
    expect(about).to_be_visible()
    about.locator("svg[hx-get]").first.click()

    # Fill and submit the inline form through the real UI. The <form> element is
    # an intentionally hidden, button-submitted form; the contenteditable fields
    # are the visible editing surface that edit.js syncs into it on submit.
    title_field = page.locator('#about [contenteditable="true"][data-field="title"]')
    expect(title_field).to_be_visible()
    title_field.fill("My Portfolio")
    page.locator('#about [contenteditable="true"][data-field="text"]').fill(unique)
    page.locator("#submit-about").click()

    # The swapped-in content shows the new text.
    expect(page.locator("#about", has_text=unique)).to_be_visible()

    # Reload the portfolio page (no edit): the change persisted.
    page.goto(f"{live_server.url}{PORTFOLIO_PATH}")
    expect(page.locator("#about", has_text=unique)).to_be_visible()


def test_non_owner_sees_no_edit_controls(page: Page, live_server, seed):
    _admin_login(page, live_server, "other")

    page.goto(f"{live_server.url}{PORTFOLIO_PATH}?edit=true")

    # The page still renders for an authenticated non-owner ...
    expect(page.locator("h1", has_text="Portfolio").first).to_be_visible()
    # ... but no edit affordances are present.
    assert page.locator("#edit-mode").count() == 0
    assert page.locator("#about svg[hx-get]").count() == 0


def test_anonymous_can_view_but_not_edit(browser: Browser, live_server, seed):
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}{PORTFOLIO_PATH}?edit=true")
        expect(page.locator("h1", has_text="Portfolio").first).to_be_visible()
        assert page.locator("#edit-mode").count() == 0
        assert page.locator("#about svg[hx-get]").count() == 0
    finally:
        page.close()
        context.close()
