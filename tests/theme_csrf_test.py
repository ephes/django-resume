"""Browser CSRF checks run before npm, rendering and selection writes."""

from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse

from django_resume import views
from django_resume.formats.json_resume.themes import (
    RenderedTheme,
    catalog_theme,
    selected_catalog_theme_key,
    selected_theme_name,
)
from django_resume.models import Resume


@pytest.fixture(params=["install", "preview", "use"])
def theme_action(request, user, settings, mocker):
    settings.DJANGO_RESUME_JSON_RESUME_ALLOW_DYNAMIC_THEME_INSTALL = True
    settings.DJANGO_RESUME_JSON_RESUME_ALLOW_CATALOG_THEME_INSTALL = True
    user.save()
    resume = Resume.objects.create(name="Synthetic", slug="csrf-theme", owner=user)
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    mocker.patch.object(views, "search_themes", return_value=[])
    selector = reverse("django_resume:json-resume-themes", kwargs={"slug": resume.slug})
    response = client.get(selector, secure=True)
    assert response.status_code == 200
    csrf = client.cookies[settings.CSRF_COOKIE_NAME].value
    action = request.param
    kwargs = {"slug": resume.slug}
    if action != "install":
        kwargs["key"] = "even"
    collaborators = [
        mocker.patch.object(views, "install_theme"),
        mocker.patch.object(
            views, "install_catalog_theme", return_value=catalog_theme("even")
        ),
        mocker.patch.object(
            views,
            "render_catalog_theme",
            return_value=RenderedTheme(
                html="<p>Synthetic preview</p>",
                theme_name="jsonresume-theme-even",
                notes=(),
            ),
        ),
        mocker.patch.object(
            views, "set_selected_theme", wraps=views.set_selected_theme
        ),
        mocker.patch.object(
            views, "set_selected_catalog_theme", wraps=views.set_selected_catalog_theme
        ),
    ]
    return SimpleNamespace(
        client=client,
        resume=resume,
        csrf=csrf,
        action=action,
        url=reverse(f"django_resume:json-resume-theme-{action}", kwargs=kwargs),
        collaborators=collaborators,
    )


def assert_untouched(action):
    for collaborator in action.collaborators:
        collaborator.assert_not_called()
    action.resume.refresh_from_db()
    assert action.resume.integration_data == {}
    assert action.resume.plugin_data == {}


@pytest.mark.django_db
@pytest.mark.parametrize("proof", ["missing", "mismatched", "foreign-origin"])
def test_theme_actions_reject_invalid_csrf_before_side_effects(theme_action, proof):
    headers = {"Origin": "https://testserver"}
    if proof != "missing":
        headers["X-CSRFToken"] = (
            ("a" * 32 if theme_action.csrf != "a" * 32 else "b" * 32)
            if proof == "mismatched"
            else theme_action.csrf
        )
    if proof == "foreign-origin":
        headers["Origin"] = "https://foreign.example"
    response = theme_action.client.post(
        theme_action.url,
        {"package": "jsonresume-theme-even"},
        secure=True,
        headers=headers,
    )
    assert response.status_code == 403
    assert_untouched(theme_action)


@pytest.mark.django_db
def test_theme_actions_accept_owner_with_same_origin_csrf(theme_action):
    response = theme_action.client.post(
        theme_action.url,
        {"package": "jsonresume-theme-even"},
        secure=True,
        headers={"Origin": "https://testserver", "X-CSRFToken": theme_action.csrf},
    )
    dynamic, catalog, render, select_dynamic, select_catalog = (
        theme_action.collaborators
    )
    theme_action.resume.refresh_from_db()
    if theme_action.action == "preview":
        assert response.status_code == 200
        assert response.content == b"<p>Synthetic preview</p>"
        catalog.assert_called_once_with("even")
        render.assert_called_once()
        assert theme_action.resume.integration_data == {}
    else:
        assert response.status_code == 302
        assert selected_theme_name(theme_action.resume) == "jsonresume-theme-even"
        render.assert_not_called()
    if theme_action.action == "install":
        dynamic.assert_called_once_with("jsonresume-theme-even")
        select_dynamic.assert_called_once()
        catalog.assert_not_called()
        select_catalog.assert_not_called()
    else:
        dynamic.assert_not_called()
        select_dynamic.assert_not_called()
        if theme_action.action == "use":
            catalog.assert_called_once_with("even")
            select_catalog.assert_called_once()
            assert selected_catalog_theme_key(theme_action.resume) == "even"
        else:
            select_catalog.assert_not_called()


@pytest.mark.django_db
def test_valid_csrf_does_not_grant_theme_ownership(theme_action, django_user_model):
    other = django_user_model.objects.create_user(username="synthetic-other")
    theme_action.client.force_login(other)
    response = theme_action.client.post(
        theme_action.url,
        {"package": "jsonresume-theme-even"},
        secure=True,
        headers={"Origin": "https://testserver", "X-CSRFToken": theme_action.csrf},
    )
    assert response.status_code == 404
    assert_untouched(theme_action)
