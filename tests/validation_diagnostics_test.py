"""Schema errors have a bounded traversal and never format document values."""

import io
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.urls import reverse

from django_resume.formats.json_resume.validation import validate_document
from django_resume.models import Resume


def test_schema_stops_after_error_budget():
    seen = []

    class Entries(list):
        def __iter__(self):
            for entry in super().__iter__():
                seen.append(True)
                yield entry

    errors = validate_document({"work": Entries([{"name": False}] * 1000)})
    assert len(seen) <= 20
    assert len(errors) <= 21
    assert "omitted" in errors[-1]
    assert errors == validate_document({"work": [{"name": False}] * 1000})


def test_schema_never_formats_invalid_values():
    class PrivateString(str):
        def __repr__(self):
            pytest.fail("Schema diagnostics must not build value representations")

    errors = validate_document({"work": [{"startDate": PrivateString("x" * 1000000)}]})
    assert "work/0/startDate" in errors[0]
    assert len(errors[0]) <= 256


def test_schema_bounds_unexpected_member_path():
    errors = validate_document({"x" * 1000000: True})
    assert len(errors[0]) <= 256


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["many", "large"])
def test_preview_and_cli_diagnostics_are_bounded(client, user, tmp_path, kind):
    user.save()
    client.force_login(user)
    document = (
        {"work": [{"name": False}] * 1000}
        if kind == "many"
        else {"work": [{"startDate": "x" * 1900000}]}
    )
    data = json.dumps(document).encode()
    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "file": SimpleUploadedFile("synthetic.json", data, "application/json"),
            "slug": "diagnostics",
            "action": "preview",
        },
    )
    assert response.status_code == 200
    assert len(response.content) < 20000
    assert b"work/0/" in response.content
    path = tmp_path / "synthetic.json"
    path.write_bytes(data)
    errors = io.StringIO()
    with pytest.raises(CommandError, match="schema validation"):
        call_command(
            "import_json_resume",
            str(path),
            owner=user.username,
            slug="diagnostics",
            stderr=errors,
        )
    assert len(errors.getvalue()) < 6000
    assert "work/0/" in errors.getvalue()
    if kind == "many":
        assert "omitted" in errors.getvalue()
        assert b"omitted" in response.content
    assert not Resume.objects.exists()


@pytest.mark.parametrize(
    "document",
    [
        {},
        {"basics": {"name": "Synthetic", "vendor": {"x": True}}},
        {"work": [{"startDate": "2020-01-01"}]},
        {"work": [{"startDate": "invalid"}]},
        {"work": False},
        {"unknown": True},
        {"skills": [{"keywords": [False]}]},
    ],
)
def test_bounded_diagnostics_preserve_pinned_schema_validity(document):
    from jsonschema.validators import validator_for
    from django_resume.formats.json_resume.validation import _schema

    schema = _schema()
    assert (not validate_document(document)) == validator_for(schema)(schema).is_valid(
        document
    )


def test_pinned_schema_only_uses_bounded_error_handlers():
    from jsonschema.validators import validator_for
    from django_resume.formats.json_resume.validation import _schema

    schema = _schema()
    validator_keywords = validator_for(schema).VALIDATORS
    allowed = {
        "type",
        "pattern",
        "additionalProperties",
        "$ref",
        "properties",
        "items",
        "additionalItems",
        "format",
    }

    def inspect(node):
        if isinstance(node, dict):
            assert set(node) & validator_keywords.keys() <= allowed
            if "additionalProperties" in node:
                assert isinstance(node["additionalProperties"], bool)
            if "additionalItems" in node:
                assert isinstance(node["items"], dict)
            for value in node.values():
                inspect(value)
        elif isinstance(node, list):
            for value in node:
                inspect(value)

    inspect(schema)
