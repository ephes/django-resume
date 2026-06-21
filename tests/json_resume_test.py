import json
import json as _json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

import django_resume.formats.json_resume as json_resume_pkg
from django_resume.formats.json_resume.dates import is_valid_resume_date
from django_resume.formats.json_resume.export import export_resume
from django_resume.formats.json_resume.validation import validate_document
from django_resume.interchange.coordinator import (
    ResolvedAdapter,
    PathConflictError,
    build_document,
)
from django_resume.models import Resume
from django_resume.plugins import SimplePlugin, ListPlugin
from django_resume.plugins.about import AboutPlugin
from django_resume.plugins.education import EducationPlugin
from django_resume.plugins.identity import IdentityPlugin
from django_resume.plugins.projects import ProjectsPlugin
from django_resume.plugins.skills import SkillsPlugin
from django_resume.plugins.timelines import (
    FreelanceTimelinePlugin,
    EmployedTimelinePlugin,
)


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
    plugin.data.set_data(
        resume,
        {
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
        },
    )
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


def test_about_facts_and_adapter_map_to_summary(resume):
    plugin = AboutPlugin()
    plugin.data.set_data(resume, {"title": "About me", "text": "I build things."})
    facts = plugin.get_structured_data(resume)
    assert facts["summary"] == "I build things."
    adapter = plugin.get_export_adapters()["json_resume"]
    result = adapter.export(facts)
    assert result.contributions == [("/basics/summary", "I build things.")]
    assert any("about.title" in note for note in result.notes)


def test_skills_facts_and_adapter_map_to_skill_objects(resume):
    plugin = SkillsPlugin()
    plugin.data.set_data(resume, {"badges": ["Python", "Django", ""]})
    facts = plugin.get_structured_data(resume)
    assert facts["skills"] == ["Python", "Django", ""]
    adapter = plugin.get_export_adapters()["json_resume"]
    result = adapter.export(facts)
    assert result.contributions == [
        ("/skills", [{"name": "Python"}, {"name": "Django"}])
    ]


def test_education_adapter_maps_valid_entry(resume):
    plugin = EducationPlugin()
    plugin.data.set_data(
        resume,
        {
            "school_name": "State University",
            "school_url": "https://uni.example",
            "start": "2010",
            "end": "2014",
        },
    )
    facts = plugin.get_structured_data(resume)
    adapter = plugin.get_export_adapters()["json_resume"]
    result = adapter.export(facts)
    assert result.contributions == [
        (
            "/education",
            [
                {
                    "institution": "State University",
                    "url": "https://uni.example",
                    "startDate": "2010",
                    "endDate": "2014",
                }
            ],
        )
    ]
    assert result.notes == []


def test_education_adapter_omits_and_reports_invalid_date(resume):
    plugin = EducationPlugin()
    plugin.data.set_data(resume, {"school_name": "Uni", "start": "start", "end": ""})
    facts = plugin.get_structured_data(resume)
    result = plugin.get_export_adapters()["json_resume"].export(facts)
    entry = dict(result.contributions)["/education"][0]
    assert entry == {"institution": "Uni"}
    assert any("start" in note for note in result.notes)


def test_timeline_adapter_maps_items_to_work_and_omits_bad_dates(resume):
    plugin = FreelanceTimelinePlugin()
    plugin.data.set_data(
        resume,
        {
            "items": [
                {
                    "id": "1",
                    "company_name": "ACME",
                    "company_url": "https://acme.example",
                    "role": "Engineer",
                    "description": "Built things",
                    "start": "2019",
                    "end": "nope",
                    "badges": ["remote", "full-time"],
                    "position": 1,
                },
            ]
        },
    )
    facts = plugin.get_structured_data(resume)
    result = plugin.get_export_adapters()["json_resume"].export(facts)
    work = dict(result.contributions)["/work"]
    assert work == [
        {
            "name": "ACME",
            "url": "https://acme.example",
            "position": "Engineer",
            "summary": "Built things",
            "highlights": ["remote", "full-time"],
            "startDate": "2019",
        }
    ]
    assert any("end date" in note for note in result.notes)


def test_both_timeline_plugins_declare_multivalued_work():
    for plugin_cls in (FreelanceTimelinePlugin, EmployedTimelinePlugin):
        adapter = plugin_cls().get_export_adapters()["json_resume"]
        assert adapter.owned_paths == ("/work",)
        assert adapter.multivalued_paths == ("/work",)


def test_projects_adapter_maps_items(resume):
    plugin = ProjectsPlugin()
    plugin.data.set_data(
        resume,
        {
            "items": [
                {
                    "id": "1",
                    "title": "Cool Tool",
                    "url": "https://tool.example",
                    "description": "Does things",
                    "badges": ["python", ""],
                    "position": 0,
                },
            ]
        },
    )
    facts = plugin.get_structured_data(resume)
    result = plugin.get_export_adapters()["json_resume"].export(facts)
    assert result.contributions == [
        (
            "/projects",
            [
                {
                    "name": "Cool Tool",
                    "url": "https://tool.example",
                    "description": "Does things",
                    "keywords": ["python"],
                }
            ],
        )
    ]


@pytest.mark.django_db
def test_export_resume_assembles_validates_and_reports(user):
    user.save()
    resume = Resume.objects.create(name="Jane", slug="jane", owner=user)
    IdentityPlugin().data.set_data(
        resume,
        {
            "name": "Jane Doe",
            "email": "jane@example.com",
        },
    )
    AboutPlugin().data.set_data(resume, {"title": "About", "text": "Hello"})
    resume.save()

    result = export_resume(resume)

    assert result.document["basics"]["name"] == "Jane Doe"
    assert result.document["basics"]["summary"] == "Hello"
    assert result.report.valid
    assert result.report.validation_errors == []
    assert "identity" in result.report.mapped_plugins
    assert "cover" in result.report.omitted_plugins


@pytest.mark.django_db
def test_command_writes_valid_json_to_stdout(user):
    user.save()
    resume = Resume.objects.create(name="Jane", slug="jane-cli", owner=user)
    IdentityPlugin().data.set_data(resume, {"name": "Jane Doe"})
    resume.save()

    stdout, stderr = StringIO(), StringIO()
    call_command("export_json_resume", "jane-cli", stdout=stdout, stderr=stderr)

    document = _json.loads(stdout.getvalue())
    assert document["basics"]["name"] == "Jane Doe"
    assert "Mapped plugins" in stderr.getvalue()


@pytest.mark.django_db
def test_command_errors_on_unknown_slug():
    with pytest.raises(CommandError):
        call_command("export_json_resume", "does-not-exist")


@pytest.mark.django_db
def test_full_resume_exports_and_validates(user):
    user.save()
    resume = Resume.objects.create(name="Jane", slug="jane-full", owner=user)
    IdentityPlugin().data.set_data(
        resume,
        {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "tagline": "Engineer",
            "github": "https://github.com/jane",
        },
    )
    AboutPlugin().data.set_data(resume, {"title": "About", "text": "Hello there."})
    SkillsPlugin().data.set_data(resume, {"badges": ["Python", "Django"]})
    EducationPlugin().data.set_data(
        resume,
        {
            "school_name": "Uni",
            "school_url": "https://uni.example",
            "start": "2010",
            "end": "2014",
        },
    )
    FreelanceTimelinePlugin().data.set_data(
        resume,
        {
            "items": [
                {
                    "id": "f1",
                    "company_name": "Acme",
                    "company_url": "https://acme.example",
                    "role": "Dev",
                    "description": "work",
                    "start": "2015",
                    "end": "2018",
                    "badges": ["remote"],
                    "position": 1,
                },
            ]
        },
    )
    EmployedTimelinePlugin().data.set_data(
        resume,
        {
            "items": [
                {
                    "id": "e1",
                    "company_name": "BigCo",
                    "company_url": "https://bigco.example",
                    "role": "Lead",
                    "description": "work",
                    "start": "2018",
                    "end": "2022",
                    "badges": [],
                    "position": 1,
                },
            ]
        },
    )
    ProjectsPlugin().data.set_data(
        resume,
        {
            "items": [
                {
                    "id": "p1",
                    "title": "Tool",
                    "url": "https://tool.example",
                    "description": "does things",
                    "badges": ["python"],
                    "position": 0,
                },
            ]
        },
    )
    resume.save()

    result = export_resume(resume)

    assert result.report.valid, result.report.validation_errors
    # Both timeline plugins contributed to a single concatenated work array.
    assert {entry["name"] for entry in result.document["work"]} == {"Acme", "BigCo"}
    assert result.document["education"][0]["institution"] == "Uni"
    assert result.document["skills"] == [{"name": "Python"}, {"name": "Django"}]


def test_conflicting_scalar_adapters_raise(resume):
    class _A:
        owned_paths = ("/basics/name",)
        multivalued_paths = ()

        def export(self, facts):
            from django_resume.interchange.protocols import AdapterExport

            return AdapterExport(contributions=[("/basics/name", "x")])

    with pytest.raises(PathConflictError):
        build_document(
            [
                ResolvedAdapter("a", _A(), {}),
                ResolvedAdapter("b", _A(), {}),
            ]
        )
