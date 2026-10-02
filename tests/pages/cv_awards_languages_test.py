"""The plain and headwind CVs show awards and languages."""

import pytest
from django.urls import reverse

from django_resume.plugins import plugin_registry

THEMES = ["plain", "headwind"]


def used_templates(response) -> set[str]:
    return {template.name for template in response.templates if template.name}


@pytest.fixture
def cv_resume(resume):
    resume.owner.save()
    resume.plugin_data = {
        "token": {"flat": {"token_required": False}},
        "identity": {"name": "Jane Doe"},
        "awards": {
            "flat": {"title": "Awards"},
            "items": [
                {
                    "id": "a1",
                    "title": "Design Award: Bronze",
                    "project": "Example Campaign",
                    "year": "2024",
                    "position": 0,
                }
            ],
        },
        "languages": {
            "flat": {"title": "Languages"},
            "items": [
                {"id": "l1", "name": "German", "level": 100, "note": "native"},
            ],
        },
    }
    resume.save()
    return resume


def set_theme(resume, theme):
    resume.plugin_data["theme"] = {"name": theme}
    resume.save()


@pytest.mark.django_db
@pytest.mark.parametrize("theme", THEMES)
def test_cv_shows_awards_and_languages(client, cv_resume, theme):
    set_theme(cv_resume, theme)

    response = client.get(reverse("resume:cv", kwargs={"slug": cv_resume.slug}))

    assert response.status_code == 200
    html = response.content.decode()
    assert "Design Award: Bronze" in html
    assert "Example Campaign" in html
    assert "German" in html
    assert 'aria-valuenow="100"' in html
    assert "native" in html
    templates = used_templates(response)
    assert f"django_resume/plugins/awards/{theme}/content.html" in templates
    assert f"django_resume/plugins/languages/{theme}/content.html" in templates


@pytest.mark.django_db
@pytest.mark.parametrize("theme", THEMES)
def test_cv_hides_empty_awards_and_languages(client, cv_resume, theme):
    set_theme(cv_resume, theme)
    del cv_resume.plugin_data["awards"]
    del cv_resume.plugin_data["languages"]
    cv_resume.save()

    response = client.get(reverse("resume:cv", kwargs={"slug": cv_resume.slug}))

    templates = used_templates(response)
    assert f"django_resume/plugins/awards/{theme}/content.html" not in templates
    assert f"django_resume/plugins/languages/{theme}/content.html" not in templates


@pytest.mark.django_db
@pytest.mark.parametrize("theme", THEMES)
def test_cv_edit_mode_offers_empty_awards_and_languages(client, cv_resume, theme):
    set_theme(cv_resume, theme)
    del cv_resume.plugin_data["awards"]
    del cv_resume.plugin_data["languages"]
    cv_resume.save()
    client.force_login(cv_resume.owner)

    response = client.get(
        reverse("resume:cv", kwargs={"slug": cv_resume.slug}), {"edit": "true"}
    )

    html = response.content.decode()
    awards = plugin_registry.get_plugin("awards")
    languages = plugin_registry.get_plugin("languages")
    assert awards.inline.get_edit_item_url(cv_resume.pk) in html
    assert languages.inline.get_edit_item_url(cv_resume.pk) in html


@pytest.mark.django_db
@pytest.mark.parametrize("theme", THEMES)
def test_awards_and_languages_inline_round_trip(client, cv_resume, theme):
    set_theme(cv_resume, theme)
    client.force_login(cv_resume.owner)
    cases = [
        (
            "awards",
            {
                "id": "a1",
                "title": "Design Award: Silver",
                "project": "Example Campaign",
                "year": "2025",
                "position": 0,
            },
            "Design Award: Silver",
        ),
        (
            "languages",
            {"id": "l1", "name": "German", "level": 90, "note": "fluent"},
            'aria-valuenow="90"',
        ),
    ]
    for name, data, expected in cases:
        plugin = plugin_registry.get_plugin(name)
        prefix = f"django_resume/plugins/{name}/{theme}/"

        form = client.get(plugin.inline.get_edit_item_url(cv_resume.pk, data["id"]))
        assert f"{prefix}item_form.html" in used_templates(form)

        item = client.post(plugin.inline.get_post_item_url(cv_resume.pk), data)
        assert f"{prefix}item.html" in used_templates(item)
        assert expected in item.content.decode()

        flat_form = client.get(plugin.inline.get_edit_flat_url(cv_resume.pk))
        assert f"{prefix}flat_form.html" in used_templates(flat_form)

        flat = client.post(
            plugin.inline.get_edit_flat_post_url(cv_resume.pk), {"title": "Renamed"}
        )
        assert f"{prefix}flat.html" in used_templates(flat)
        assert "Renamed" in flat.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("theme", [*THEMES, "editorial"])
def test_item_forms_render_missing_optional_fields_empty(client, cv_resume, theme):
    set_theme(cv_resume, theme)
    # entries saved without their optional fields
    cv_resume.plugin_data["awards"]["items"] = [
        {"id": "a1", "title": "Bronze", "position": 0}
    ]
    cv_resume.plugin_data["languages"]["items"] = [
        {"id": "l1", "name": "German", "level": 100}
    ]
    cv_resume.save()
    client.force_login(cv_resume.owner)
    awards = plugin_registry.get_plugin("awards")
    languages = plugin_registry.get_plugin("languages")

    for url in (
        awards.inline.get_edit_item_url(cv_resume.pk, "a1"),
        languages.inline.get_edit_item_url(cv_resume.pk, "l1"),
        languages.inline.get_edit_item_url(cv_resume.pk),
    ):
        html = client.get(url).content.decode()
        assert "None" not in html, url


@pytest.mark.django_db
def test_headwind_language_bar_fill_survives_print_overrides(client, cv_resume):
    set_theme(cv_resume, "headwind")

    html = client.get(
        reverse("resume:cv", kwargs={"slug": cv_resume.slug})
    ).content.decode()

    # headwind's print CSS resets gradient backgrounds to white
    fill = html.split('role="meter"', 1)[1].split("</div>", 1)[0]
    assert "bg-gradient" not in fill
