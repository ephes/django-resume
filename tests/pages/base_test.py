import pytest
from django.test import RequestFactory

from django_resume.pages.base import (
    ResumePage,
    build_base_context,
    build_section_context,
    page_template_path,
)
from django_resume.plugins import plugin_registry


@pytest.mark.django_db
def test_build_section_context_explicit_list(resume):
    resume.owner.save()
    resume.save()
    request = RequestFactory().get("/john-doe/")
    request.user = resume.owner

    context = build_section_context(request, resume, {}, ["identity", "about"])

    assert "identity" in context
    assert "about" in context
    assert "skills" not in context


@pytest.mark.django_db
def test_build_section_context_all(resume):
    resume.owner.save()
    resume.save()
    request = RequestFactory().get("/john-doe/")
    request.user = resume.owner

    context = build_section_context(request, resume, {}, "__all__")

    registered = {p.name for p in plugin_registry.get_all_plugins()}
    assert registered.issubset(set(context))


@pytest.mark.django_db
def test_build_section_context_skips_unknown_section(resume):
    # An unregistered/typo'd section name is silently skipped (no key added).
    resume.owner.save()
    resume.save()
    request = RequestFactory().get("/john-doe/")
    request.user = resume.owner

    context = build_section_context(request, resume, {}, ["does-not-exist"])

    assert context == {}


@pytest.mark.django_db
def test_build_base_context_owner_vs_anonymous(resume, django_user_model):
    from django.contrib.auth.models import AnonymousUser

    resume.owner.save()
    resume.save()

    owner_request = RequestFactory().get("/john-doe/?edit=true")
    owner_request.user = resume.owner
    owner_context = build_base_context(owner_request, resume)
    assert owner_context["is_editable"] is True
    assert owner_context["show_edit_button"] is True

    anon_request = RequestFactory().get("/john-doe/?edit=true")
    anon_request.user = AnonymousUser()
    anon_context = build_base_context(anon_request, resume)
    assert anon_context["is_editable"] is False
    assert anon_context["show_edit_button"] is False


def test_page_template_path_uses_theme(resume):
    assert (
        page_template_path(resume, "resume_cv.html")
        == "django_resume/pages/plain/resume_cv.html"
    )


def test_default_page_hooks():
    page = ResumePage()
    rf = RequestFactory().get("/")
    assert page.check_access(rf, None) is None
    sentinel = object()
    assert page.finalize_response(sentinel, rf, None) is sentinel
