"""Exact ORM budgets around the real built-in CV renderer and token fallback."""

from datetime import timedelta

import pytest
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.utils import timezone

from django_resume.models import Resume
from django_resume.pages.base import build_section_context, dispatch_page
from django_resume.pages.builtins import CvPage
from django_resume.plugins import TokenPlugin, plugin_registry


@pytest.mark.django_db
@pytest.mark.parametrize("size", [1, 100])
@pytest.mark.parametrize(
    "visitor,token,status",
    [
        ("owner", None, 200),
        ("anonymous", None, 403),
        ("other", None, 403),
        ("anonymous", "invalid", 403),
        ("other", "invalid", 403),
        ("anonymous", "expired", 403),
        ("other", "expired", 403),
        ("anonymous", "valid", 200),
        ("other", "valid", 200),
    ],
)
def test_cv_uses_one_loaded_resume(
    django_user_model, django_assert_num_queries, settings, size, visitor, token, status
):
    settings.DJANGO_RESUME_TOKEN_TTL = timedelta(days=1)
    owner = django_user_model.objects.create_user(username="owner")
    other = django_user_model.objects.create_user(username="other")
    now = timezone.now()
    row = Resume.objects.create(
        name="Synthetic",
        slug="synthetic",
        owner=owner,
        plugin_data={
            "education": {
                "items": [
                    {
                        "id": str(i),
                        "school_name": f"Synthetic school {i}",
                        "position": i,
                    }
                    for i in range(size)
                ]
            },
            "token": {
                "items": [
                    {"id": "valid", "token": "valid", "created": now.isoformat()},
                    {
                        "id": "expired",
                        "token": "expired",
                        "created": (now - timedelta(days=3)).isoformat(),
                    },
                ]
            },
        },
    )
    request = RequestFactory().get(
        "/resume/synthetic/cv/", {"token": token} if token else {}
    )
    request.user = {"owner": owner, "other": other, "anonymous": AnonymousUser()}[
        visitor
    ]
    # RequestFactory supplies an already loaded user; dispatch does a single
    # select_related(owner) query. Plain templates have no rendition/site caches.
    with django_assert_num_queries(1):
        response = dispatch_page(request, row.slug, CvPage())
    assert response.status_code == status
    assert response["Cache-Control"] == "private, no-store"
    if status == 200:
        assert f"Synthetic school {size - 1}" in response.content.decode()
    else:
        assert "Synthetic school" not in response.content.decode()


@pytest.mark.django_db
def test_standalone_token_plugin_retains_owner_lookup(user, django_assert_num_queries):
    user.save()
    row = Resume.objects.create(name="Synthetic", slug="synthetic", owner=user)
    request = RequestFactory().get("/")
    request.user = user
    with django_assert_num_queries(1):
        assert TokenPlugin().get_context(request, {}, row.pk, context={}) == {}
    request.user = AnonymousUser()
    with django_assert_num_queries(0), pytest.raises(PermissionDenied):
        TokenPlugin().get_context(request, {}, row.pk, context={})


@pytest.mark.django_db
def test_token_subclass_keeps_original_signature_and_empty_context(user):
    class CustomToken(TokenPlugin):
        name = "custom-token"

        def get_context(
            self, request, plugin_data, resume_pk, *, context, edit=False, theme="plain"
        ):
            assert context == {}
            return {"custom": True}

    user.save()
    row = Resume.objects.create(name="Synthetic", slug="synthetic", owner=user)
    request = RequestFactory().get("/")
    request.user = user
    plugin_registry.register(CustomToken)
    try:
        context = build_section_context(
            request, row, {"unrelated": "value"}, [CustomToken.name]
        )
        assert context[CustomToken.name] == {"custom": True}
    finally:
        plugin_registry.unregister(CustomToken)
