"""Typed execution policy and literal legacy-link query preservation."""

from urllib.parse import urlencode

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

from django_resume import views
from django_resume.formats.json_resume import themes


@pytest.mark.parametrize(
    "name,check",
    [
        (
            "DJANGO_RESUME_JSON_RESUME_ALLOW_DYNAMIC_THEME_INSTALL",
            themes.dynamic_theme_install_allowed,
        ),
        (
            "DJANGO_RESUME_JSON_RESUME_ALLOW_CATALOG_THEME_INSTALL",
            themes.catalog_theme_install_allowed,
        ),
        (
            "DJANGO_RESUME_JSON_RESUME_ALLOW_THEME_SCRIPTS",
            views._theme_content_security_policy,
        ),
    ],
)
@pytest.mark.parametrize("value", ["false", "true", 0, 1, [], {}, None])
def test_execution_flags_reject_untyped_values(settings, name, check, value):
    setattr(settings, name, value)
    with pytest.raises(ImproperlyConfigured, match=name):
        check()


@pytest.mark.parametrize("enabled", [False, True])
def test_execution_flags_accept_booleans(settings, enabled):
    settings.DJANGO_RESUME_JSON_RESUME_ALLOW_DYNAMIC_THEME_INSTALL = enabled
    settings.DJANGO_RESUME_JSON_RESUME_ALLOW_CATALOG_THEME_INSTALL = enabled
    settings.DJANGO_RESUME_JSON_RESUME_ALLOW_THEME_SCRIPTS = enabled
    assert themes.dynamic_theme_install_allowed() is enabled
    assert themes.catalog_theme_install_allowed() is enabled
    assert (
        "script-src 'unsafe-inline'" in views._theme_content_security_policy()
    ) is enabled


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query",
    ["", urlencode([("token", "invented &+/?=%"), ("label", "one"), ("label", "two")])],
)
def test_legacy_cv_redirect_preserves_literal_query(client, query):
    url = reverse("django_resume:cv-redirect", kwargs={"slug": "invented"})
    response = client.get(url + ("?" + query if query else ""))
    target = reverse("django_resume:cv", kwargs={"slug": "invented"})
    assert response["Location"] == target + ("?" + query if query else "")
    assert "no-store" in response["Cache-Control"]
    assert "private" in response["Cache-Control"]
    assert response["Referrer-Policy"] == "no-referrer"


@pytest.mark.django_db
def test_legacy_token_link_still_opens_private_cv(client, django_user_model):
    from django_resume.models import Resume

    owner = django_user_model.objects.create_user(username="invented-cv-owner")
    credential = "invented+&/=?%"
    resume = Resume.objects.create(
        name="Invented CV",
        slug="invented-private",
        owner=owner,
        plugin_data={
            "identity": {"name": "Invented CV"},
            "token": {
                "flat": {"token_required": True},
                "items": [{"id": "invented", "token": credential}],
            },
        },
    )
    url = reverse("django_resume:cv-redirect", kwargs={"slug": resume.slug})
    response = client.get(
        url
        + "?"
        + urlencode([("token", credential), ("label", "one"), ("label", "two")]),
        follow=True,
    )
    assert response.status_code == 200
    assert b"Invented CV" in response.content
    assert response.wsgi_request.GET["token"] == credential
    assert response.wsgi_request.GET.getlist("label") == ["one", "two"]


@pytest.mark.django_db
@pytest.mark.parametrize("catalog", [False, True])
def test_invalid_install_flag_cannot_invoke_install(
    client, django_user_model, settings, mocker, catalog, tmp_path
):
    from django_resume.models import Resume

    settings.DJANGO_RESUME_JSON_RESUME_THEME_DIR = tmp_path / "themes"
    owner = django_user_model.objects.create_user(username="invented-theme-owner")
    resume = Resume.objects.create(name="Invented", slug="invented-theme", owner=owner)
    client.force_login(owner)
    flag = (
        "DJANGO_RESUME_JSON_RESUME_ALLOW_"
        + ("CATALOG" if catalog else "DYNAMIC")
        + "_THEME_INSTALL"
    )
    setattr(settings, flag, "false")
    install = mocker.patch.object(
        views, "install_catalog_theme" if catalog else "install_theme"
    )
    kwargs = {"slug": resume.slug}
    if catalog:
        kwargs["key"] = "even"
    url = reverse(
        "django_resume:json-resume-theme-preview"
        if catalog
        else "django_resume:json-resume-theme-install",
        kwargs=kwargs,
    )
    with pytest.raises(ImproperlyConfigured, match=flag):
        client.post(url, {"package": "jsonresume-theme-even"})
    install.assert_not_called()
