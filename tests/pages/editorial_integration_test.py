"""Regression boundaries between editorial content and the 0.3.0 page API."""

import pytest
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse

from django_resume.pages import ResumePage, by_capability, page_registry
from django_resume.pages.base import build_section_context


@pytest.fixture
def editorial_resume(resume):
    resume.owner.save()
    resume.plugin_data = {
        "theme": {"name": "editorial"},
        "token": {"flat": {"token_required": False}},
        "cover": {
            "flat": {
                "title": "Application",
                "recipient": "Example studio",
                "place_date": "Düsseldorf, 28.09.2026",
                "subject": "Design application",
                "salutation": "Hello team",
            },
            "items": [{"id": "intro", "title": "Hello", "text": "My letter."}],
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
                    "id": "de",
                    "name": "Deutsch",
                    "level": 100,
                    "note": "Muttersprache",
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
def test_editorial_builtin_pages_preserve_content(client, editorial_resume):
    resume = editorial_resume
    cover = client.get(reverse("resume:detail", kwargs={"slug": resume.slug}))
    assert cover.status_code == 200
    assert "django_resume/pages/editorial/resume_detail.html" in {
        t.name for t in cover.templates
    }
    assert cover.context["cover"]["subject"] == "Design application"
    assert cover.context["cover"]["recipient"] == "Example studio"
    assert cover.context["cover"]["salutation"] == "Hello team"
    assert cover.context["cover"]["place_date"] == "Düsseldorf, 28.09.2026"
    assert "My letter." in cover.content.decode()

    cv = client.get(reverse("resume:cv", kwargs={"slug": resume.slug}))
    assert cv.status_code == 200
    assert "django_resume/pages/editorial/resume_cv.html" in {
        t.name for t in cv.templates
    }
    html = cv.content.decode()
    assert html.index("First school") < html.index("Later school")
    assert "BA" in html and "MA" in html
    assert 'aria-valuetext="Muttersprache"' in html
    assert "Design prize" in html
    resume.refresh_from_db()
    assert resume.plugin_data["cover"]["items"][0]["text"] == "My letter."


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
    assert context["languages"]["ordered_entries"][0]["note"] == "Muttersprache"
    assert context["awards"]["ordered_entries"][0]["title"] == "Design prize"
    assert "cover" not in context


@pytest.mark.django_db
def test_overview_and_editorial_fragment_include_registered_portfolio(
    client, editorial_resume
):
    class PortfolioPage(ResumePage):
        url_name = "editorial-test-portfolio"
        nav_title = "Portfolio"
        nav_order = 15
        nav_group = "Resume"

        def nav_url(self, resume):
            return "/katharina/"

    page_registry.register(PortfolioPage)
    try:
        # The real overview route deliberately uses plain, regardless of the
        # resume's theme. The editorial fragment is a reusable template alias.
        client.force_login(editorial_resume.owner)
        response = client.get(reverse("resume:list"))
        assert response.status_code == 200
        assert "django_resume/pages/plain/resume_list.html" in {
            t.name for t in response.templates
        }
        fragment = render_to_string(
            "django_resume/pages/editorial/resume_list_main.html",
            {"resumes": [editorial_resume], "is_editable": True},
        )
    finally:
        page_registry.unregister(PortfolioPage)
    for html in (response.content.decode(), fragment):
        assert (
            html.index(">Cover</a>")
            < html.index(">Portfolio</a>")
            < html.index(">CV</a>")
        )
        assert 'href="/katharina/"' in html
        assert ">403</a>" not in html


@pytest.mark.django_db
def test_editorial_token_denied_cv_preserves_theme_and_referrer_policy(
    client, editorial_resume
):
    editorial_resume.plugin_data["token"]["flat"]["token_required"] = True
    editorial_resume.save()
    response = client.get(reverse("resume:cv", kwargs={"slug": editorial_resume.slug}))
    assert response.status_code == 403
    assert response["Referrer-Policy"] == "no-referrer"
    templates = {t.name for t in response.templates}
    assert "django_resume/pages/editorial/cv_403.html" in templates
    assert "django_resume/plugins/permission_denied/editorial/content.html" in templates
    html = response.content.decode()
    assert "Request my CV" in html
    assert "Access by invitation" in html
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
    templates = {t.name for t in response.templates}
    assert "django_resume/pages/editorial/cv_403.html" in templates
    assert "django_resume/plugins/permission_denied/editorial/content.html" in templates
    html = response.content.decode()
    assert "Request my CV" in html
    assert "Access by invitation" in html
    assert "<strong>access token</strong>" in html
    assert f'hx-get="{response.context["permission_denied"]["edit_url"]}"' in html
