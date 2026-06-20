import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse

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


# Order-independence of the 403 context is structural: render_cv_403 fetches the
# permission_denied plugin BY NAME (build_section_context(["permission_denied"]))
# rather than relying on iteration stopping at the token plugin. That by-name
# fetch is covered by test_render_cv_403_includes_permission_denied_context
# (Task 4) and the existing
# test_cv_permission_denied_message_renders_sanitized_markdown, so no fragile
# global-registry-reordering test is needed here.


@pytest.mark.django_db
def test_permission_denied_editor_route_is_owner_only(
    client, resume, django_user_model
):
    resume.owner.save()
    resume.plugin_data["permission_denied"] = {
        "title": "Access Token Needed for CV",
        "email": "tokensupport@example.com",
        "text": "hello",
    }
    resume.save()
    url = reverse("resume:403", kwargs={"slug": resume.slug})

    # Anonymous -> redirected to login
    r = client.get(url)
    assert r.status_code == 302
    assert "login" in r.url

    # Authenticated non-owner -> 403
    other = django_user_model.objects.create_user(username="other", password="pw")
    client.force_login(other)
    assert client.get(url).status_code == 403

    # Owner -> 200 with the permission_denied editor content (via render_cv_403)
    client.force_login(resume.owner)
    r = client.get(url)
    assert r.status_code == 200
    assert "Access Token Needed for CV" in r.content.decode("utf-8")


def test_builtin_pages_registered():
    from django_resume.pages import page_registry

    assert {p.url_name for p in page_registry.get_all_pages()} >= {
        "detail",
        "cv",
        "403",
    }


def test_detail_route_is_the_bare_catch_all():
    from django_resume.pages import page_registry

    patterns = page_registry.get_urls()
    assert str(patterns[-1].pattern) == "<slug:slug>/"
    assert patterns[-1].name == "detail"


@pytest.mark.django_db
def test_cv_route_is_get_only(client, resume):
    # Intentional behavior change: page routes are GET-only (see changelog).
    resume.owner.save()
    resume.save()
    url = reverse("resume:cv", kwargs={"slug": resume.slug})

    r = client.post(url)

    assert r.status_code == 405
    assert r["Allow"] == "GET"
