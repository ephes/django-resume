"""Synthetic access policies and versioned round-trip envelopes."""

from copy import deepcopy

import pytest
from django.urls import reverse

from django_resume.formats.json_resume.export import (
    _source_document_for_unchanged_import,
    export_resume,
)
from django_resume.formats.json_resume.importer import import_resume_document
from django_resume.models import Resume


def envelope_document(plugin_data, **envelope):
    return {
        "basics": {"name": "Synthetic"},
        "meta": {"django_resume": {"plugin_data": plugin_data, **envelope}},
    }


@pytest.mark.django_db
@pytest.mark.parametrize("value", [None, 0, 1, "", "false", [], {}])
def test_import_refuses_non_boolean_token_policy(user, value):
    user.save()
    result = import_resume_document(
        envelope_document({"token": {"flat": {"token_required": value}}}),
        owner=user,
        slug="invalid-policy",
    )
    assert result.resume is None
    assert not result.report.valid
    assert result.report.validation_errors == [
        "meta.django_resume.plugin_data.token.flat.token_required must be a boolean"
    ]
    assert not Resume.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("value", [None, 0, 1, "", "false", [], {}, False, True])
def test_persisted_policy_only_explicit_false_allows_cv(client, user, value):
    user.save()
    row = Resume.objects.create(
        name="Synthetic",
        slug="policy",
        owner=user,
        plugin_data={
            "token": {"flat": {"token_required": value}},
            "education": {"items": [{"id": "school", "school_name": "Private school"}]},
        },
    )
    response = client.get(reverse("resume:cv", kwargs={"slug": row.slug}))
    assert response.status_code == (200 if value is False else 403)
    assert ("Private school" in response.content.decode()) is (value is False)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "flat", [{}, {"token_required": True}, {"token_required": False}]
)
def test_supported_and_absent_token_policies_import(client, user, flat):
    user.save()
    result = import_resume_document(
        envelope_document({"token": {"flat": flat}}), owner=user, slug="valid-policy"
    )
    assert result.report.valid
    response = client.get(reverse("resume:cv", kwargs={"slug": result.resume.slug}))
    assert response.status_code == (200 if flat.get("token_required") is False else 403)


@pytest.mark.django_db
@pytest.mark.parametrize("version", [2, 0, -1, True, False, "1", None, [], {}])
def test_unsupported_envelope_version_refuses_restore_but_allows_portable(
    user, version
):
    user.save()
    document = envelope_document(
        {"private_extension": {"secret": "synthetic"}},
        version=version,
        preserved_extensions=[{"future": "private"}],
    )
    before = deepcopy(document)
    result = import_resume_document(document, owner=user, slug="rejected-version")
    assert result.resume is None
    assert not result.report.valid
    assert any(
        "meta.django_resume.version" in error
        for error in result.report.validation_errors
    )
    assert not Resume.objects.exists()

    portable = import_resume_document(
        document, owner=user, slug="portable", restore_django_resume_data=False
    )
    assert portable.report.valid
    assert portable.resume.plugin_data["identity"]["name"] == "Synthetic"
    assert "private_extension" not in portable.resume.plugin_data
    state = portable.resume.integration_data["json_resume"]
    assert "source_document" not in state
    assert "preserved_extensions" not in state
    assert any(
        "version" in note and "ignored" in note for note in portable.report.notes
    )
    assert any(
        "unsupported meta.django_resume envelope was ignored" in note
        for note in portable.report.notes
    )
    assert not any("plugin_data was ignored" in note for note in portable.report.notes)
    assert (
        "private_extension"
        not in export_resume(portable.resume).document["meta"]["django_resume"][
            "plugin_data"
        ]
    )
    assert document == before


@pytest.mark.django_db
@pytest.mark.parametrize("envelope", [{}, {"version": 1}])
def test_legacy_and_v1_nested_payload_roundtrip_without_mutation(user, envelope):
    user.save()
    document = envelope_document(
        {"opaque": {"nested": [{"value": True}, [None, 1, "one"]]}}, **envelope
    )
    before = deepcopy(document)
    result = import_resume_document(document, owner=user, slug="unchanged")
    assert result.report.valid
    exported = export_resume(result.resume)
    assert exported.report.valid
    assert exported.document == before
    assert document == before
    exported.document["meta"]["django_resume"]["plugin_data"]["opaque"][
        "nested"
    ].clear()
    assert document == before
    assert result.resume.plugin_data["opaque"]["nested"]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "original,edited", [(True, 1), (False, 0), (1, True), (1, 1.0)]
)
def test_json_type_edit_to_opaque_plugin_is_exported(user, original, edited):
    user.save()
    document = envelope_document({"opaque": {"nested": [{"value": original}]}})
    result = import_resume_document(document, owner=user, slug="edited")
    row = result.resume
    row.plugin_data["opaque"]["nested"][0]["value"] = edited
    row.save()
    row.refresh_from_db()
    exported = export_resume(row)
    value = exported.document["meta"]["django_resume"]["plugin_data"]["opaque"][
        "nested"
    ][0]["value"]
    assert type(value) is type(edited)
    assert value == edited
    assert (
        document["meta"]["django_resume"]["plugin_data"]["opaque"]["nested"][0]["value"]
        is original
    )


def test_projection_json_types_also_prevent_source_reuse(resume):
    resume.plugin_data = {}
    resume.integration_data = {
        "json_resume": {
            "source_document": {"basics": {"name": "Source"}},
            "source_adapter_document": {"custom": {"value": True}},
            "source_plugin_data": {},
        }
    }
    assert (
        _source_document_for_unchanged_import(resume, {"custom": {"value": 1}}) is None
    )
