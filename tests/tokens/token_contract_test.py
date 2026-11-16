from datetime import datetime, timedelta, timezone as datetime_timezone
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db import connection

from django_resume.plugins.tokens import TokenItemForm, TokenPlugin, is_token_expired
from django_resume.formats.json_resume.importer import (
    import_resume_document,
    load_document_bytes,
)


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


@pytest.mark.django_db
@pytest.mark.skipif(
    connection.vendor != "sqlite",
    reason="PostgreSQL jsonb refuses lone surrogates, so this stored state is SQLite-only",
)
@pytest.mark.parametrize("surrogate", ["\ud800", "\udfff"])
@pytest.mark.parametrize("valid_sibling", [False, True])
@pytest.mark.parametrize("reverse_items", [False, True])
def test_imported_unencodable_secret_does_not_break_protected_requests(
    user, client, caplog, surrogate, valid_sibling, reverse_items
):
    from django.urls import reverse

    malformed = "synthetic-secret-" + surrogate
    valid = "synthetic-valid-ünicode"
    items = [{"id": "malformed", "token": malformed}]
    if valid_sibling:
        items.append({"id": "valid", "token": valid})
    if reverse_items:
        items.reverse()
    document = {
        "basics": {"name": "Synthetic"},
        "meta": {"django_resume": {"plugin_data": {"token": {"items": items}}}},
    }
    # Take the raw escaped-JSON import path, then reload the persisted document.
    wire = json.dumps(document, ensure_ascii=True).encode("ascii")
    user.save()
    imported = import_resume_document(
        load_document_bytes(wire), owner=user, slug="synthetic-surrogate"
    )
    assert imported.report.valid
    row = imported.resume
    row.refresh_from_db()
    assert any(item["token"] == malformed for item in row.plugin_data["token"]["items"])
    url = reverse("resume:cv", kwargs={"slug": row.slug})
    for query, status in [
        ({}, 403),
        ({"token": "synthetic-wrong"}, 403),
        ({"token": valid}, 200 if valid_sibling else 403),
    ]:
        response = client.get(url, query)
        assert response.status_code == status
        assert "private" in response["Cache-Control"]
        assert "no-store" in response["Cache-Control"]
        assert response["Referrer-Policy"] == "no-referrer"
        assert b"synthetic-secret-" not in response.content
        assert valid.encode("utf-8") not in response.content
        assert b"Traceback" not in response.content
    assert "synthetic-secret-" not in caplog.text
    assert valid not in caplog.text
    assert "Traceback" not in caplog.text


@pytest.mark.parametrize("oversized", ["count", "secret", "aggregate", "created"])
@pytest.mark.parametrize("valid_first", [True, False])
def test_oversized_policy_refused_before_comparison_or_date_parsing(
    rf, monkeypatch, oversized, valid_first
):
    from unittest.mock import Mock
    from django_resume.plugins import tokens

    good = {"token": "synthetic-valid"}
    bad = {
        "count": [{"token": "x"}] * 257,
        "secret": [{"token": "x" * 65537}],
        "aggregate": [{"token": "é" * 256}] * 128,
        "created": [{"token": "bad", "created": "2" * 129}],
    }[oversized]
    items = [good, *bad] if valid_first else [*bad, good]
    compare, parse = Mock(return_value=False), Mock(return_value=None)
    monkeypatch.setattr(tokens.hmac, "compare_digest", compare)
    monkeypatch.setattr(tokens, "parse_datetime", parse)
    request = rf.get("/", {"token": good["token"]})
    request.user = AnonymousUser()
    with pytest.raises(PermissionDenied, match="Invalid token policy") as error:
        tokens.TokenPlugin.check_permissions(request, {"items": items})
    assert str(error.value) == "Invalid token policy."
    compare.assert_not_called()
    parse.assert_not_called()


def test_oversized_count_admission_never_iterates_restored_list(rf):
    class NoIteration(list):
        def __iter__(self):
            raise AssertionError("must admit count before traversal")

    request = rf.get("/", {"token": "synthetic"})
    request.user = AnonymousUser()
    with pytest.raises(PermissionDenied, match="Invalid token policy"):
        TokenPlugin.check_permissions(request, {"items": NoIteration([{}] * 257)})


def test_oversized_secret_is_not_encoded(rf):
    class NoEncoding(str):
        def encode(self, *args, **kwargs):
            raise AssertionError("must admit length before encoding")

    request = rf.get("/", {"token": "synthetic"})
    request.user = AnonymousUser()
    with pytest.raises(PermissionDenied, match="Invalid token policy"):
        TokenPlugin.check_permissions(
            request, {"items": [{"token": NoEncoding("x" * 65537)}]}
        )


def test_exact_policy_budget_keeps_unicode_tokens_and_all_comparisons(rf, monkeypatch):
    from django_resume.plugins import tokens

    credential = "é" * 128
    request = rf.get("/", {"token": credential})
    request.user = AnonymousUser()
    compared = []
    original = tokens.hmac.compare_digest

    def compare(left, right):
        compared.append(len(right))
        return original(left, right)

    monkeypatch.setattr(tokens.hmac, "compare_digest", compare)
    assert (
        TokenPlugin.check_permissions(request, {"items": [{"token": credential}] * 256})
        is None
    )
    assert compared == [256] * 256


@pytest.mark.django_db
def test_oversized_restored_policy_never_returns_cv(resume, client, caplog):
    from django.urls import reverse
    from django_resume.plugins import plugin_registry

    resume.owner.save()
    resume.plugin_data = {
        "token": {
            "items": [
                {"token": "synthetic-valid"},
                {"token": "synthetic-secret-" * 6000},
            ]
        },
        "identity": {"name": "Synthetic private CV content"},
    }
    resume.save()
    plugin_registry.register(TokenPlugin)
    response = client.get(
        reverse("resume:cv", kwargs={"slug": resume.slug}), {"token": "synthetic-valid"}
    )
    assert response.status_code == 403
    assert b"Synthetic private CV content" not in response.content
    assert b"synthetic-secret-" not in response.content
    assert "synthetic-secret-" not in caplog.text
    assert "no-store" in response["Cache-Control"]
