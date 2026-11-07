"""Synthetic round-trip envelopes through preview, planning and creation."""

from copy import deepcopy
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from django_resume.formats.json_resume.export import export_resume
from django_resume.formats.json_resume.importer import (
    create_prepared_import,
    prepare_resume_import,
)
from django_resume.models import Resume
from django_resume.plugins.education import EducationPlugin


INVALID_ITEMS = [
    [{}],
    [{"id": ""}],
    [{"id": " "}],
    [{"id": 7}],
    [{"id": "same"}, {"id": "same"}],
    [{"id": "a", "position": 0}, {"id": "b", "position": "1"}],
    [{"id": "a", "position": None}],
    [{"id": "a", "position": True}],
    [{"id": "a", "position": 1.5}],
    [{"id": "a", "position": {}}],
]


def document_for(plugin, items):
    return {
        "basics": {"name": "Synthetic"},
        "meta": {
            "django_resume": {"plugin_data": {plugin: {"items": deepcopy(items)}}}
        },
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "plugin",
    [
        "awards",
        "cover",
        "education",
        "employed_timeline",
        "freelance_timeline",
        "languages",
        "projects",
        "token",
    ],
)
@pytest.mark.parametrize("items", INVALID_ITEMS)
def test_invalid_list_plan_reports_field_and_never_creates(user, plugin, items):
    user.save()
    prepared = prepare_resume_import(
        document_for(plugin, items), slug="rejected", owner=user
    )
    assert prepared.plan is None
    assert not prepared.report.valid
    assert all(
        f"meta.django_resume.plugin_data.{plugin}.items[" in error
        for error in prepared.report.validation_errors
    )
    result = create_prepared_import(prepared, owner=user)
    assert result.resume is None
    assert result.report.validation_errors
    assert not Resume.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("items", INVALID_ITEMS)
def test_invalid_envelope_browser_preview_and_create_do_not_create(client, user, items):
    user.save()
    client.force_login(user)
    document = json.dumps(document_for("education", items)).encode()
    for action in ("preview", "create"):
        response = client.post(
            reverse("resume:json-resume-import"),
            {
                "action": action,
                "slug": "rejected",
                "file": SimpleUploadedFile(
                    "synthetic.json", document, "application/json"
                ),
            },
        )
        assert response.status_code == 200
        if action == "preview":
            assert "education.items[" in response.content.decode()
            assert "import_preview" not in response.context
        else:
            assert response.context["import_form"].non_field_errors()
        assert not Resume.objects.exists()


@pytest.mark.django_db
def test_older_valid_envelope_reexports_and_remains_editable(client, user):
    user.save()
    client.force_login(user)
    document = document_for(
        "education", [{"id": "older", "school_name": "Synthetic school"}]
    )
    prepared = prepare_resume_import(document, slug="older", owner=user)
    assert prepared.report.valid
    result = create_prepared_import(prepared, owner=user)
    row = result.resume
    assert row is not None
    assert export_resume(row).document == document
    plugin = EducationPlugin()
    response = client.get(plugin.inline.get_edit_item_url(row.pk, "older"))
    form = response.context["form"]
    data = {name: form[name].value() or "" for name in form.fields}
    data["school_name"] = "Edited synthetic school"
    assert client.post(plugin.inline.get_post_item_url(row.pk), data).status_code == 200
    row.refresh_from_db()
    assert (
        row.plugin_data["education"]["items"][0]["school_name"]
        == "Edited synthetic school"
    )


@pytest.mark.django_db
def test_unknown_plugin_item_schema_is_preserved(user):
    user.save()
    document = document_for(
        "custom_extension", [{"position": "first"}, {"id": 7, "position": None}]
    )
    prepared = prepare_resume_import(document, slug="extension", owner=user)
    assert prepared.report.valid
    result = create_prepared_import(prepared, owner=user)
    assert result.resume.plugin_data == document["meta"]["django_resume"]["plugin_data"]
    assert export_resume(result.resume).document == document
