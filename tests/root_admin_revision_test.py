"""The actual root admin form cannot replace a newer document."""

import json

import pytest
from django.urls import reverse

from django_resume.plugins.identity import IdentityPlugin
from tests.editor_helpers import post_current_editor


def root_data(form):
    return {
        "name": "Synthetic edited",
        "slug": form.instance.slug,
        "owner": form.instance.owner_id,
        "plugin_data": json.dumps(form.initial["plugin_data"]),
        "integration_data": json.dumps(form.initial["integration_data"]),
        "edit_revision": form["edit_revision"].value()
        if "edit_revision" in form.fields
        else "",
        "_save": "Save",
    }


@pytest.mark.django_db
@pytest.mark.parametrize("changed", ["plugin_data", "integration_data", "name"])
def test_root_admin_rejects_stale_document(admin_client, resume, changed):
    resume.owner.save()
    resume.plugin_data = {"identity": {"name": "Before"}}
    resume.integration_data = {"extension": "Before"}
    resume.save()
    url = reverse("admin:django_resume_resume_change", args=[resume.pk])
    form = admin_client.get(url).context["adminform"].form
    data = root_data(form)
    if changed == "plugin_data":
        resume.owner.is_staff = True
        resume.owner.save()
        admin_client.force_login(resume.owner)
        response = post_current_editor(
            admin_client,
            IdentityPlugin().admin.get_change_post_url(resume.pk),
            {"name": "After"},
        )
        assert response.status_code == 200
        from django.contrib.auth import get_user_model

        admin_client.force_login(get_user_model().objects.get(is_superuser=True))
    else:
        setattr(
            resume,
            changed,
            {"extension": "After"} if changed == "integration_data" else "After",
        )
        resume.save(update_fields=[changed])
    resume.refresh_from_db()
    current = (resume.name, resume.plugin_data, resume.integration_data)
    response = admin_client.post(url, data)
    assert response.status_code == 200
    assert response.context["adminform"].form.errors
    resume.refresh_from_db()
    assert (resume.name, resume.plugin_data, resume.integration_data) == current


@pytest.mark.django_db
def test_root_admin_fresh_document_is_editable(admin_client, resume):
    resume.owner.save()
    resume.save()
    url = reverse("admin:django_resume_resume_change", args=[resume.pk])
    data = root_data(admin_client.get(url).context["adminform"].form)
    data.update(
        plugin_data='{"vendor":{"answer":42}}', integration_data='{"vendor":true}'
    )
    assert admin_client.post(url, data).status_code == 302
    resume.refresh_from_db()
    assert resume.name == "Synthetic edited"
    assert resume.plugin_data == {"vendor": {"answer": 42}}
    assert resume.integration_data == {"vendor": True}


@pytest.mark.django_db
@pytest.mark.parametrize("token", ["", "tampered"])
def test_root_admin_requires_current_signed_revision(admin_client, resume, token):
    resume.owner.save()
    resume.save()
    url = reverse("admin:django_resume_resume_change", args=[resume.pk])
    data = root_data(admin_client.get(url).context["adminform"].form)
    data["edit_revision"] = token
    response = admin_client.post(url, data)
    assert response.status_code == 200
    assert response.context["adminform"].form.errors["edit_revision"]
    resume.refresh_from_db()
    assert resume.name == "John Doe"


@pytest.mark.django_db(databases=["default", "other"])
@pytest.mark.parametrize("conflict", [False, True])
def test_root_admin_uses_routed_writer_and_cas(
    admin_client, resume, settings, monkeypatch, conflict
):
    from django.db import connections
    from django.db.models import QuerySet
    from django.contrib.admin.models import LogEntry

    resume.owner.save()
    resume.save()
    # Resume writes go to other; auth and admin logging stay on default.
    from django.contrib.auth import get_user_model

    # Same pk on both aliases: the admin validates the owner choice on default
    # (only Resume is routed), while the routed row's FK lives on other.
    owner = (
        get_user_model()
        .objects.db_manager("other")
        .create(pk=resume.owner.pk, username="synthetic")
    )
    from django_resume.models import Resume

    row = Resume.objects.using("other").create(name="Other", slug="other", owner=owner)
    url = reverse("admin:django_resume_resume_change", args=[row.pk])

    class Router:
        def db_for_read(self, model, **hints):
            return "other" if model is Resume else None

        def db_for_write(self, model, **hints):
            return "other" if model is Resume else None

        def allow_relation(self, obj1, obj2, **hints):
            return True

    settings.DATABASE_ROUTERS = [Router()]
    data = root_data(admin_client.get(url).context["adminform"].form)
    original_update = QuerySet.update
    calls = []

    def lose_cas(queryset, **kwargs):
        if queryset.model is Resume:
            assert queryset.db == "other"
            assert connections["other"].in_atomic_block
            assert "plugin_data" in str(queryset.query)
            calls.append(True)
            if conflict:
                return 0
        return original_update(queryset, **kwargs)

    monkeypatch.setattr(QuerySet, "update", lose_cas)
    response = admin_client.post(url, data)
    assert response.status_code == (200 if conflict else 302)
    if conflict:
        assert response.context["adminform"].form.non_field_errors()
    assert calls == [True]
    row.refresh_from_db(using="other")
    resume.refresh_from_db(using="default")
    assert row.name == ("Other" if conflict else "Synthetic edited")
    assert resume.name == "John Doe"
    assert LogEntry.objects.count() == (0 if conflict else 1)


@pytest.mark.django_db
def test_root_admin_can_clear_json_fields(admin_client, resume):
    resume.owner.save()
    resume.plugin_data = {"vendor": "old"}
    resume.integration_data = {"vendor": "old"}
    resume.save()
    url = reverse("admin:django_resume_resume_change", args=[resume.pk])
    data = root_data(admin_client.get(url).context["adminform"].form)
    data.update(plugin_data="", integration_data="")
    assert admin_client.post(url, data).status_code == 302
    resume.refresh_from_db()
    assert resume.plugin_data == resume.integration_data == {}


@pytest.mark.django_db
def test_root_admin_permission_denial_keeps_document(client, resume):
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    url = reverse("admin:django_resume_resume_change", args=[resume.pk])
    assert (
        client.post(url, {"name": "Forbidden", "edit_revision": "tampered"}).status_code
        == 403
    )
    resume.refresh_from_db()
    assert resume.name == "John Doe"
