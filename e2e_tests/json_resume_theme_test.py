"""Browser coverage for the example JSON Resume theme catalog flow."""

import pytest
from playwright.sync_api import Page, expect

PASSWORD = "json-theme-pw"


@pytest.fixture
def seed(transactional_db, django_user_model):
    from django_resume.models import Resume

    owner = django_user_model.objects.create_superuser(
        username="jochen", email="jochen@example.com", password=PASSWORD
    )
    resume = Resume.objects.create(name="Jochen", slug="jochen", owner=owner)
    resume.plugin_data["identity"] = {"name": "Jochen Example"}
    resume.save()
    return {"owner": owner, "resume": resume}


def _admin_login(page: Page, live_server, username: str) -> None:
    page.goto(f"{live_server.url}/admin/login/")
    page.fill("#id_username", username)
    page.fill("#id_password", PASSWORD)
    page.click('input[type="submit"]')
    page.wait_for_url(f"{live_server.url}/admin/")


def test_owner_previews_then_uses_catalog_json_resume_theme(
    page: Page, live_server, seed, monkeypatch
):
    from django_resume.formats.json_resume.themes import (
        RenderedTheme,
        catalog_theme,
        selected_theme_name,
    )

    monkeypatch.setattr(
        "django_resume.views.install_catalog_theme", lambda key: catalog_theme(key)
    )

    def fake_preview_render(resume, key):
        assert selected_theme_name(resume) is None
        return RenderedTheme(
            html=f"<html><body><h1>{key.title()} Preview</h1><p>Jochen Example</p></body></html>",
            theme_name="jsonresume-theme-even",
            notes=(),
        )

    monkeypatch.setattr("django_resume.views.render_catalog_theme", fake_preview_render)

    def fake_selected_render(resume):
        assert selected_theme_name(resume) == "jsonresume-theme-even"
        return RenderedTheme(
            html="<html><body><h1>Even Theme Rendered</h1><p>Jochen Example</p></body></html>",
            theme_name="jsonresume-theme-even",
            notes=(),
        )

    monkeypatch.setattr(
        "django_resume.views.render_selected_theme", fake_selected_render
    )

    _admin_login(page, live_server, "jochen")
    page.goto(f"{live_server.url}/resume/")
    row = page.locator("#resume-jochen")
    expect(row.get_by_role("link", name="JSON Themes")).to_be_visible()
    row.get_by_role("link", name="JSON Themes").click()

    expect(page.locator("h1", has_text="JSON Resume Render Themes")).to_be_visible()
    expect(page.get_by_role("heading", name="Render theme catalog")).to_be_visible()
    expect(page.get_by_text("jsonresume-theme-even@0.26.1")).to_be_visible()
    expect(page.get_by_text("Development discovery")).not_to_be_visible()
    expect(page.get_by_role("button", name="Install and apply")).to_have_count(0)

    page.get_by_label("Filter render theme catalog").fill("even")
    expect(page.locator("[data-theme-card]").filter(has_text="Even")).to_be_visible()

    even_card = page.locator("[data-theme-card]").filter(
        has_text="jsonresume-theme-even"
    )
    expect(even_card.locator("img")).to_have_attribute(
        "src", "https://jsonresume.org/img/themes/even.png"
    )

    with page.expect_popup() as popup_info:
        even_card.get_by_role("button", name="Preview render").click(force=True)
    preview = popup_info.value
    expect(preview.locator("h1", has_text="Even Preview")).to_be_visible()
    expect(preview.get_by_text("Jochen Example")).to_be_visible()
    preview.close()

    expect(
        page.get_by_text("No JSON Resume render theme is selected yet.")
    ).to_be_visible()

    even_card.get_by_role("button", name="Use render theme").click(force=True)
    expect(page.get_by_text("Selected JSON Resume render theme:")).to_be_visible()
    expect(page.get_by_text("jsonresume-theme-even", exact=True)).to_be_visible()

    rendered_href = page.get_by_role("link", name="Open rendered page").get_attribute(
        "href"
    )
    assert rendered_href is not None
    rendered = page.context.new_page()
    try:
        rendered.goto(f"{live_server.url}{rendered_href}")
        expect(rendered.locator("h1", has_text="Even Theme Rendered")).to_be_visible()
        expect(rendered.get_by_text("Jochen Example")).to_be_visible()
    finally:
        rendered.close()


def test_catalog_use_button_shows_pending_feedback(
    page: Page, live_server, seed, monkeypatch
):
    from django_resume.formats.json_resume.themes import catalog_theme

    monkeypatch.setattr(
        "django_resume.views.install_catalog_theme", lambda key: catalog_theme(key)
    )

    _admin_login(page, live_server, "jochen")
    page.goto(f"{live_server.url}/resume/jochen/json-resume/themes/")
    page.evaluate(
        """() => {
            const form = document.querySelector("[data-theme-install-form]");
            form.addEventListener("submit", event => event.preventDefault(), {capture: true});
        }"""
    )

    button = page.locator("[data-install-submit]").first
    expect(button).to_have_text("Use render theme")
    button.click()

    expect(button).to_be_disabled()
    expect(button).to_have_text("Installing...")
    expect(page.locator("[data-install-status]").first).to_be_visible()
