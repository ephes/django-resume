import json
from pathlib import Path

import django_resume.formats.json_resume as json_resume_pkg
from django_resume.formats.json_resume.dates import is_valid_resume_date
from django_resume.formats.json_resume.validation import validate_document
from django_resume.plugins import SimplePlugin, ListPlugin
from django_resume.plugins.identity import IdentityPlugin


def test_vendored_schema_is_present_and_loadable():
    schema_path = Path(json_resume_pkg.__file__).parent / "schema" / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "basics" in schema["properties"]
    assert "work" in schema["properties"]
    assert "iso8601" in schema["definitions"]


def test_base_plugins_expose_empty_export_defaults(resume):
    assert SimplePlugin().get_structured_data(resume) == {}
    assert SimplePlugin().get_export_adapters() == {}
    assert ListPlugin().get_structured_data(resume) == {}
    assert ListPlugin().get_export_adapters() == {}


def test_is_valid_resume_date_accepts_iso_forms():
    assert is_valid_resume_date("2020")
    assert is_valid_resume_date("2020-06")
    assert is_valid_resume_date("2020-06-29")


def test_is_valid_resume_date_rejects_placeholders_and_empty():
    assert not is_valid_resume_date("start")
    assert not is_valid_resume_date("")
    assert not is_valid_resume_date("2020/06")


def test_validate_document_accepts_minimal_valid_document():
    assert validate_document({"basics": {"name": "Jane"}}) == []


def test_validate_document_reports_bad_date_pattern():
    errors = validate_document({"work": [{"name": "ACME", "startDate": "nope"}]})
    assert errors
    assert any("startDate" in message or "0" in message for message in errors)


def test_identity_facts_and_adapter_map_to_basics(resume):
    plugin = IdentityPlugin()
    plugin.data.set_data(resume, {
        "name": "Jane Doe",
        "tagline": "Engineer",
        "email": "jane@example.com",
        "phone": "+1 555",
        "github": "https://github.com/jane",
        "linkedin": "https://linkedin.com/in/jane",
        "mastodon": "",
        "pronouns": "she/her",
        "location_name": "Berlin",
        "location_url": "https://maps.example/berlin",
        "avatar_alt": "Jane's headshot",
    })
    facts = plugin.get_structured_data(resume)
    assert facts["name"] == "Jane Doe"
    adapter = plugin.get_export_adapters()["json_resume"]
    result = adapter.export(facts)
    contributions = dict(result.contributions)
    assert contributions["/basics/name"] == "Jane Doe"
    assert contributions["/basics/label"] == "Engineer"
    assert contributions["/basics/email"] == "jane@example.com"
    assert contributions["/basics/profiles"] == [
        {"network": "GitHub", "url": "https://github.com/jane"},
        {"network": "LinkedIn", "url": "https://linkedin.com/in/jane"},
    ]
    assert any("pronouns" in note for note in result.notes)
    assert any("location_name" in note for note in result.notes)
    assert any("avatar_alt" in note for note in result.notes)
