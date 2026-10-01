"""The editorial page theme renders the CV, cover letter and denial page."""

import pytest
from django.test import RequestFactory
from django.urls import reverse
from django.utils import translation

from django_resume.pages import by_capability
from django_resume.pages.base import build_section_context


def template_names(response):
    return {template.name for template in response.templates}


@pytest.fixture
def editorial_resume(resume):
    resume.owner.save()
    resume.plugin_data = {
        "theme": {"name": "editorial"},
        "token": {"flat": {"token_required": False}},
        "identity": {
            "name": "Jane Mary Doe",
            "tagline": "Art Director",
            "email": "jane@example.com",
            "website": "https://portfolio.example",
        },
        "cover": {
            "flat": {
                "title": "Application",
                "recipient": "Example Studio\nMain Street 1",
                "place_date": "Example City, 2026-09-28",
                "subject": "Design application",
                "salutation": "Hello team,",
                "closing": "Best regards",
                "signature_name": "Jane",
            },
            "items": [{"id": "intro", "title": "Hello", "text": "My letter."}],
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
                    "badges": ["Client A", "Client B"],
                    "position": 0,
                }
            ],
        },
        "education": {
            "flat": {"title": "Education"},
            "items": [
                {
                    "id": "later",
                    "school_name": "Later school",
                    "degree": "MA",
                    "position": 1,
                },
                {
                    "id": "first",
                    "school_name": "First school",
                    "degree": "BA",
                    "position": 0,
                },
            ],
        },
        "languages": {
            "flat": {"title": "Languages"},
            "items": [
                {
                    "id": "en",
                    "name": "English",
                    "level": 100,
                    "note": "Native",
                    "position": 0,
                }
            ],
        },
        "awards": {
            "flat": {"title": "Awards"},
            "items": [
                {
                    "id": "award",
                    "title": "Design prize",
                    "project": "Identity",
                    "year": "2026",
                    "position": 0,
                }
            ],
        },
        "permission_denied": {
            "title": "Request my CV",
            "sub_title": "Access by invitation",
            "email": "access@example.com",
            "text": "Please request an **access token**.",
        },
    }
    resume.save()
    return resume


@pytest.mark.django_db
def test_editorial_cover_letter_renders_letter_details(client, editorial_resume):
    response = client.get(
        reverse("resume:detail", kwargs={"slug": editorial_resume.slug})
    )

    assert response.status_code == 200
    assert "django_resume/pages/editorial/resume_detail.html" in template_names(
        response
    )
    html = response.content.decode()
    assert "<title>Cover letter — Jane Mary Doe</title>" in html
    assert "Example Studio<br>Main Street 1" in html
    assert "Example City, 2026-09-28" in html
    assert "Design application" in html
    assert "Hello team," in html
    assert "My letter." in html
    assert "Best regards" in html
    # signature name rendered as a handwriting label with the real text kept
    assert '<span class="hw-text">Jane</span>' in html
    assert "django_resume/css/editorial/cover.css" in html


@pytest.mark.django_db
def test_editorial_cv_renders_sections_and_resources(client, editorial_resume):
    response = client.get(reverse("resume:cv", kwargs={"slug": editorial_resume.slug}))

    assert response.status_code == 200
    assert "django_resume/pages/editorial/resume_cv.html" in template_names(response)
    html = response.content.decode()
    # the first word is set apart, the rest of the name is kept
    assert '<span class="cv-firstname">Jane</span>' in html
    assert '<span class="cv-lastname">Mary Doe</span>' in html
    assert html.index("First school") < html.index("Later school")
    assert 'aria-valuetext="Native"' in html
    assert "Design prize" in html
    # rail labels are handwriting labels with the real text kept
    for label in ("Let&#x27;s talk about", "Education", "Resources", "Contact"):
        assert f'<span class="hw-text">{label}</span>' in html
    # the print button is hidden until print.js reveals it; no PDF files
    assert "data-editorial-print" in html
    assert "<li hidden data-editorial-print-container>" in html
    assert "django_resume/js/editorial/print.js" in html
    assert ".pdf" not in html
    assert '<a href="https://portfolio.example">Portfolio</a>' in html
    assert 'data-label="Clients:"' in html


@pytest.mark.django_db
def test_editorial_cv_hides_resources_rail_without_website(client, editorial_resume):
    del editorial_resume.plugin_data["identity"]["website"]
    editorial_resume.save()

    html = client.get(
        reverse("resume:cv", kwargs={"slug": editorial_resume.slug})
    ).content.decode()

    assert (
        '<section class="cv-rail cv-rail--resources" hidden data-editorial-print-container>'
        in html
    )
    assert ">Portfolio</a>" not in html


@pytest.mark.django_db
def test_editorial_theme_strings_are_translated_to_german(client, editorial_resume):
    with translation.override("de"):
        cv = client.get(reverse("resume:cv", kwargs={"slug": editorial_resume.slug}))
        cover = client.get(
            reverse("resume:detail", kwargs={"slug": editorial_resume.slug})
        )

    cv_html = cv.content.decode()
    assert '<html lang="de">' in cv_html
    assert "<title>Lebenslauf von Jane Mary Doe</title>" in cv_html
    for label in ("Sprechen wir über", "Ausbildung", "Ressourcen", "Kontakt"):
        assert f'<span class="hw-text">{label}</span>' in cv_html
    assert "Drucken / als PDF speichern" in cv_html
    assert 'data-label="Kunden:"' in cv_html
    assert "<title>Anschreiben — Jane Mary Doe</title>" in cover.content.decode()


@pytest.mark.django_db
def test_editorial_owner_edit_mode_renders_editors(client, editorial_resume):
    client.force_login(editorial_resume.owner)

    cover = client.get(
        reverse("resume:detail", kwargs={"slug": editorial_resume.slug}),
        {"edit": "true"},
    )
    cv = client.get(
        reverse("resume:cv", kwargs={"slug": editorial_resume.slug}), {"edit": "true"}
    )

    assert cover.status_code == 200 and cv.status_code == 200
    assert "hx-get=" in cover.content.decode()
    assert "hx-get=" in cv.content.decode()


@pytest.mark.django_db
@pytest.mark.parametrize("theme", ["plain", "headwind", "editorial"])
def test_theme_selector_offers_editorial(client, editorial_resume, theme):
    from django_resume.plugins import plugin_registry

    editorial_resume.plugin_data["theme"]["name"] = theme
    editorial_resume.save()
    client.force_login(editorial_resume.owner)
    plugin = plugin_registry.get_plugin("theme")

    response = client.get(plugin.inline.get_edit_url(editorial_resume.pk))

    assert response.status_code == 200
    assert 'value="editorial"' in response.content.decode()


@pytest.mark.django_db
def test_editorial_cover_flat_form_edits_signature(client, editorial_resume):
    from django_resume.plugins import plugin_registry

    client.force_login(editorial_resume.owner)
    plugin = plugin_registry.get_plugin("cover")

    response = client.get(plugin.inline.get_edit_flat_url(editorial_resume.pk))

    html = response.content.decode()
    assert "django_resume/plugins/cover/editorial/flat_form.html" in template_names(
        response
    )
    for field in ("recipient", "place_date", "subject", "salutation", "closing"):
        assert f'name="{field}"' in html
    assert 'name="signature_img"' in html
    assert 'name="clear_signature"' in html


@pytest.mark.django_db
def test_editorial_lists_selected_by_cv_capability(editorial_resume):
    request = RequestFactory().get("/")
    request.user = editorial_resume.owner

    context = build_section_context(
        request, editorial_resume, {}, by_capability("cv"), theme="editorial"
    )

    assert [item["id"] for item in context["education"]["ordered_entries"]] == [
        "first",
        "later",
    ]
    assert context["languages"]["ordered_entries"][0]["note"] == "Native"
    assert context["awards"]["ordered_entries"][0]["title"] == "Design prize"
    assert "cover" not in context


@pytest.mark.django_db
def test_editorial_token_denied_cv_keeps_theme_and_referrer_policy(
    client, editorial_resume
):
    editorial_resume.plugin_data["token"]["flat"]["token_required"] = True
    editorial_resume.save()

    response = client.get(reverse("resume:cv", kwargs={"slug": editorial_resume.slug}))

    assert response.status_code == 403
    assert response["Referrer-Policy"] == "no-referrer"
    templates = template_names(response)
    assert "django_resume/pages/editorial/cv_403.html" in templates
    assert "django_resume/plugins/permission_denied/editorial/content.html" in templates
    html = response.content.decode()
    assert "Request my CV" in html
    assert "<strong>access token</strong>" in html
    assert "mailto:access@example.com" in html
    assert "hx-get=" not in html


@pytest.mark.django_db
def test_editorial_owner_permission_editor_uses_themed_fragment(
    client, editorial_resume, django_user_model
):
    editorial_resume.plugin_data["token"]["flat"]["token_required"] = True
    editorial_resume.save()
    url = reverse("resume:403", kwargs={"slug": editorial_resume.slug}) + "?edit=true"
    assert client.get(url).status_code == 302
    other = django_user_model.objects.create_user(username="other-editorial")
    client.force_login(other)
    assert client.get(url).status_code == 403

    client.force_login(editorial_resume.owner)
    response = client.get(url)

    assert response.status_code == 200
    assert "django_resume/plugins/permission_denied/editorial/content.html" in (
        template_names(response)
    )
    html = response.content.decode()
    assert f'hx-get="{response.context["permission_denied"]["edit_url"]}"' in html
