import json
from pathlib import Path

import django_resume.formats.json_resume as json_resume_pkg
from django_resume.plugins import SimplePlugin, ListPlugin


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
