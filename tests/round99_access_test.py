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
