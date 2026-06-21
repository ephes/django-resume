"""Theme template fallback.

When a resume's active theme does not ship a page template, page rendering
falls back predictably to the ``plain`` theme -- for the page frame *and* the
section plugins it renders -- so a missing theme template never crashes a page
that has a valid ``plain`` fallback.
"""

import pytest
from django.test import RequestFactory
from django.urls import reverse

from django_resume.pages.base import (
    page_template_name,
    page_template_path,
    resolve_page_theme,
)


def _set_theme(resume, name):
    resume.plugin_data["theme"] = {"name": name}


def test_page_template_name_is_pure():
    assert (
        page_template_name("headwind", "resume_cv.html")
        == "django_resume/pages/headwind/resume_cv.html"
    )


@pytest.mark.django_db
def test_resolve_keeps_theme_that_has_the_template(resume):
    resume.owner.save()
    _set_theme(resume, "headwind")
    resume.save()
    # headwind ships resume_detail.html, so no fallback.
    assert resolve_page_theme(resume, "resume_detail.html") == "headwind"
    assert (
        page_template_path(resume, "resume_detail.html")
        == "django_resume/pages/headwind/resume_detail.html"
    )


@pytest.mark.django_db
def test_resolve_falls_back_to_plain_for_unknown_theme(resume):
    resume.owner.save()
    _set_theme(resume, "ghost")  # a theme that ships no page templates
    resume.save()

    assert resolve_page_theme(resume, "resume_detail.html") == "plain"
    assert (
        page_template_path(resume, "resume_detail.html")
        == "django_resume/pages/plain/resume_detail.html"
    )


@pytest.mark.django_db
def test_resolve_falls_back_when_theme_lacks_only_one_template(resume):
    # headwind has cv_403.html, but a theme missing a specific template still
    # falls back per-template rather than wholesale.
    resume.owner.save()
    _set_theme(resume, "ghost")
    resume.save()
    assert resolve_page_theme(resume, "cv_403.html") == "plain"


def test_plain_theme_resolves_without_a_loader_lookup(resume):
    # The default plain theme short-circuits (its templates are the fallback).
    assert resolve_page_theme(resume, "resume_detail.html") == "plain"


@pytest.mark.django_db
def test_detail_page_renders_via_plain_fallback_for_unknown_theme(client, resume):
    # The product path: a resume whose theme ships no templates still renders
    # (HTTP 200) through the plain fallback -- frame and section plugins -- with
    # no TemplateDoesNotExist.
    resume.owner.save()
    _set_theme(resume, "ghost")
    resume.save()

    response = client.get(reverse("resume:detail", kwargs={"slug": resume.slug}))

    assert response.status_code == 200
    used = {t.name for t in response.templates if t.name}
    assert "django_resume/pages/plain/resume_detail.html" in used
    # A section fragment also resolved via plain (proves coherent fallback).
    assert any(
        name.startswith("django_resume/plugins/") and "/plain/" in name for name in used
    )


@pytest.mark.django_db
def test_detail_page_uses_theme_template_when_present(client, resume):
    resume.owner.save()
    _set_theme(resume, "headwind")
    resume.save()

    response = client.get(reverse("resume:detail", kwargs={"slug": resume.slug}))

    assert response.status_code == 200
    used = {t.name for t in response.templates if t.name}
    assert "django_resume/pages/headwind/resume_detail.html" in used
    assert "django_resume/pages/plain/resume_detail.html" not in used


@pytest.mark.django_db
def test_build_section_context_accepts_explicit_theme(resume):
    from django_resume.pages.base import build_section_context

    resume.owner.save()
    resume.save()
    request = RequestFactory().get("/john-doe/")
    request.user = resume.owner

    # Passing an explicit theme is honored over resume.current_theme.
    context = build_section_context(request, resume, {}, ["identity"], theme="headwind")
    assert (
        "django_resume/plugins/identity/headwind/"
        in context["identity"]["templates"].main
    )
