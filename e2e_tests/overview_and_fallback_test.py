"""Live-server browser coverage for navigation ordering/grouping and theme
template fallback -- the product paths, asserting visible structure and
rendered content rather than just HTTP status.
"""

import pytest
from playwright.sync_api import Browser, Page, expect

PASSWORD = "overview-pw"


@pytest.fixture
def seed(transactional_db, django_user_model):
    from django_resume.models import Resume

    owner = django_user_model.objects.create_superuser(
        username="jochen", email="jochen@example.com", password=PASSWORD
    )
    Resume.objects.create(name="Jochen", slug="jochen", owner=owner)
    # A second resume whose active theme ships no page templates, to exercise
    # the plain fallback in a real browser.
    ghost = Resume.objects.create(name="Ghosty", slug="ghosty", owner=owner)
    ghost.plugin_data["theme"] = {"name": "ghost-theme-with-no-templates"}
    ghost.save()
    return {"owner": owner}


def _admin_login(page: Page, live_server, username: str) -> None:
    page.goto(f"{live_server.url}/admin/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", PASSWORD)
    page.click('input[type="submit"]')
    page.wait_for_url(f"{live_server.url}/admin/")


def test_overview_renders_grouped_ordered_nav(page: Page, live_server, seed):
    _admin_login(page, live_server, "jochen")
    page.goto(f"{live_server.url}/resume/")

    row = page.locator("#resume-jochen")
    expect(row).to_be_visible()

    # The overview keeps the compact inline list layout.
    expect(row.get_by_text("Jochen:", exact=False)).to_be_visible()

    # Links appear in explicit nav_order, NOT registration order: PortfolioPage
    # registers last but nav_order=15 puts it between Cover (10) and CV (20).
    link_texts = [t.strip() for t in row.get_by_role("link").all_inner_texts()]
    assert link_texts == ["Cover", "Portfolio", "CV", "403", "Themes"]

    # Public page links still precede owner-only actions in the row.
    row_text = row.inner_text()
    assert row_text.index("CV") < row_text.index("403")


def test_page_renders_via_plain_fallback_for_themeless_theme(
    browser: Browser, live_server, seed
):
    # The "ghosty" resume's active theme ships no templates; the portfolio page
    # (third-party + capability-selected) must still render -- through the plain
    # fallback -- rather than 500 on TemplateDoesNotExist.
    context = browser.new_context()
    page = context.new_page()
    try:
        page.goto(f"{live_server.url}/resume/ghosty/portfolio/")
        # Visible content from the plain portfolio template proves it rendered.
        expect(page.locator("h1", has_text="Portfolio").first).to_be_visible()
        # The identity section fragment also resolved (coherent fallback, not a
        # half-rendered frame).
        expect(page.locator("#identity")).to_be_visible()
    finally:
        page.close()
        context.close()
