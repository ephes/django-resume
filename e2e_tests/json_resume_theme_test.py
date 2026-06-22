"""Browser coverage for the example JSON Resume theme selector flow."""

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


def test_owner_searches_installs_applies_and_opens_json_resume_theme(
    page: Page, live_server, seed, monkeypatch
):
    from django_resume.formats.json_resume.themes import (
        RenderedTheme,
        ThemeSearchResult,
        selected_theme_name,
    )

    monkeypatch.setattr(
        "django_resume.views.search_themes",
        lambda query: [
            ThemeSearchResult(
                name="jsonresume-theme-even",
                version="0.26.1",
                description="Flat JSON Resume theme",
                keywords=("jsonresume-theme",),
            )
        ],
    )
    monkeypatch.setattr("django_resume.views.install_theme", lambda package_name: None)

    def fake_render(resume):
        assert selected_theme_name(resume) == "jsonresume-theme-even"
        return RenderedTheme(
            html="<html><body><h1>Even Theme Rendered</h1><p>Jochen Example</p></body></html>",
            theme_name="jsonresume-theme-even",
            notes=(),
        )

    monkeypatch.setattr("django_resume.views.render_selected_theme", fake_render)

    _admin_login(page, live_server, "jochen")
    page.goto(f"{live_server.url}/resume/")
    row = page.locator("#resume-jochen")
    expect(row.get_by_role("link", name="Themes")).to_be_visible()
    row.get_by_role("link", name="Themes").click()

    expect(page.locator("h1", has_text="JSON Resume Themes")).to_be_visible()
    page.get_by_label("Theme search").fill("even")
    page.get_by_role("button", name="Search").click()

    expect(page.get_by_text("jsonresume-theme-even")).to_be_visible()
    page.get_by_role("button", name="Install and apply").click(force=True)

    expect(page.get_by_text("Selected theme:")).to_be_visible()
    expect(page.get_by_role("code")).to_have_text("jsonresume-theme-even")

    with page.expect_popup() as popup_info:
        page.get_by_role("link", name="Open rendered page").click(force=True)
    rendered = popup_info.value
    expect(rendered.locator("h1", has_text="Even Theme Rendered")).to_be_visible()
    expect(rendered.get_by_text("Jochen Example")).to_be_visible()
    rendered.close()


def test_theme_install_button_shows_pending_feedback(
    page: Page, live_server, seed, monkeypatch
):
    from django_resume.formats.json_resume.themes import ThemeSearchResult

    monkeypatch.setattr(
        "django_resume.views.search_themes",
        lambda query: [
            ThemeSearchResult(
                name="jsonresume-theme-even",
                version="0.26.1",
                description="Flat JSON Resume theme",
                keywords=("jsonresume-theme",),
            )
        ],
    )

    _admin_login(page, live_server, "jochen")
    page.goto(f"{live_server.url}/resume/jochen/json-resume/themes/")
    page.evaluate(
        """() => {
            const form = document.querySelector("[data-theme-install-form]");
            form.addEventListener("submit", event => event.preventDefault(), {capture: true});
        }"""
    )

    button = page.locator("[data-install-submit]")
    expect(button).to_have_text("Install and apply")
    button.click()

    expect(button).to_be_disabled()
    expect(button).to_have_text("Installing...")
    expect(page.locator("[data-install-status]")).to_be_visible()
