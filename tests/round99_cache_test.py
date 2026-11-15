"""Owner-only response policy through real Django cache middleware."""

import pytest
from django.core.cache import cache
from django.test import Client
from django.urls import reverse

from django_resume import views
from django_resume.formats.json_resume.themes import JsonResumeThemeError
from django_resume.plugins import plugin_registry
from tests.plugin_stale_edit_test import editor_resume as _editor_resume, loaded_data

editor_resume = _editor_resume


@pytest.fixture
def cached_site(settings, tmp_path):
    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = tmp_path / "themes"
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "synthetic-round99",
        }
    }
    settings.MIDDLEWARE = [
        "django.middleware.cache.UpdateCacheMiddleware",
        *settings.MIDDLEWARE,
        "django.middleware.cache.FetchFromCacheMiddleware",
    ]
    settings.CACHE_MIDDLEWARE_SECONDS = 600
    cache.clear()
    yield
    cache.clear()


def assert_private(response):
    directives = response["Cache-Control"].split(", ")
    assert "private" in directives
    assert "no-store" in directives


@pytest.mark.django_db
@pytest.mark.parametrize(
    "route", ["json-resume", "json-resume-themes", "json-resume-rendered"]
)
@pytest.mark.parametrize("error", [False, True])
def test_owner_artifact_cache_policy(
    client,
    editor_resume,
    cached_site,
    mocker,
    route,
    error,
    django_user_model,
    settings,
):
    if error:
        if route == "json-resume":
            from django_resume.interchange.coordinator import PathConflictError

            mocker.patch.object(
                views, "export_resume", side_effect=PathConflictError("synthetic")
            )
        elif route == "json-resume-rendered":
            mocker.patch.object(
                views,
                "render_selected_theme",
                side_effect=JsonResumeThemeError("synthetic render error"),
            )
        else:
            # Selector diagnostics carry owner-specific query text.
            settings.DJANGO_RESUME_JSON_RESUME_ALLOW_DYNAMIC_THEME_INSTALL = True
            mocker.patch.object(
                views,
                "search_themes",
                side_effect=JsonResumeThemeError("synthetic search error"),
            )
    elif route == "json-resume-rendered":
        from types import SimpleNamespace

        mocker.patch.object(
            views,
            "render_selected_theme",
            return_value=SimpleNamespace(html="<p>Invented private artifact</p>"),
        )
    url = reverse("django_resume:" + route, kwargs={"slug": editor_resume.slug})
    response = client.get(url)
    assert_private(response)
    # A different session cannot receive the successful owner response from cache.
    outsider = Client()
    assert outsider.get(url).status_code == 302
    other = django_user_model.objects.create_user(username="invented-other-owner")
    outsider.force_login(other)
    assert outsider.get(url).status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize("plugin_name", ["identity", "token"])
def test_inline_get_post_are_never_replayed(
    client, editor_resume, cached_site, plugin_name, django_user_model
):
    plugin = plugin_registry.get_plugin(plugin_name)
    if plugin_name == "identity":
        get_url = plugin.inline.get_edit_url(editor_resume.pk)
        post_url = plugin.inline.get_post_url(editor_resume.pk)
    else:
        editor_resume.plugin_data["token"] = {
            "items": [
                {
                    "id": "invented-token",
                    "token": "invented-secret",
                    "receiver": "Invented receiver",
                }
            ]
        }
        editor_resume.save(update_fields=["plugin_data"])
        get_url = plugin.inline.get_edit_flat_url(editor_resume.pk)
        post_url = plugin.inline.get_edit_flat_post_url(editor_resume.pk)
    response = client.get(get_url)
    assert_private(response)
    data = loaded_data(client, get_url, post_url)
    if plugin_name == "identity":
        data["name"] = "New invented name"
        data["email"] = "invalid"
    else:
        data["edit_revision"] = "tampered"
    invalid = client.post(post_url, data)
    assert invalid.context["form"].errors
    assert_private(invalid)
    if plugin_name == "identity":
        data["email"] = "invented@example.invalid"
    else:
        data = loaded_data(client, get_url, post_url)
        data["token_required"] = "on"
    assert_private(client.post(post_url, data))
    fresh = client.get(get_url)
    assert_private(fresh)
    if plugin_name == "identity":
        assert "New invented" in fresh.content.decode()
    else:
        assert fresh.context["form"]["token_required"].value() is True
    outsider = Client()
    assert outsider.get(get_url).status_code == (
        302 if plugin_name == "identity" else 403
    )

    other = django_user_model.objects.create_user(username="invented-other-editor")
    outsider.force_login(other)
    assert outsider.get(get_url).status_code == 403
