from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.test import override_settings
from django.utils import timezone

from django_resume.plugins.tokens import (
    TOKEN_ALPHABET,
    TokenPlugin,
    generate_random_string,
    get_token_ttl,
)


def test_generate_random_string_has_requested_length_and_uses_expected_charset():
    generated = generate_random_string(10)

    assert len(generated) == 10
    assert all(character in TOKEN_ALPHABET for character in generated)


@pytest.mark.django_db
def test_tokens_check_permissions_request_authenticated(resume, rf):
    # Given a request by the resume owner
    resume.owner.save()
    resume.save()
    request = rf.get("/")
    request.user = resume.owner

    # When we call the check_permissions method
    permitted_if_none = TokenPlugin.check_permissions(
        request, {"flat": {"token_required": True}}, resume
    )

    # Then the method should return None
    assert permitted_if_none is None


def test_tokens_check_permissions_rejects_missing_token(rf):
    request = rf.get("/")
    request.user = AnonymousUser()

    with pytest.raises(PermissionDenied, match="Token required to access this page."):
        TokenPlugin.check_permissions(request, {"flat": {"token_required": True}})


def test_tokens_check_permissions_rejects_invalid_token(rf):
    request = rf.get("/", {"token": "wrong-token"})
    request.user = AnonymousUser()

    with pytest.raises(PermissionDenied, match="Invalid token."):
        TokenPlugin.check_permissions(
            request,
            {
                "flat": {"token_required": True},
                "items": [{"token": "expected-token"}],
            },
        )


def test_tokens_check_permissions_accepts_valid_token_for_anonymous_user(rf):
    request = rf.get("/", {"token": "expected-token"})
    request.user = AnonymousUser()

    permitted_if_none = TokenPlugin.check_permissions(
        request,
        {
            "flat": {"token_required": True},
            "items": [{"token": "expected-token"}],
        },
    )

    assert permitted_if_none is None


@override_settings(DJANGO_RESUME_TOKEN_TTL=timedelta(seconds=1))
def test_tokens_check_permissions_accepts_legacy_token_without_created(rf):
    request = rf.get("/", {"token": "legacy-token"})
    request.user = AnonymousUser()

    permitted_if_none = TokenPlugin.check_permissions(
        request,
        {
            "flat": {"token_required": True},
            "items": [{"token": "legacy-token"}],
        },
    )

    assert permitted_if_none is None


def test_tokens_check_permissions_skips_token_when_not_required(rf):
    request = rf.get("/")
    request.user = AnonymousUser()

    permitted_if_none = TokenPlugin.check_permissions(
        request, {"flat": {"token_required": False}}
    )

    assert permitted_if_none is None


@override_settings(DJANGO_RESUME_TOKEN_TTL=timedelta(minutes=5))
def test_tokens_check_permissions_rejects_expired_token(rf):
    request = rf.get("/", {"token": "expired-token"})
    request.user = AnonymousUser()
    expired_created = (timezone.now() - timedelta(minutes=6)).isoformat()

    with pytest.raises(PermissionDenied, match="Token expired."):
        TokenPlugin.check_permissions(
            request,
            {
                "flat": {"token_required": True},
                "items": [{"token": "expired-token", "created": expired_created}],
            },
        )


@override_settings(DJANGO_RESUME_TOKEN_TTL=timedelta(minutes=5))
def test_tokens_check_permissions_accepts_unexpired_token(rf):
    request = rf.get("/", {"token": "fresh-token"})
    request.user = AnonymousUser()
    fresh_created = (timezone.now() - timedelta(minutes=4)).isoformat()

    permitted_if_none = TokenPlugin.check_permissions(
        request,
        {
            "flat": {"token_required": True},
            "items": [{"token": "fresh-token", "created": fresh_created}],
        },
    )

    assert permitted_if_none is None


@override_settings(DJANGO_RESUME_TOKEN_TTL=None)
def test_tokens_check_permissions_accepts_expired_token_when_ttl_disabled(rf):
    request = rf.get("/", {"token": "non-expiring-token"})
    request.user = AnonymousUser()
    expired_created = (timezone.now() - timedelta(days=365)).isoformat()

    permitted_if_none = TokenPlugin.check_permissions(
        request,
        {
            "flat": {"token_required": True},
            "items": [{"token": "non-expiring-token", "created": expired_created}],
        },
    )

    assert permitted_if_none is None


@override_settings(DJANGO_RESUME_TOKEN_TTL="30d")
def test_get_token_ttl_rejects_invalid_setting_type():
    with pytest.raises(ImproperlyConfigured, match="DJANGO_RESUME_TOKEN_TTL"):
        get_token_ttl()


def test_tokens_check_permissions_ignores_malformed_items(rf):
    request = rf.get("/", {"token": "expected-token"})
    request.user = AnonymousUser()

    permitted_if_none = TokenPlugin.check_permissions(
        request,
        {
            "flat": {"token_required": True},
            "items": [42, None, {"receiver": "test"}, {"token": "expected-token"}],
        },
    )

    assert permitted_if_none is None


def test_tokens_check_permissions_rejects_non_ascii_token(rf):
    request = rf.get("/", {"token": "\u00e4"})
    request.user = AnonymousUser()

    with pytest.raises(PermissionDenied, match="Invalid token."):
        TokenPlugin.check_permissions(
            request,
            {
                "flat": {"token_required": True},
                "items": [{"token": "expected-token"}, {"token": "\u00f6"}],
            },
        )


def test_tokens_check_permissions_accepts_matching_non_ascii_stored_token(rf):
    request = rf.get("/", {"token": "t\u00f6ken"})
    request.user = AnonymousUser()

    permitted_if_none = TokenPlugin.check_permissions(
        request,
        {"flat": {"token_required": True}, "items": [{"token": "t\u00f6ken"}]},
    )

    assert permitted_if_none is None


@pytest.mark.django_db
def test_tokens_check_permissions_rejects_other_logged_in_user(
    resume, rf, django_user_model
):
    resume.owner.save()
    resume.save()
    other = django_user_model.objects.create_user(username="other", password="x")
    request = rf.get("/")
    request.user = other

    with pytest.raises(PermissionDenied, match="Token required to access this page."):
        TokenPlugin.check_permissions(
            request, {"flat": {"token_required": True}}, resume
        )


@pytest.mark.django_db
def test_tokens_check_permissions_without_resume_does_not_bypass_for_owner(resume, rf):
    # Legacy two-argument callers cannot identify the owner, so only staff
    # users skip the token check.
    resume.owner.save()
    resume.save()
    request = rf.get("/")
    request.user = resume.owner

    with pytest.raises(PermissionDenied):
        TokenPlugin.check_permissions(request, {"flat": {"token_required": True}})


@pytest.mark.django_db
@pytest.mark.parametrize("pass_resume", [True, False])
def test_tokens_check_permissions_staff_user_bypasses_token(
    resume, rf, django_user_model, pass_resume
):
    resume.owner.save()
    resume.save()
    staff = django_user_model.objects.create_user(
        username="staff", password="x", is_staff=True
    )
    request = rf.get("/")
    request.user = staff

    args = (resume,) if pass_resume else ()
    assert (
        TokenPlugin.check_permissions(
            request, {"flat": {"token_required": True}}, *args
        )
        is None
    )
