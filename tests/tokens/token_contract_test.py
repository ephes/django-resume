from datetime import datetime, timedelta, timezone as datetime_timezone
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied

from django_resume.plugins.tokens import TokenItemForm, TokenPlugin, is_token_expired


@pytest.mark.parametrize(
    "credential",
    ["abc+def&tail=1", "plus+", "amp&", "equal=", "hash#", "ünicode", "percent%20"],
)
def test_generated_link_round_trips_and_redeems(credential, resume, rf):
    form = TokenItemForm(resume=resume, initial={"token": credential})
    link = form.fields["cv_link"].initial
    assert parse_qs(urlsplit(link).query) == {"token": [credential]}
    request = rf.get(link)
    request.user = AnonymousUser()
    assert request.GET["token"] == credential
    assert (
        TokenPlugin.check_permissions(request, {"items": [{"token": credential}]})
        is None
    )
    rendered = str(form["cv_link"])
    assert 'rel="noreferrer noopener"' in rendered


@pytest.mark.parametrize(
    "created",
    [
        "9999-12-31T23:59:59+00:00",
        "0001-01-01T00:00:00+00:00",
        "9999-12-31T23:59:59-23:59",
        "0001-01-01T00:00:00+23:59",
        "9999-13-31T00:00:00+00:00",
        "0000-01-01T00:00:00+00:00",
        "not-a-date",
        "2026-01-01T00:00:00+99:00",
    ],
)
@pytest.mark.parametrize("ttl", [timedelta(days=30), timedelta.max, timedelta.min])
def test_bad_or_extreme_sibling_never_breaks_valid_credential(
    created, ttl, settings, rf
):
    settings.DJANGO_RESUME_TOKEN_TTL = ttl
    request = rf.get("/", {"token": "synthetic-valid"})
    request.user = AnonymousUser()
    assert (
        TokenPlugin.check_permissions(
            request,
            {
                "items": [
                    {"token": "synthetic-extreme", "created": created},
                    {"token": "synthetic-valid"},
                ]
            },
        )
        is None
    )


@pytest.mark.parametrize(
    "created",
    [
        "9999-13-31T00:00:00+00:00",
        "not-a-date",
        "0000-01-01",
        "2026-01-01T00:00:00+99:00",
        42,
        "",
    ],
)
def test_malformed_timestamp_fails_closed(created, rf):
    request = rf.get("/", {"token": "synthetic-malformed"})
    request.user = AnonymousUser()
    with pytest.raises(PermissionDenied, match="expired"):
        TokenPlugin.check_permissions(
            request, {"items": [{"token": "synthetic-malformed", "created": created}]}
        )


@pytest.mark.parametrize("created", [None, "missing"])
def test_missing_timestamp_retains_legacy_policy(created):
    item = {} if created == "missing" else {"created": created}
    assert is_token_expired(item, ttl=timedelta.min) is False


def test_expiry_boundary_and_extremes_do_not_extend_expired_credentials():
    now = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
    assert is_token_expired(
        {"created": (now - timedelta(days=30)).isoformat()}, now=now
    )
    assert not is_token_expired(
        {"created": (now - timedelta(days=30) + timedelta(microseconds=1)).isoformat()},
        now=now,
    )
    assert is_token_expired({"created": "0001-01-01T00:00:00+00:00"}, now=now)
    assert not is_token_expired({"created": "9999-12-31T23:59:59+00:00"}, now=now)


@pytest.mark.parametrize("token_data", [None, [], 1, {"items": None}, {"items": 1}])
@pytest.mark.parametrize("bypass", ["owner", "staff"])
@pytest.mark.django_db
def test_malformed_containers_retain_owner_staff_bypass(
    resume, client, django_user_model, token_data, bypass
):
    from django.urls import reverse
    from django_resume.models import Resume
    from django_resume.plugins import plugin_registry

    resume.owner.save()
    resume.save()
    Resume.objects.filter(pk=resume.pk).update(plugin_data={"token": token_data})
    plugin_registry.register(TokenPlugin)
    user = (
        resume.owner
        if bypass == "owner"
        else django_user_model.objects.create(username="synthetic-staff", is_staff=True)
    )
    client.force_login(user)
    response = client.get(reverse("resume:cv", kwargs={"slug": resume.slug}))
    assert response.status_code == 200
    assert "private" in response["Cache-Control"]
    assert "no-store" in response["Cache-Control"]
    assert response["Referrer-Policy"] == "no-referrer"
