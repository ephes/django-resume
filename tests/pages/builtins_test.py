import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from django_resume.pages.builtins import CvPage, render_cv_403
from django_resume.plugins import plugin_registry, TokenPlugin


@pytest.mark.django_db
def test_cv_check_access_allows_when_token_unregistered(resume):
    resume.owner.save()
    resume.save()
    plugin_registry.unregister(TokenPlugin)

    request = RequestFactory().get("/john-doe/cv/")
    request.user = AnonymousUser()

    assert CvPage().check_access(request, resume) is None


@pytest.mark.django_db
def test_cv_check_access_denies_without_token(resume):
    resume.owner.save()
    resume.save()
    plugin_registry.register(TokenPlugin)

    request = RequestFactory().get("/john-doe/cv/")
    request.user = AnonymousUser()

    response = CvPage().check_access(request, resume)
    assert response is not None
    assert response.status_code == 403


@pytest.mark.django_db
def test_render_cv_403_includes_permission_denied_context(resume):
    resume.owner.save()
    resume.plugin_data["permission_denied"] = {
        "title": "Access Token Needed for CV",
        "email": "tokensupport@example.com",
        "text": "hello",
    }
    resume.save()

    request = RequestFactory().get("/john-doe/cv/")
    request.user = AnonymousUser()

    response = render_cv_403(request, resume, status=403)
    assert response.status_code == 403
    assert b"Access Token Needed for CV" in response.content
