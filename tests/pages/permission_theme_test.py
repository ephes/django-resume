"""Denial pages and inline editing remain available for partial themes."""

from copy import deepcopy

import pytest
from django.urls import reverse


@pytest.fixture
def protected_resume(resume):
    resume.owner.save()
    resume.plugin_data = {
        "theme": {"name": "headwind"},
        "permission_denied": {
            "title": "CV access request",
            "sub_title": "Invitation required",
            "email": "access@example.com",
            "text": "Please request a token.",
        },
    }
    resume.save()
    return resume


@pytest.mark.django_db
def test_headwind_denied_cv_and_owner_editor(client, protected_resume):
    resume = protected_resume
    denied = client.get(reverse("resume:cv", kwargs={"slug": resume.slug}))
    assert denied.status_code == 403
    assert denied["Referrer-Policy"] == "no-referrer"
    assert "django_resume/pages/headwind/cv_403.html" in {
        t.name for t in denied.templates
    }
    assert "Access Denied" in denied.content.decode()

    client.force_login(resume.owner)
    editor = client.get(
        reverse("resume:403", kwargs={"slug": resume.slug}), {"edit": "true"}
    )
    assert editor.status_code == 200
    assert "django_resume/pages/headwind/cv_403.html" in {
        t.name for t in editor.templates
    }
    # Headwind's existing frame is static. Its inline form endpoint must still
    # resolve through the plain fallback when an integration links to it.
    form = client.get(
        reverse("resume:permission_denied-edit", kwargs={"resume_id": resume.pk})
    )
    assert form.status_code == 200
    assert "django_resume/plugins/permission_denied/plain/form.html" in {
        t.name for t in form.templates
    }


@pytest.mark.django_db
def test_partial_third_party_theme_falls_back_for_denial_fragments(
    client, protected_resume, settings
):
    # A real loaded page template with no matching plugin templates exercises
    # the compatibility boundary that page-level fallback alone cannot handle.
    templates = deepcopy(settings.TEMPLATES)
    templates[0]["APP_DIRS"] = False
    templates[0]["OPTIONS"]["loaders"] = [
        (
            "django.template.loaders.locmem.Loader",
            {
                "django_resume/pages/partial/cv_403.html": "Third-party frame: {% include permission_denied.templates.main %}",
            },
        ),
        "django.template.loaders.app_directories.Loader",
    ]
    settings.TEMPLATES = templates
    resume = protected_resume
    resume.plugin_data["theme"]["name"] = "partial"
    resume.save()
    denied = client.get(reverse("resume:cv", kwargs={"slug": resume.slug}))
    assert denied.status_code == 403
    assert denied["Referrer-Policy"] == "no-referrer"
    assert "Third-party frame:" in denied.content.decode()
    assert "CV access request" in denied.content.decode()
    assert "django_resume/plugins/permission_denied/plain/content.html" in {
        t.name for t in denied.templates
    }

    client.force_login(resume.owner)
    editor = client.get(
        reverse("resume:403", kwargs={"slug": resume.slug}), {"edit": "true"}
    )
    assert editor.status_code == 200
    assert "hx-get=" in editor.content.decode()
    form_url = reverse("resume:permission_denied-edit", kwargs={"resume_id": resume.pk})
    form = client.get(form_url)
    assert form.status_code == 200
    assert "django_resume/plugins/permission_denied/plain/form.html" in {
        t.name for t in form.templates
    }
    post_url = reverse("resume:permission_denied-post", kwargs={"resume_id": resume.pk})
    invalid = client.post(post_url, {"title": ""})
    assert invalid.status_code == 200
    assert "django_resume/plugins/permission_denied/plain/form.html" in {
        t.name for t in invalid.templates
    }
    updated = client.post(
        post_url,
        {**resume.plugin_data["permission_denied"], "title": "Updated access request"},
    )
    assert updated.status_code == 200
    assert "Updated access request" in updated.content.decode()
    assert "django_resume/plugins/permission_denied/plain/content.html" in {
        t.name for t in updated.templates
    }


@pytest.mark.django_db
def test_plain_denial_avatar_uses_its_own_dimensions(client, protected_resume):
    resume = protected_resume
    resume.plugin_data["theme"]["name"] = "plain"
    resume.plugin_data["permission_denied"].update(
        {"avatar_img": "denied.png", "avatar_img_width": 120, "avatar_img_height": 80}
    )
    # a cover avatar with other dimensions must not leak into the denial page
    resume.plugin_data["cover"] = {"avatar_img_width": 999, "avatar_img_height": 999}
    resume.save()

    html = client.get(
        reverse("resume:cv", kwargs={"slug": resume.slug})
    ).content.decode()

    assert 'width="120"' in html
    assert 'height="80"' in html
    assert 'width="999"' not in html
