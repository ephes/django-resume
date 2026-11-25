from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse

from django_resume.pages.builtins import CvPage, render_cv_403
from django_resume.plugins import plugin_registry, TokenPlugin
from django_resume.plugins.registry import PluginRegistry


@pytest.mark.django_db
@pytest.mark.parametrize("denial_renderer", [True, False])
@pytest.mark.parametrize(
    "visitor,token,public,status",
    [
        ("anonymous", None, False, 403),
        ("anonymous", "invalid", False, 403),
        ("anonymous", "valid", False, 200),
        ("other", None, False, 403),
        ("owner", None, False, 200),
        ("staff", None, False, 200),
        ("anonymous", None, True, 200),
    ],
)
def test_cv_policy_without_token_renderer(
    client,
    resume,
    django_user_model,
    monkeypatch,
    denial_renderer,
    visitor,
    token,
    public,
    status,
):
    resume.owner.save()
    resume.plugin_data = {
        "token": {
            "flat": {"token_required": not public},
            "items": [{"token": "valid"}],
        },
        "education": {
            "items": [{"id": "school", "school_name": "Private synthetic school"}]
        },
        "permission_denied": {"title": "Synthetic access request"},
    }
    resume.save()
    isolated = PluginRegistry()
    isolated.plugins = {
        name: plugin
        for name, plugin in plugin_registry.plugins.items()
        if name != "token" and (denial_renderer or name != "permission_denied")
    }
    monkeypatch.setattr(plugin_registry, "plugins", isolated.plugins)
    if visitor == "owner":
        client.force_login(resume.owner)
    elif visitor != "anonymous":
        user = django_user_model.objects.create_user(
            username=visitor, is_staff=visitor == "staff"
        )
        client.force_login(user)
    response = client.get(
        reverse("resume:cv", kwargs={"slug": resume.slug}),
        {"token": token} if token else {},
    )
    assert response.status_code == status
    if status == 200:
        assert b"Private synthetic school" in response.content
    else:
        assert b"Private synthetic school" not in response.content
        if denial_renderer:
            assert b"Synthetic access request" in response.content
        else:
            assert b"Access denied" in response.content
            assert b"Synthetic access request" not in response.content
    if not public:
        assert response["Referrer-Policy"] == "no-referrer"
        assert response["Cache-Control"] == "private, no-store"
        assert response["X-Robots-Tag"] == "noindex"


@pytest.mark.django_db
def test_permission_denied_editor_without_renderer_is_missing(
    client, resume, monkeypatch
):
    resume.owner.save()
    resume.save()
    monkeypatch.delitem(plugin_registry.plugins, "permission_denied")
    client.force_login(resume.owner)

    response = client.get(reverse("resume:403", kwargs={"slug": resume.slug}))

    assert response.status_code == 404


@pytest.mark.django_db
def test_cv_check_access_denies_without_token(resume):
    resume.owner.save()
    resume.save()
    token_registered = plugin_registry.get_plugin(TokenPlugin.name) is not None
    if not token_registered:
        plugin_registry.register(TokenPlugin)
    try:
        request = RequestFactory().get("/john-doe/cv/")
        request.user = AnonymousUser()

        response = CvPage().check_access(request, resume)
        assert response is not None
        assert response.status_code == 403
    finally:
        if not token_registered:
            plugin_registry.unregister(TokenPlugin)


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


@pytest.mark.django_db
@pytest.mark.parametrize("edit", [False, True])
def test_denial_editor_login_return_keeps_only_edit_mode(client, resume, edit):
    resume.owner.save()
    resume.save()
    url = reverse("resume:403", kwargs={"slug": resume.slug})
    query = {"token": ["synthetic+&=#", "another-synthetic-token"], "source": "test"}
    if edit:
        query["edit"] = "true"

    response = client.get(url, query)

    assert response.status_code == 302
    next_url = f"{url}?edit=true" if edit else url
    assert parse_qs(urlsplit(response.url).query)["next"] == [next_url]

    client.force_login(resume.owner)
    editor = client.get(next_url)
    assert editor.status_code == 200
    assert editor.context["show_edit_button"] is edit


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
def test_cv_route_is_read_only(client, resume):
    resume.owner.save()
    resume.save()
    url = reverse("resume:cv", kwargs={"slug": resume.slug})

    r = client.post(url)

    assert r.status_code == 405
    assert r["Allow"] == "GET, HEAD"


@pytest.mark.django_db
@pytest.mark.parametrize("page", ["detail", "cv", "403"])
@pytest.mark.parametrize("owner", [False, True])
def test_page_head_matches_get(client, resume, page, owner):
    from django.utils import translation

    resume.owner.save()
    resume.plugin_data["theme"] = {"language": "de"}
    resume.save()
    if owner:
        client.force_login(resume.owner)
    url = reverse(f"resume:{page}", kwargs={"slug": resume.slug})
    with translation.override("en"):
        get = client.get(url)
        head = client.head(url)
        assert translation.get_language() == "en"
    assert head.status_code == get.status_code
    # Session/CSRF cookies and generated signed fields are request specific.
    for header in ("Content-Type", "Cache-Control", "Vary", "Location"):
        assert head.get(header) == get.get(header)
    assert head.content == b""
    assert client.post(url).status_code == 405
