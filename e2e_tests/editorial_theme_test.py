"""Live-server browser tests for the editorial page theme.

Run with::

    uv run pytest --ds=e2e_tests.settings e2e_tests/editorial_theme_test.py
"""

import pytest
from playwright.sync_api import Page, expect

PASSWORD = "editorial-pw"


@pytest.fixture
def editorial_resume(transactional_db, django_user_model):
    from django_resume.models import Resume

    owner = django_user_model.objects.create_superuser(
        username="editorial", email="editorial@example.com", password=PASSWORD
    )
    return Resume.objects.create(
        name="Jane",
        slug="jane",
        owner=owner,
        plugin_data={
            "theme": {"name": "editorial"},
            "token": {"flat": {"token_required": False}},
            "identity": {
                "name": "Jane Doe",
                "tagline": "Art Director",
                "email": "jane@example.com",
                "website": "https://portfolio.example",
            },
            "employed_timeline": {
                "flat": {"title": "Work Experience"},
                "items": [
                    {
                        "id": "w1",
                        "company_name": "Example Studio",
                        "company_url": "",
                        "role": "Designer",
                        "description": "Designed things.",
                        "start": "2020",
                        "end": "2024",
                        "badges": [],
                        "position": 0,
                    }
                ],
            },
            "cover": {
                "flat": {
                    "subject": "Design application",
                    "salutation": "Hello team,",
                    "closing": "Best regards",
                },
                "items": [{"id": "p1", "title": "", "text": "My letter."}],
            },
        },
    )


@pytest.mark.parametrize("path", ["cv/", ""])
def test_print_button_is_revealed_by_script_and_hidden_in_print(
    page: Page, live_server, editorial_resume, path
):
    page.goto(f"{live_server.url}/resume/jane/{path}")

    button = page.get_by_role("button", name="Print / save as PDF")
    expect(button).to_be_visible()
    page.evaluate("window.print = () => { window.__printed = true; }")
    button.click()
    assert page.evaluate("window.__printed") is True

    page.emulate_media(media="print")
    expect(button).to_be_hidden()


def test_print_button_stays_hidden_without_javascript(
    browser, live_server, editorial_resume
):
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()
    page.goto(f"{live_server.url}/resume/jane/cv/")

    expect(page.get_by_role("button", name="Print / save as PDF")).to_be_hidden()
    # the portfolio link does not depend on the script
    expect(page.get_by_role("link", name="Portfolio")).to_be_visible()
    context.close()


@pytest.mark.parametrize("width", [360, 1440])
def test_cv_has_no_horizontal_overflow_and_written_labels(
    page: Page, live_server, editorial_resume, width
):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{live_server.url}/resume/jane/cv/")

    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    )
    assert overflow <= 0
    expect(page.locator(".hw-label[data-hw]").first).to_be_attached()
    expect(page.locator(".hw-text", has_text="Work Experience")).to_have_count(1)


def _login(page: Page, live_server) -> None:
    page.goto(f"{live_server.url}/admin/login/")
    page.fill("#id_username", "editorial")
    page.fill("#id_password", PASSWORD)
    page.click('input[type="submit"]')
    page.wait_for_url(f"{live_server.url}/admin/")


def test_identity_save_refreshes_portfolio_link(
    page: Page, live_server, editorial_resume
):
    _login(page, live_server)
    page.goto(f"{live_server.url}/resume/jane/cv/?edit=true")

    page.locator("#identity svg.edit-icon-small").first.click()
    page.locator('#identity [contenteditable][data-field="website"]').fill(
        "https://new-portfolio.example"
    )
    with page.expect_navigation():
        page.click("#submit-identity")

    expect(page.get_by_role("link", name="Portfolio")).to_have_attribute(
        "href", "https://new-portfolio.example"
    )


def test_cover_flat_save_refreshes_letter_body(
    page: Page, live_server, editorial_resume
):
    _login(page, live_server)
    page.goto(f"{live_server.url}/resume/jane/?edit=true")

    page.locator("#cover-flat svg.edit-icon-small").first.click()
    page.fill('#cover-flat input[name="closing"]', "Warm regards")
    with page.expect_navigation():
        page.click("#submit-cover")

    expect(page.locator(".cover-closing")).to_have_text("Warm regards")


def test_handwriting_label_inserted_by_htmx_is_visible(
    page: Page, live_server, editorial_resume
):
    from django_resume.models import Resume

    resume = Resume.objects.get(slug="jane")
    resume.plugin_data["token"]["flat"]["token_required"] = True
    resume.plugin_data["permission_denied"] = {
        "title": "Request my CV",
        "sub_title": "By invitation",
        "email": "access@example.com",
        "text": "Please ask.",
    }
    resume.save()
    _login(page, live_server)
    page.goto(f"{live_server.url}/resume/jane/403/?edit=true")
    page.wait_for_function("document.documentElement.classList.contains('js-hw')")

    page.locator("#permission_denied svg.edit-icon-small").first.click()
    page.locator("#permission_denied form").evaluate("form => form.requestSubmit()")
    page.wait_for_selector("#permission_denied form", state="detached")
    page.wait_for_selector("#permission_denied .editorial-403-title .hw-svg")

    ink = page.locator("#permission_denied .hw-ink-group")
    assert ink.evaluate("el => getComputedStyle(el).visibility") == "visible"


def test_print_shows_lines_that_have_not_been_drawn_yet(
    page: Page, live_server, editorial_resume
):
    editorial_resume.plugin_data["skills"] = {"badges": ["Branding"]}
    editorial_resume.plugin_data["languages"] = {
        "flat": {"title": "Languages"},
        "items": [{"id": "l1", "name": "English", "level": 100, "position": 0}],
    }
    editorial_resume.save()
    page.set_viewport_size({"width": 1440, "height": 400})
    page.goto(f"{live_server.url}/resume/jane/cv/")
    page.wait_for_function("document.documentElement.classList.contains('js-lines')")

    page.emulate_media(media="print")

    for selector in (".timeline-entry", ".cv-rail-body > section + section"):
        element = page.locator(selector).first
        assert not element.evaluate("el => el.classList.contains('cv-line-drawn')")
        transform = element.evaluate("el => getComputedStyle(el, '::before').transform")
        assert transform in ("none", "matrix(1, 0, 0, 1, 0, 0)"), selector


def test_resources_rail_hidden_without_website_and_javascript(
    browser, live_server, editorial_resume
):
    editorial_resume.plugin_data["identity"].pop("website")
    editorial_resume.save()
    context = browser.new_context(java_script_enabled=False)
    page = context.new_page()

    page.goto(f"{live_server.url}/resume/jane/cv/")

    expect(page.locator(".cv-rail--resources")).to_be_hidden()
    context.close()


def test_owner_switches_resume_language(page: Page, live_server, editorial_resume):
    _login(page, live_server)
    page.goto(f"{live_server.url}/resume/jane/?edit=true")

    page.locator("#theme svg.edit-icon-small").first.click()
    page.select_option("#theme select#language", "de")
    with page.expect_navigation():
        page.click("#submit-theme")

    expect(page.locator("html")).to_have_attribute("lang", "de")
    page.goto(f"{live_server.url}/resume/jane/cv/")
    expect(page.locator(".hw-text", has_text="Kontakt")).to_have_count(1)
