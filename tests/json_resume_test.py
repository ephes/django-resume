import json
import json as _json
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError
from django.urls import reverse

import django_resume.formats.json_resume as json_resume_pkg
from django_resume.formats.json_resume.dates import is_valid_resume_date
from django_resume.formats.json_resume.export import export_resume
from django_resume.formats.json_resume.importer import (
    JsonResumeImportError,
    MAX_INPUT_BYTES,
    import_resume_document,
    load_document,
)
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


def load_official_schema_sample() -> dict:
    path = Path(__file__).parent / "fixtures" / "jsonresume_schema_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_vendored_schema_is_present_and_loadable():
    schema_path = Path(json_resume_pkg.__file__).parent / "schema" / "schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    assert "basics" in schema["properties"]
    assert "work" in schema["properties"]
    assert "iso8601" in schema["definitions"]


def test_base_plugins_expose_empty_export_defaults(resume):
    assert SimplePlugin().get_structured_data(resume) == {}
    assert SimplePlugin().get_export_adapters() == {}
    assert SimplePlugin().get_import_adapters() == {}
    assert ListPlugin().get_structured_data(resume) == {}
    assert ListPlugin().get_export_adapters() == {}
    assert ListPlugin().get_import_adapters() == {}


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
    assert result.document["meta"]["django_resume"]["plugin_data"]["about"] == {
        "title": "About",
        "text": "Hello",
    }
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
    assert result.document["meta"]["django_resume"]["plugin_data"] == resume.plugin_data


def test_skills_facts_parse_json_string_badges(resume):
    plugin = SkillsPlugin()
    plugin.data.set_data(resume, {"badges": '["Python", "Django"]'})
    facts = plugin.get_structured_data(resume)
    assert facts["skills"] == ["Python", "Django"]


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


@pytest.mark.django_db
def test_import_resume_document_creates_resume_from_portable_json(user):
    user.save()
    document = {
        "basics": {
            "name": "Jane Doe",
            "label": "Engineer",
            "email": "jane@example.com",
            "phone": "+1",
            "url": "https://jane.example",
            "summary": "Hello",
            "profiles": [
                {"network": "GitHub", "url": "https://github.com/jane"},
                {"network": "Bluesky", "url": "https://bsky.app/profile/jane"},
            ],
        },
        "skills": [
            {"name": "Python", "level": "Senior", "keywords": ["Django", "pytest"]}
        ],
        "education": [
            {
                "institution": "Uni",
                "url": "https://uni.example",
                "startDate": "2010",
                "endDate": "2014",
            },
            {
                "institution": "Second Uni",
            },
        ],
        "work": [
            {
                "name": "Acme",
                "url": "https://acme.example",
                "position": "Dev",
                "summary": "Built things",
                "startDate": "2020",
                "highlights": ["Django"],
            }
        ],
        "projects": [
            {
                "name": "Tool",
                "url": "https://tool.example",
                "description": "Does things",
                "keywords": ["python"],
            }
        ],
    }

    result = import_resume_document(document, owner=user, slug="jane-imported")

    assert result.resume is not None
    imported = Resume.objects.get(slug="jane-imported")
    assert imported.name == "Jane Doe"
    assert imported.plugin_data["identity"]["github"] == "https://github.com/jane"
    assert imported.plugin_data["about"]["text"] == "Hello"
    assert imported.plugin_data["skills"]["badges"] == ["Python"]
    assert imported.plugin_data["education"]["start"] == "2010"
    assert (
        imported.plugin_data["employed_timeline"]["items"][0]["company_name"] == "Acme"
    )
    assert imported.plugin_data["projects"]["items"][0]["title"] == "Tool"
    assert "identity" in result.report.mapped_plugins
    notes = "\n".join(result.report.notes)
    assert "basics.url is not imported" in notes
    assert "basics.profiles entry 'Bluesky' is not imported" in notes
    assert "about.title defaulted to 'About'" in notes
    assert "education entries beyond the first were not imported" in notes
    assert "skills entry 'Python' level is not imported" in notes
    assert "skills entry 'Python' keywords are not imported" in notes
    assert "freelance and employed" in notes
    assert "projects.flat.title defaulted to 'Projects'" in notes


@pytest.mark.django_db
def test_import_resume_document_rejects_invalid_optional_dates(user):
    user.save()
    document = {"work": [{"name": "Acme", "startDate": "Present"}]}

    result = import_resume_document(document, owner=user, slug="bad-date")

    assert result.resume is None
    assert not result.report.valid
    assert result.report.validation_errors
    assert not Resume.objects.filter(slug="bad-date").exists()


@pytest.mark.django_db
def test_import_resume_document_rejects_existing_slug(user):
    user.save()
    Resume.objects.create(name="Existing", slug="existing-slug", owner=user)

    with pytest.raises(
        JsonResumeImportError,
        match="A resume with slug 'existing-slug' already exists",
    ):
        import_resume_document(
            {"basics": {"name": "Jane"}},
            owner=user,
            slug="existing-slug",
        )


@pytest.mark.django_db
def test_import_resume_document_wraps_slug_integrity_race(user, monkeypatch):
    user.save()

    def create_race(*args, **kwargs):
        raise IntegrityError("UNIQUE constraint failed: django_resume_resume.slug")

    monkeypatch.setattr(Resume.objects, "create", create_race)

    with pytest.raises(
        JsonResumeImportError,
        match="A resume with slug 'race-slug' already exists",
    ):
        import_resume_document(
            {"basics": {"name": "Jane"}},
            owner=user,
            slug="race-slug",
        )


@pytest.mark.django_db
def test_import_resume_document_restores_django_resume_plugin_data_for_round_trip(user):
    user.save()
    resume = Resume.objects.create(name="Cleo", slug="cleo", owner=user)
    resume.plugin_data = {
        "identity": {
            "name": "Queen Cleo",
            "pronouns": "she | her | Majesty",
            "tagline": "Royal coach",
        },
        "about": {"title": "About", "text": "Rule well."},
        "education": {
            "school_name": "Alexandria",
            "school_url": "https://alexandria.example",
            "start": "Ancient Times",
            "end": "Cleopatra VII",
        },
        "pyramid": {"height": 230},
    }
    resume.save()
    before = export_resume(resume)
    assert before.report.valid, before.report.validation_errors

    result = import_resume_document(
        before.document,
        owner=user,
        slug="cleo-roundtrip",
        name="Cleo Round Trip",
    )

    assert result.resume is not None
    imported = Resume.objects.get(slug="cleo-roundtrip")
    assert imported.plugin_data == resume.plugin_data
    after = export_resume(imported)
    assert json.dumps(before.document, indent=2, ensure_ascii=False) == json.dumps(
        after.document, indent=2, ensure_ascii=False
    )
    assert "pyramid" in result.report.restored_plugins


@pytest.mark.django_db
def test_imported_official_schema_sample_renders_and_reexports_identically(
    client, user
):
    user.save()
    document = load_official_schema_sample()

    result = import_resume_document(
        document,
        owner=user,
        slug="jsonresume-schema-sample",
        restore_django_resume_data=False,
    )

    assert result.resume is not None
    client.force_login(user)
    response = client.get(
        reverse("django_resume:cv", kwargs={"slug": "jsonresume-schema-sample"})
    )
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "John Doe" in content
    assert "Company" in content
    export_response = client.get(
        reverse(
            "django_resume:json-resume", kwargs={"slug": "jsonresume-schema-sample"}
        )
    )
    assert export_response.status_code == 200
    assert export_response.headers["Content-Type"] == "application/json; charset=utf-8"
    assert (
        export_response.headers["Content-Disposition"]
        == 'attachment; filename="jsonresume-schema-sample.json"'
    )
    assert export_response.headers["Cache-Control"] == "private, no-store"
    assert json.loads(export_response.content) == document

    exported = export_resume(result.resume)
    assert exported.report.valid, exported.report.validation_errors
    assert exported.document == document
    assert any(
        "re-exported unchanged source JSON Resume document" in note
        for note in exported.report.notes
    )


@pytest.mark.django_db
def test_imported_source_document_is_not_reexported_after_mapped_data_changes(user):
    user.save()
    document = load_official_schema_sample()
    result = import_resume_document(
        document,
        owner=user,
        slug="jsonresume-schema-edited",
        restore_django_resume_data=False,
    )
    assert result.resume is not None
    resume = result.resume
    plugin_data = dict(resume.plugin_data)
    identity = dict(plugin_data["identity"])
    identity["name"] = "Jane Changed"
    plugin_data["identity"] = identity
    resume.plugin_data = plugin_data
    resume.save()

    exported = export_resume(resume)

    assert exported.document != document
    assert exported.document["basics"]["name"] == "Jane Changed"
    assert (
        exported.document["meta"]["django_resume"]["plugin_data"] == resume.plugin_data
    )


@pytest.mark.django_db
def test_imported_source_document_is_not_reexported_after_adapterless_data_changes(
    user,
):
    user.save()
    document = load_official_schema_sample()
    result = import_resume_document(
        document,
        owner=user,
        slug="jsonresume-schema-token-edited",
        restore_django_resume_data=False,
    )
    assert result.resume is not None
    resume = result.resume
    plugin_data = dict(resume.plugin_data)
    plugin_data["token"] = {"flat": {"token_required": False}}
    resume.plugin_data = plugin_data
    resume.save()

    exported = export_resume(resume)

    assert exported.document != document
    assert exported.document["meta"]["django_resume"]["plugin_data"]["token"] == {
        "flat": {"token_required": False}
    }


@pytest.mark.django_db
def test_portable_only_import_does_not_reemit_ignored_django_resume_plugin_data(user):
    user.save()
    resume = Resume.objects.create(name="Jane", slug="jane-private-token", owner=user)
    resume.plugin_data = {
        "identity": {"name": "Jane"},
        "token": {
            "flat": {"token_required": True},
            "items": [{"token": "secret-token", "receiver": "Hiring Manager"}],
        },
    }
    resume.save()
    source = export_resume(resume)
    assert source.document["meta"]["django_resume"]["plugin_data"]["token"]["items"]

    result = import_resume_document(
        source.document,
        owner=user,
        slug="jane-portable-only",
        restore_django_resume_data=False,
    )

    assert result.resume is not None
    imported = result.resume
    assert "token" not in imported.plugin_data
    exported = export_resume(imported)
    exported_plugin_data = exported.document["meta"]["django_resume"]["plugin_data"]
    assert "token" not in exported_plugin_data
    assert exported_plugin_data == imported.plugin_data
    notes = "\n".join(result.report.notes)
    assert "meta.django_resume.plugin_data was ignored" in notes


@pytest.mark.django_db
def test_json_resume_export_view_requires_resume_owner(client, user, django_user_model):
    user.save()
    other = django_user_model.objects.create_user(username="other", password="password")
    resume = Resume.objects.create(name="Jane", slug="jane-private-json", owner=user)
    IdentityPlugin().data.set_data(resume, {"name": "Jane"})
    resume.save()

    response = client.get(
        reverse("django_resume:json-resume", kwargs={"slug": resume.slug})
    )
    assert response.status_code == 302

    client.force_login(other)
    response = client.get(
        reverse("django_resume:json-resume", kwargs={"slug": resume.slug})
    )
    assert response.status_code == 404

    client.force_login(user)
    response = client.get(
        reverse("django_resume:json-resume", kwargs={"slug": resume.slug})
    )
    assert response.status_code == 200
    assert json.loads(response.content)["basics"]["name"] == "Jane"


@pytest.mark.django_db
def test_import_resume_document_rejects_malformed_restored_plugin_data(user):
    user.save()
    document = {
        "basics": {"name": "Jane"},
        "meta": {"django_resume": {"plugin_data": {"token": "not-a-dict"}}},
    }

    result = import_resume_document(document, owner=user, slug="bad-envelope")

    assert result.resume is None
    assert not result.report.valid
    assert result.report.validation_errors == [
        "meta.django_resume.plugin_data.token must be an object"
    ]
    assert not Resume.objects.filter(slug="bad-envelope").exists()


@pytest.mark.django_db
def test_import_resume_document_rejects_non_object_restored_plugin_data(user):
    user.save()
    document = {
        "basics": {"name": "Jane"},
        "meta": {"django_resume": {"plugin_data": "not-an-object"}},
    }

    result = import_resume_document(document, owner=user, slug="bad-envelope-type")

    assert result.resume is None
    assert not result.report.valid
    assert result.report.validation_errors == [
        "meta.django_resume.plugin_data must be an object"
    ]


@pytest.mark.django_db
def test_import_resume_document_rejects_render_crashing_plugin_data_shape(user):
    user.save()
    document = {
        "basics": {"name": "Jane"},
        "meta": {"django_resume": {"plugin_data": {"token": {"flat": "bad"}}}},
    }

    result = import_resume_document(document, owner=user, slug="bad-token-envelope")

    assert result.resume is None
    assert not result.report.valid
    assert result.report.validation_errors == [
        "meta.django_resume.plugin_data.token.flat must be an object"
    ]
    assert not Resume.objects.filter(slug="bad-token-envelope").exists()


@pytest.mark.django_db
def test_preserved_extensions_are_stored_and_reexported(user):
    user.save()
    document = {
        "basics": {"name": "Jane"},
        "meta": {
            "django_resume": {
                "preserved_extensions": [
                    {
                        "source_path": "/basics/x-third-party",
                        "payload": {"rating": "excellent"},
                        "origin": "third-party",
                    }
                ]
            }
        },
    }

    result = import_resume_document(
        document,
        owner=user,
        slug="jane-preserved",
        restore_django_resume_data=False,
    )

    assert result.resume is not None
    exported = export_resume(result.resume)
    assert exported.document["meta"]["django_resume"]["preserved_extensions"] == [
        {
            "source_path": "/basics/x-third-party",
            "payload": {"rating": "excellent"},
            "origin": "third-party",
        }
    ]


@pytest.mark.django_db
def test_import_resume_document_rejects_duplicate_source_path_adapters(user):
    user.save()

    class _Adapter:
        source_paths = ("/basics",)

        def import_data(self, document):
            from django_resume.interchange.protocols import AdapterImport

            return AdapterImport(plugin_data={"name": "Jane"})

    class _Plugin:
        def __init__(self, name):
            self.name = name

        def get_import_adapters(self):
            return {"json_resume": _Adapter()}

    class _Registry:
        @staticmethod
        def get_all_plugins():
            return [_Plugin("a"), _Plugin("b")]

    with pytest.raises(
        JsonResumeImportError,
        match="Multiple import adapters claim source path '/basics'",
    ):
        import_resume_document(
            {"basics": {"name": "Jane"}},
            owner=user,
            slug="conflict",
            registry=_Registry(),
            restore_django_resume_data=False,
        )


@pytest.mark.django_db
def test_import_resume_document_rejects_overlapping_source_path_adapters(user):
    user.save()

    class _Adapter:
        def __init__(self, source_paths):
            self.source_paths = source_paths

        def import_data(self, document):
            from django_resume.interchange.protocols import AdapterImport

            return AdapterImport(plugin_data={"name": "Jane"})

    class _Plugin:
        def __init__(self, name, source_paths):
            self.name = name
            self.source_paths = source_paths

        def get_import_adapters(self):
            return {"json_resume": _Adapter(self.source_paths)}

    class _Registry:
        @staticmethod
        def get_all_plugins():
            return [
                _Plugin("parent", ("/basics",)),
                _Plugin("child", ("/basics/name",)),
            ]

    with pytest.raises(
        JsonResumeImportError,
        match="Overlapping import source paths '/basics' and '/basics/name'",
    ):
        import_resume_document(
            {"basics": {"name": "Jane"}},
            owner=user,
            slug="overlap",
            registry=_Registry(),
            restore_django_resume_data=False,
        )


@pytest.mark.django_db
def test_import_resume_document_rejects_adapter_without_source_paths(user):
    user.save()

    class _Adapter:
        def import_data(self, document):
            from django_resume.interchange.protocols import AdapterImport

            return AdapterImport(plugin_data={"name": "Jane"})

    class _Plugin:
        name = "broken"

        @staticmethod
        def get_import_adapters():
            return {"json_resume": _Adapter()}

    class _Registry:
        @staticmethod
        def get_all_plugins():
            return [_Plugin()]

    with pytest.raises(
        JsonResumeImportError,
        match="Import adapter for plugin 'broken' has no source_paths",
    ):
        import_resume_document(
            {"basics": {"name": "Jane"}},
            owner=user,
            slug="missing-source-paths",
            registry=_Registry(),
            restore_django_resume_data=False,
        )


@pytest.mark.django_db
def test_import_json_resume_command_creates_resume(tmp_path, user):
    user.save()
    path = tmp_path / "resume.json"
    path.write_text(
        json.dumps({"basics": {"name": "CLI Jane", "email": "jane@example.com"}}),
        encoding="utf-8",
    )
    stdout, stderr = StringIO(), StringIO()

    call_command(
        "import_json_resume",
        str(path),
        "--owner",
        user.username,
        "--slug",
        "cli-jane",
        stdout=stdout,
        stderr=stderr,
    )

    assert Resume.objects.get(slug="cli-jane").name == "CLI Jane"
    assert "Imported" in stdout.getvalue()
    assert "Mapped plugins" in stderr.getvalue()


@pytest.mark.django_db
def test_import_json_resume_command_errors_on_unknown_owner(tmp_path):
    path = tmp_path / "resume.json"
    path.write_text(json.dumps({"basics": {"name": "Jane"}}), encoding="utf-8")
    with pytest.raises(CommandError):
        call_command(
            "import_json_resume",
            str(path),
            "--owner",
            "missing",
            "--slug",
            "jane",
        )


@pytest.mark.django_db
def test_import_json_resume_command_errors_on_missing_file(user):
    user.save()
    with pytest.raises(CommandError, match="Could not read"):
        call_command(
            "import_json_resume",
            "/tmp/does-not-exist-json-resume.json",
            "--owner",
            user.username,
            "--slug",
            "missing-file",
        )


@pytest.mark.django_db
def test_import_json_resume_command_errors_on_invalid_slug(tmp_path, user):
    user.save()
    path = tmp_path / "resume.json"
    path.write_text(json.dumps({"basics": {"name": "Jane"}}), encoding="utf-8")

    with pytest.raises(CommandError, match="Invalid resume slug"):
        call_command(
            "import_json_resume",
            str(path),
            "--owner",
            user.username,
            "--slug",
            "bad slug",
        )


@pytest.mark.django_db
def test_import_json_resume_command_errors_on_overlong_name(tmp_path, user):
    user.save()
    path = tmp_path / "resume.json"
    path.write_text(
        json.dumps({"basics": {"name": "J" * 256}}),
        encoding="utf-8",
    )

    with pytest.raises(CommandError, match="Resume name exceeds maximum length"):
        call_command(
            "import_json_resume",
            str(path),
            "--owner",
            user.username,
            "--slug",
            "overlong-name",
        )


def test_load_document_rejects_duplicate_keys(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text('{"basics": {"name": "Jane", "name": "Janet"}}', encoding="utf-8")
    with pytest.raises(JsonResumeImportError, match="Duplicate JSON object key"):
        load_document(path)


def test_load_document_rejects_missing_file():
    with pytest.raises(JsonResumeImportError, match="Could not read"):
        load_document("/tmp/does-not-exist-json-resume.json")


def test_load_document_rejects_directory(tmp_path):
    with pytest.raises(JsonResumeImportError, match="Could not read"):
        load_document(tmp_path)


def test_load_document_rejects_unreadable_file(tmp_path):
    path = tmp_path / "unreadable.json"
    path.write_text("{}", encoding="utf-8")
    path.chmod(0)
    try:
        with pytest.raises(JsonResumeImportError, match="Could not read"):
            load_document(path)
    finally:
        path.chmod(0o600)


def test_load_document_rejects_oversize_file(tmp_path):
    path = tmp_path / "oversize.json"
    path.write_text(" " * (MAX_INPUT_BYTES + 1), encoding="utf-8")
    with pytest.raises(JsonResumeImportError, match="Input exceeds maximum size"):
        load_document(path)


def test_load_document_rejects_invalid_json(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text('{"basics": ', encoding="utf-8")
    with pytest.raises(JsonResumeImportError, match="Invalid JSON"):
        load_document(path)
