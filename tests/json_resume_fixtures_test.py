"""Round trips of invented, editor- and registry-shaped JSON Resume fixtures.

Every fixture in ``tests/fixtures/jsonresume/`` is synthetic: names, employers,
URLs (reserved ``.example`` domains) and texts are made up. Never add real
résumé data here.
"""

import json
from pathlib import Path

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from django_resume.formats.json_resume.export import export_resume, portable_document
from django_resume.formats.json_resume.importer import (
    import_resume_document,
    load_document_bytes,
    prepare_resume_import,
)
from django_resume.formats.json_resume.validation import validate_document
from django_resume.models import Resume
from django_resume.plugins.identity import IdentityJsonResumeAdapter
from django_resume.plugins.languages import LanguagesJsonResumeAdapter

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "jsonresume"
FIXTURE_NAMES = sorted(path.stem for path in FIXTURE_DIR.glob("*.json"))
# The envelope fixture re-exports exactly only when its envelope is restored;
# its own tests below cover both modes.
PORTABLE_FIXTURES = [name for name in FIXTURE_NAMES if name != "extensions_envelope"]


def fixture_bytes(name: str) -> bytes:
    return (FIXTURE_DIR / f"{name}.json").read_bytes()


def load_fixture(name: str) -> dict:
    return load_document_bytes(fixture_bytes(name), source=name)


def slug_for(name: str, suffix: str = "") -> str:
    return name.replace("_", "-") + suffix


def import_fixture(name: str, user, *, restore: bool = False, suffix: str = ""):
    result = import_resume_document(
        load_fixture(name),
        owner=user,
        slug=slug_for(name, suffix),
        restore_django_resume_data=restore,
    )
    assert result.report.valid, result.report.validation_errors
    assert result.resume is not None
    return result


def import_fixture_document(document: dict, user, slug: str):
    result = import_resume_document(
        document, owner=user, slug=slug, restore_django_resume_data=False
    )
    assert result.resume is not None, result.report.validation_errors
    return result


def projected_export(resume: Resume):
    """Export through the plugin adapters, bypassing the stored source document."""
    resume.integration_data["json_resume"].pop("source_document", None)
    resume.save()
    exported = export_resume(resume)
    assert exported.report.valid, exported.report.validation_errors
    return exported


def notes_of(report) -> str:
    return "\n".join(report.notes)


def test_fixture_set_is_present():
    assert FIXTURE_NAMES == [
        "extensions_envelope",
        "highlights_heavy",
        "skills_variants",
        "sparse_editor",
        "unicode_international",
    ]


@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_fixture_is_schema_valid(name):
    assert validate_document(load_fixture(name)) == []


@pytest.mark.django_db
@pytest.mark.parametrize("name", PORTABLE_FIXTURES)
@pytest.mark.parametrize("restore", [False, True])
def test_unchanged_import_reexports_source_document_exactly(user, name, restore):
    user.save()
    result = import_fixture(name, user, restore=restore)

    exported = export_resume(result.resume)

    assert exported.report.valid, exported.report.validation_errors
    assert exported.document == load_fixture(name)
    assert "re-exported unchanged source JSON Resume document" in notes_of(
        exported.report
    )


@pytest.mark.django_db
@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_adapter_projection_is_schema_valid_and_a_portable_fixpoint(user, name):
    user.save()
    first = import_fixture(name, user)
    stored_projection = first.resume.integration_data["json_resume"][
        "source_adapter_document"
    ]
    assert validate_document(stored_projection) == []

    exported = projected_export(first.resume)
    assert portable_document(exported.document) == stored_projection

    second = import_fixture_document(
        portable_document(exported.document), user, slug_for(name, "-again")
    )
    assert second.resume.plugin_data == first.resume.plugin_data


@pytest.mark.django_db
@pytest.mark.parametrize("name", FIXTURE_NAMES)
@pytest.mark.parametrize("restore", [False, True])
def test_envelope_export_restores_plugin_data_and_reexports_identically(
    user, name, restore
):
    user.save()
    first = import_fixture(name, user, restore=restore)
    exported = projected_export(first.resume)

    restored = import_resume_document(
        exported.document, owner=user, slug=slug_for(name, "-restored")
    )

    assert restored.resume is not None
    assert restored.resume.plugin_data == first.resume.plugin_data
    assert export_resume(restored.resume).document == exported.document


@pytest.mark.django_db
def test_sparse_editor_document_reports_empty_sections_as_unmapped(user):
    prepared = prepare_resume_import(
        load_fixture("sparse_editor"),
        slug="sparse-editor",
        restore_django_resume_data=False,
    )

    assert prepared.plan is not None
    report = prepared.report
    assert report.mapped_plugins == ["employed_timeline", "identity"]
    for plugin_name in ("about", "awards", "education", "languages", "projects"):
        assert report.omitted_plugins[plugin_name] == "adapter produced no plugin data"
    assert prepared.plan.unmapped_sections == [
        "awards",
        "certificates",
        "education",
        "interests",
        "languages",
        "projects",
        "publications",
        "references",
        "skills",
        "volunteer",
    ]
    identity = prepared.plan.plugin_data["identity"]
    assert identity["name"] == "Pat Placeholder"
    assert identity["tagline"] == identity["location_name"] == ""
    [work] = prepared.plan.plugin_data["employed_timeline"]["items"]
    assert (work["company_name"], work["start"], work["end"]) == (
        "Nowhere Widgets",
        "2021",
        "",
    )


@pytest.mark.django_db
def test_highlights_heavy_document_maps_bullets_dates_and_long_text(user):
    user.save()
    document = load_fixture("highlights_heavy")
    result = import_fixture("highlights_heavy", user)
    plugin_data = result.resume.plugin_data

    assert plugin_data["about"]["text"] == document["basics"]["summary"]
    assert len(plugin_data["about"]["text"]) > 2000
    current, previous, leap_day = plugin_data["employed_timeline"]["items"]
    assert current["description"] == (
        "Owns the invented routing platform.\n\n"
        "- Cut fictional p99 latency by 40%\n"
        "- Line one of a highlight that an editor wrapped onto line two\n"
        "- Migrated 3 made-up services to a queue\n"
        "- Ran an invented on-call rotation for 12 people"
    )
    assert (current["start"], current["end"]) == ("2022-03", "")
    assert previous["description"] == "- Shipped the pretend MVP"
    assert (previous["start"], previous["end"]) == ("2018", "2022-02-28")
    assert (leap_day["start"], leap_day["end"]) == ("2016-02-29", "2016-08")
    assert leap_day["description"] == ""
    assert plugin_data["identity"]["github"] == "https://github.example/robin-example"

    prepared = prepare_resume_import(
        document, slug="highlights-plan", restore_django_resume_data=False
    )
    assert prepared.plan is not None
    assert prepared.plan.unmapped_sections == ["volunteer"]

    projection = projected_export(result.resume).document
    assert [entry.get("endDate") for entry in projection["work"]] == [
        None,
        "2022-02-28",
        "2016-08",
    ]
    # Item-level project fields without a django-resume field are dropped
    # without a note; see "Remaining Work" in docs/dev/jsonresume.txt.
    assert projection["projects"] == [
        {
            "name": "toy-router",
            "url": "https://toy.example",
            "description": "A routing toy.",
            "keywords": ["Rust", "graphs"],
        }
    ]


@pytest.mark.django_db
def test_skills_variants_document_flattens_keywords_and_reports_lossy_fields(user):
    user.save()
    result = import_fixture("skills_variants", user)
    plugin_data = result.resume.plugin_data

    # Keywords win over category names, empty keywords are skipped, a category
    # with an empty keyword list falls back to its name, and nameless entries
    # without keywords are dropped. Duplicates across categories are kept.
    assert plugin_data["skills"]["badges"] == [
        "Python",
        "Django",
        "PostgreSQL",
        "Frontend",
        "Testing",
        "Docker",
        "Kubernetes",
        "Docker",
        "Terraform",
    ]
    assert [item["name"] for item in plugin_data["languages"]["items"]] == [
        "English",
        "Esperanto",
    ]
    assert [item["note"] for item in plugin_data["languages"]["items"]] == [
        "Native speaker",
        "",
    ]
    notes = notes_of(result.report)
    assert "skills entry 'Backend' level is not imported" in notes
    assert "skills entry 'Backend' category name is not imported" in notes
    assert "skills entry 'Testing' level is not imported" in notes
    assert "skills entry '(unnamed skill)' level is not imported" in notes
    assert "languages entry without a language name is not imported" in notes
    assert "languages levels defaulted to 80" in notes

    projection = projected_export(result.resume).document
    assert projection["languages"] == [
        {"language": "English", "fluency": "Native speaker"},
        {"language": "Esperanto"},
    ]
    assert "interests" not in projection


@pytest.mark.django_db
def test_unicode_document_keeps_text_exact_and_maps_profiles_and_location(client, user):
    user.save()
    document = load_fixture("unicode_international")
    result = import_fixture("unicode_international", user)
    plugin_data = result.resume.plugin_data
    identity = plugin_data["identity"]

    assert result.resume.name == "Zoë Ångström-Øyelaran 李小龍"
    assert identity["name"] == document["basics"]["name"]
    assert identity["tagline"] == "Ingeniérie · Δεδομένα · データ"
    # Combining marks are stored as given, not NFC-normalized.
    assert plugin_data["about"]["text"] == document["basics"]["summary"]
    assert "é" in plugin_data["about"]["text"]
    assert identity["github"] == "https://github.example/zoe"
    assert identity["linkedin"] == "https://linkedin.example/in/zoe"
    assert identity["mastodon"] == "https://social.example/@zoe"
    assert identity["location_name"] == "Zürich, ZH, CH"
    assert [item["degree"] for item in plugin_data["education"]["items"]] == [
        "M.Sc., Informatik",
        "数学",
    ]
    assert plugin_data["awards"]["items"][0]["project"] == "Für «grüne» Software"
    notes = notes_of(result.report)
    assert "basics.profiles entry 'Xing' is not imported" in notes
    assert (
        "basics.location city, region, countryCode combined into "
        "identity.location_name" in notes
    )
    assert "awards entry 'Preis für Ökologie' awarder is not imported" in notes
    assert "education entry '東京例大学' area was merged into the degree" in notes

    client.force_login(user)
    page = client.get(
        reverse("django_resume:cv", kwargs={"slug": "unicode-international"})
    )
    assert page.status_code == 200
    content = page.content.decode("utf-8")
    assert "Société Générale d’Exemple" in content
    assert "日本語" in content
    response = client.get(
        reverse("django_resume:json-resume", kwargs={"slug": "unicode-international"})
    )
    assert json.loads(response.content.decode("utf-8")) == document

    projection = projected_export(result.resume).document
    assert projection["basics"]["location"] == {"address": "Zürich, ZH, CH"}
    assert projection["basics"]["profiles"] == [
        {"network": "GitHub", "url": "https://github.example/zoe"},
        {"network": "LinkedIn", "url": "https://linkedin.example/in/zoe"},
        {"network": "Mastodon", "url": "https://social.example/@zoe"},
    ]


@pytest.mark.django_db
def test_extensions_envelope_restores_plugin_data_and_preserved_extensions(user):
    user.save()
    document = load_fixture("extensions_envelope")
    envelope = document["meta"]["django_resume"]
    result = import_fixture("extensions_envelope", user, restore=True)

    assert result.resume.plugin_data == envelope["plugin_data"]
    assert result.report.restored_plugins == [
        "about",
        "custom_widget",
        "identity",
        "skills",
    ]
    assert result.report.mapped_plugins == []
    exported = export_resume(result.resume)
    assert exported.document == document

    projection = projected_export(result.resume).document
    assert projection["meta"]["django_resume"]["plugin_data"] == envelope["plugin_data"]
    assert (
        projection["meta"]["django_resume"]["preserved_extensions"]
        == envelope["preserved_extensions"]
    )
    assert projection["basics"]["summary"] == envelope["plugin_data"]["about"]["text"]
    # Third-party meta keys and item-level x- fields are not re-exported.
    assert set(projection["meta"]) == {"django_resume"}
    assert "x-pronunciation" not in projection["basics"]
    notes = notes_of(projected_export(result.resume).report)
    assert "identity.pronouns has no JSON Resume mapping; not exported" in notes


@pytest.mark.django_db
def test_extensions_envelope_portable_import_ignores_plugin_data(user):
    user.save()
    result = import_fixture("extensions_envelope", user, restore=False)
    plugin_data = result.resume.plugin_data

    assert "custom_widget" not in plugin_data
    assert plugin_data["about"]["text"] == "Envelope fixture."
    assert plugin_data["skills"]["badges"] == ["Plugins"]
    [work] = plugin_data["employed_timeline"]["items"]
    assert "x-team-size" not in work
    assert work["id"] == "json-resume-work-1"
    notes = notes_of(result.report)
    assert "meta.django_resume.plugin_data was ignored" in notes
    assert "stored meta.django_resume.preserved_extensions" in notes

    exported = export_resume(result.resume)
    assert exported.document != load_fixture("extensions_envelope")
    assert exported.document["meta"]["django_resume"]["plugin_data"] == plugin_data
    assert exported.document["meta"]["django_resume"]["preserved_extensions"] == [
        {
            "source_path": "/basics/x-pronunciation",
            "payload": "kwin",
            "origin": "third-party",
        }
    ]


@pytest.mark.django_db
@pytest.mark.parametrize("name", FIXTURE_NAMES)
def test_browser_preview_and_confirm_creates_fixture_resume(client, user, name):
    user.save()
    client.force_login(user)
    data = fixture_bytes(name)
    url = reverse("django_resume:json-resume-import")
    slug = slug_for(name, "-browser")

    preview = client.post(
        url,
        {
            "file": SimpleUploadedFile(f"{name}.json", data, "application/json"),
            "action": "preview",
            "slug": slug,
        },
    )
    assert "import_preview" in preview.context, preview.context["import_form"].errors
    created = client.post(
        url,
        {
            "file": SimpleUploadedFile(f"{name}.json", data, "application/json"),
            "action": "create",
            "slug": slug,
            "confirmation": preview.context["import_preview"]["confirmation"],
        },
    )

    assert created.status_code == 200
    resume = Resume.objects.get(slug=slug)
    expected = prepare_resume_import(load_fixture(name), slug=slug, owner=user)
    assert expected.plan is not None
    assert resume.plugin_data == expected.plan.plugin_data


@pytest.mark.django_db
def test_editor_empty_end_date_is_rejected_by_the_pinned_schema(user):
    """Some editors write ``"endDate": ""`` for current positions.

    The pinned schema's date pattern rejects the empty string, so the import is
    refused as a whole; see "Remaining Work" in docs/dev/jsonresume.txt.
    """
    user.save()
    document = load_fixture("sparse_editor")
    document["work"][0]["endDate"] = ""

    result = import_resume_document(document, owner=user, slug="empty-end-date")

    assert result.resume is None
    assert any("work/0/endDate" in error for error in result.report.validation_errors)


def test_identity_location_address_wins_over_other_location_fields():
    result = IdentityJsonResumeAdapter().import_data(
        {
            "basics": {
                "location": {
                    "address": "Beispielweg 1\nHinterhaus",
                    "postalCode": "00000",
                    "city": "Musterstadt",
                    "countryCode": "",
                }
            }
        }
    )

    assert result.plugin_data["location_name"] == "Beispielweg 1\nHinterhaus"
    assert result.notes == [
        "basics.location city, postalCode not imported by the identity plugin"
    ]


def test_identity_location_ignores_blank_or_non_object_values():
    adapter = IdentityJsonResumeAdapter()

    blank = adapter.import_data({"basics": {"location": {"address": "  "}}})
    assert blank.plugin_data["location_name"] == ""
    assert blank.notes == []
    invalid = adapter.import_data({"basics": {"location": "Somewhere"}})
    assert invalid.plugin_data["location_name"] == ""
    assert invalid.notes == ["basics.location is not an object; not imported"]


def test_languages_import_reports_only_nameless_entries():
    result = LanguagesJsonResumeAdapter().import_data(
        {"languages": [{"fluency": "Some"}, {"language": " "}]}
    )

    assert result.plugin_data == {}
    assert result.notes == [
        "languages entry without a language name is not imported",
        "languages entry without a language name is not imported",
    ]
