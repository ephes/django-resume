"""List plugin link targets are reduced to safe schemes when rendered.

JSON Resume imports store item data without running the item forms, so the
forms' URL validation cannot be relied on at render time.
"""

import pytest
from django.urls import reverse

from django_resume.plugins.education import EducationItemForm
from django_resume.plugins.projects import ProjectItemForm
from django_resume.plugins.timelines import TimelineItemForm

THEMES = ["plain", "headwind", "editorial"]
DANGEROUS = "JaVaScRiPt:alert(document.domain)"


def timeline_item(item_id, url):
    return {
        "id": item_id,
        "role": "Developer",
        "company_name": f"Company {item_id}",
        "company_url": url,
        "description": "Work",
        "start": "2020",
        "end": "2022",
        "badges": [],
        "position": 0,
    }


@pytest.fixture
def cv_resume(resume):
    resume.owner.save()
    resume.plugin_data = {
        "token": {"flat": {"token_required": False}},
        "identity": {"name": "Jane Doe"},
        "employed_timeline": {
            "flat": {"title": "Employed"},
            "items": [
                timeline_item("w1", DANGEROUS),
                timeline_item("w2", "https://employer.example/"),
            ],
        },
        "freelance_timeline": {
            "flat": {"title": "Freelance"},
            "items": [timeline_item("f1", DANGEROUS)],
        },
        "projects": {
            "flat": {"title": "Projects"},
            "items": [
                {
                    "id": "p1",
                    "title": "Project",
                    "url": DANGEROUS,
                    "description": "Project",
                    "badges": [],
                    "position": 0,
                },
                {
                    "id": "p2",
                    "title": "Other project",
                    "url": "https://project.example/",
                    "description": "Project",
                    "badges": [],
                    "position": 1,
                },
            ],
        },
        "education": {
            "flat": {"title": "Education"},
            "items": [
                {
                    "id": "e1",
                    "school_name": "School",
                    "school_url": DANGEROUS,
                    "degree": "BSc",
                    "start": "2010",
                    "end": "2014",
                    "position": 0,
                },
                {
                    "id": "e2",
                    "school_name": "Other school",
                    "school_url": "https://school.example/",
                    "degree": "MSc",
                    "start": "2014",
                    "end": "2016",
                    "position": 1,
                },
            ],
        },
    }
    resume.save()
    return resume


@pytest.mark.django_db
@pytest.mark.parametrize("theme", THEMES)
@pytest.mark.parametrize("edit", [False, True])
def test_cv_does_not_render_dangerous_item_link_schemes(client, cv_resume, theme, edit):
    cv_resume.plugin_data["theme"] = {"name": theme}
    cv_resume.save()
    if edit:
        client.force_login(cv_resume.owner)

    response = client.get(
        reverse("resume:cv", kwargs={"slug": cv_resume.slug}),
        {"edit": "true"} if edit else {},
    )

    assert response.status_code == 200
    html = response.content.decode()
    assert "javascript:" not in html.lower()
    # The entries themselves and safe links are still rendered.
    assert "Company w1" in html
    assert 'href="https://employer.example/"' in html


@pytest.mark.django_db
@pytest.mark.parametrize("theme", ["plain", "headwind"])
def test_cv_keeps_safe_project_and_school_links(client, cv_resume, theme):
    cv_resume.plugin_data["theme"] = {"name": theme}
    cv_resume.save()

    response = client.get(reverse("resume:cv", kwargs={"slug": cv_resume.slug}))

    html = response.content.decode()
    assert 'href="https://project.example/"' in html
    assert 'href="https://school.example/"' in html


@pytest.mark.parametrize(
    "form_class, context_key, field_name, item",
    [
        (TimelineItemForm, "entry", "company_url", timeline_item("w1", DANGEROUS)),
        (
            ProjectItemForm,
            "project",
            "url",
            {
                "id": "p1",
                "title": "Project",
                "url": DANGEROUS,
                "description": "Project",
                "badges": [],
            },
        ),
        (
            EducationItemForm,
            "entry",
            "school_url",
            {"id": "e1", "school_name": "School", "school_url": DANGEROUS},
        ),
    ],
)
def test_item_context_drops_dangerous_link_schemes(
    resume, form_class, context_key, field_name, item
):
    form = form_class(data={}, resume=resume, existing_items=[])

    context = form.set_context(item, {"edit_url": "#", "delete_url": "#"})

    assert context[context_key][field_name] == ""
