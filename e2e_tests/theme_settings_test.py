"""Page-theme settings persist across themes and show bound name errors."""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture
def settings_resume(test_user):
    from django_resume.models import Resume

    return Resume.objects.create(
        name="Synthetic settings validation",
        slug="settings-validation",
        owner=test_user,
        plugin_data={
            "theme": {"name": "plain", "language": "en"},
            "token": {"flat": {"token_required": False}},
            "identity": {"name": "Synthetic Person"},
        },
    )


def select_theme(page: Page, theme: str) -> None:
    field = page.locator('#form-theme [name="name"]')
    if field.first.evaluate("element => element.tagName") == "SELECT":
        field.select_option(theme)
    else:
        page.locator(f'#form-theme [name="name"][value="{theme}"]').locator(
            ".."
        ).click()


@pytest.mark.parametrize(
    ("initial", "selected"),
    [("plain", "editorial"), ("editorial", "headwind"), ("headwind", "plain")],
)
def test_theme_and_language_switch_persists_and_preselects(
    logged_in_page: Page, live_server, settings_resume, initial, selected
):
    resume = settings_resume
    resume.plugin_data["theme"]["name"] = initial
    resume.save()
    page = logged_in_page
    page.goto(f"{live_server.url}/resume/{resume.slug}/?edit=true")
    page.locator("#theme [hx-get]").click()
    select_theme(page, selected)
    page.locator("#language").select_option("de")
    with page.expect_navigation():
        page.locator("#submit-theme").click()
    resume.refresh_from_db()
    assert resume.plugin_data["theme"] == {"name": selected, "language": "de"}
    expect(page.locator("html")).to_have_attribute("lang", "de")
    if selected == "editorial":
        expect(page.locator("body")).to_have_class("editorial-page")
    elif selected == "headwind":
        expect(page.locator("body")).to_have_class("font-sans antialiased")
    else:
        expect(page.locator('link[href*="css/styles.css"]')).to_have_count(1)
    page.locator("#theme [hx-get]").click()
    field = page.locator('#form-theme [name="name"]')
    if field.first.evaluate("element => element.tagName") == "SELECT":
        expect(field).to_have_value(selected)
    else:
        expect(
            page.locator(f'#form-theme [name="name"][value="{selected}"]')
        ).to_be_checked()
    expect(page.locator("#language")).to_have_value("de")


@pytest.mark.parametrize("theme", ["plain", "editorial", "headwind"])
@pytest.mark.parametrize("name", ["", "x" * 101], ids=["blank", "overlong"])
def test_invalid_theme_name_shows_error_without_changing_saved_settings(
    logged_in_page: Page, live_server, settings_resume, client, theme, name
):
    from django_resume.plugins import plugin_registry

    resume = settings_resume
    resume.plugin_data["theme"]["name"] = theme
    resume.save()
    client.force_login(resume.owner)
    response = client.post(
        plugin_registry.get_plugin("theme").inline.get_post_url(resume.pk),
        {"name": name, "language": "de"},
    )
    assert response.status_code == 200
    error = str(response.context["form"].errors["name"][0])
    resume.refresh_from_db()
    assert resume.plugin_data["theme"] == {"name": theme, "language": "en"}

    page = logged_in_page
    page.goto(f"{live_server.url}/resume/{resume.slug}/?edit=true")
    page.locator("#theme [hx-get]").click()
    field = page.locator('#form-theme [name="name"]')
    if field.first.evaluate("element => element.tagName") == "SELECT":
        field.evaluate(
            "(select, value) => select.add(new Option('Invalid theme', value))", name
        )
        field.select_option(name)
    else:
        field.first.evaluate(
            "(input, value) => { input.value = value; input.checked = true; }", name
        )
    page.locator("#language").select_option("de")
    navigations = []
    page.on("framenavigated", lambda frame: navigations.append(frame.url))
    with page.expect_response(
        lambda response: response.request.method == "POST"
    ) as posted:
        page.locator("#submit-theme").click()
    assert posted.value.status == 200
    expect(page.locator("#form-theme")).to_be_visible()
    resume.refresh_from_db()
    assert resume.plugin_data["theme"] == {"name": theme, "language": "en"}
    expect(page.locator("#theme")).to_contain_text(error)
    expect(page.locator("#language")).to_have_value("de")
    assert navigations == []
