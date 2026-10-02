"""Invalid resume-language settings stay open while successful saves reload."""

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.parametrize("theme", ["editorial", "plain", "headwind"])
def test_invalid_language_keeps_theme_form_open(
    logged_in_page: Page, live_server, test_user, client, theme
):
    from django_resume.models import Resume
    from django_resume.plugins import plugin_registry

    resume = Resume.objects.create(
        name="Synthetic theme validation",
        slug="theme-validation",
        owner=test_user,
        plugin_data={
            "theme": {"name": theme, "language": "en"},
            "token": {"flat": {"token_required": False}},
            "identity": {"name": "Synthetic Person"},
        },
    )
    client.force_login(test_user)
    invalid = client.post(
        plugin_registry.get_plugin("theme").inline.get_post_url(resume.pk),
        {"name": theme, "language": "xx"},
    )
    assert invalid.status_code == 200
    assert "Select a valid choice" in invalid.content.decode()
    page = logged_in_page
    page.goto(f"{live_server.url}/resume/{resume.slug}/?edit=true")
    page.locator("#theme [hx-get]").click()
    expect(page.locator("#form-theme")).to_be_visible()
    page.locator("#language").evaluate(
        "select => select.add(new Option('Invalid language', 'xx'))"
    )
    page.locator("#language").select_option("xx")
    navigations = []
    page.on("framenavigated", lambda frame: navigations.append(frame.url))
    with page.expect_response(
        lambda response: response.request.method == "POST"
    ) as posted:
        page.locator("#submit-theme").click()
    assert posted.value.status == 200
    expect(page.locator("#form-theme")).to_be_visible()
    expect(page.locator("#theme")).to_contain_text("Select a valid choice")
    # Observe the next page event-loop turn after HTMX processes the response.
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    assert navigations == []
    resume.refresh_from_db()
    assert resume.plugin_data["theme"] == {"name": theme, "language": "en"}

    page.locator("#language").select_option("de")
    with page.expect_navigation():
        page.locator("#submit-theme").click()
    resume.refresh_from_db()
    assert resume.plugin_data["theme"] == {"name": theme, "language": "de"}
    expect(page.locator("html")).to_have_attribute("lang", "de")
