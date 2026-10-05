"""Focused checks for the synthetic import-preview prototype.

Run explicitly (the repository ``testpaths`` only collects ``tests/``)::

    uv run pytest experiments/2026-10-04-import-preview/test_preview.py

The generator runs in fresh subprocesses with its own dummy-database settings.
The parity test runs the real create importer against pytest-django's
throwaway test database to prove the preview reports match production.
"""

import hashlib
import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))

from generate import CALLER, MODES, load_fixtures  # noqa: E402


def run_isolated(code, *args):
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code), *map(str, args)],
        cwd=HERE,
        check=True,
        capture_output=True,
        text=True,
    )


def source_hashes():
    return {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted((ROOT / "src").rglob("*"))
        if path.is_file() and "__pycache__" not in path.parts
    }


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    output = tmp_path_factory.mktemp("preview") / "review"
    before = source_hashes()
    run_isolated(
        "import sys; from generate import generate; generate(sys.argv[1])", output
    )
    assert source_hashes() == before
    return output


@pytest.fixture(scope="module")
def data(generated):
    return json.loads((generated / "reports.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def page(generated):
    return (generated / "preview.html").read_text(encoding="utf-8")


def test_lossy_portable_report_uses_actual_adapter_notes(data):
    for mode in MODES:
        lossy = data["lossy"][mode]
        report = lossy["report"]
        assert report["valid"]
        assert report["mapped_plugins"] == ["identity", "skills"]
        assert not report["restored_plugins"]
        assert lossy["plugin_data"]["skills"]["badges"] == ["Testing", "Documentation"]
        assert lossy["mapping_notes"] == [
            "skills entry 'Engineering category' level is not imported",
            "skills entry 'Engineering category' category name is not imported",
            "basics.profiles entry 'Example Network' is not imported",
            "basics.image cannot be imported into local avatar storage",
            "basics.location is not imported by the identity plugin",
        ]
        assert lossy["unmapped_sections"] == ["interests"]
        assert "re-exports it exactly" in lossy["source_retention"]


def test_envelope_restore_and_portable_modes_differ(data):
    restored = data["envelope"]["restore"]
    portable = data["envelope"]["portable"]
    assert restored["report"]["restored_plugins"] == ["identity", "skills"]
    assert not restored["report"]["mapped_plugins"]
    assert restored["plugin_data"]["identity"]["pronouns"] == "they/them"
    assert restored["ignored_portable_sections"] == ["basics", "skills"]
    assert "re-exports it exactly" in restored["source_retention"]
    assert portable["report"]["mapped_plugins"] == ["identity", "skills"]
    assert not portable["report"]["restored_plugins"]
    assert portable["plugin_data"]["identity"]["name"] == "Portable Alex"
    assert "not keep this source" in portable["source_retention"]
    for result in (restored, portable):
        assert (
            "stored meta.django_resume.preserved_extensions"
            in result["report"]["notes"]
        )


def test_invalid_inputs_produce_no_creation_payload(data):
    for mode in MODES:
        invalid = data["invalid"][mode]
        assert not invalid["report"]["valid"]
        assert invalid["report"]["validation_errors"]
        assert invalid["plugin_data"] is None
    bad_envelope = data["invalid-envelope"]
    assert not bad_envelope["restore"]["report"]["valid"]
    assert bad_envelope["restore"]["plugin_data"] is None
    assert bad_envelope["restore"]["report"]["validation_errors"] == [
        "meta.django_resume.plugin_data.skills.items must be a list"
    ]
    assert bad_envelope["portable"]["report"]["valid"]


@pytest.mark.django_db
def test_preview_matches_production_create_import(data, django_user_model):
    from django_resume.formats.json_resume.importer import import_resume_document

    owner = django_user_model.objects.create(username="synthetic-preview-owner")
    for fixture, document in load_fixtures().items():
        for mode in MODES:
            expected = data[fixture][mode]
            result = import_resume_document(
                json.loads(json.dumps(document)),
                owner=owner,
                slug=CALLER["slug"],
                name=CALLER["name"],
                restore_django_resume_data=mode == "restore",
            )
            actual = result.report.__dict__
            assert actual == expected["report"], (fixture, mode)
            if result.resume is None:
                assert expected["plugin_data"] is None
            else:
                assert result.resume.plugin_data == expected["plugin_data"]
                assert result.resume.name == expected["name"]
                result.resume.delete()


def test_page_is_escaped_static_and_cannot_create(page):
    assert "Alex Example &lt;synthetic&gt;" in page
    assert "<synthetic>" not in page
    assert "slug availability is unknown" in page
    assert '<button type="button" disabled' in page
    for forbidden in (
        "<form",
        'type="file"',
        "fetch(",
        "XMLHttpRequest",
        "<script src",
        "<link",
        "http://",
        "https://",
        "/Users/",
        "/private/",
        "/tmp/",
    ):
        assert forbidden not in page, forbidden
    assert page.count("<article") == len(load_fixtures()) * len(MODES)
    assert 'aria-live="polite"' in page and 'name="viewport"' in page


def test_existing_output_is_not_overwritten(generated, page):
    result = subprocess.run(
        [sys.executable, str(HERE / "generate.py"), "--output", str(generated)],
        capture_output=True,
    )
    assert result.returncode != 0
    assert (generated / "preview.html").read_text(encoding="utf-8") == page


def test_parser_errors_and_forbidden_side_effect_seams():
    run_isolated(
        """
        import http.client, os, socket, subprocess, urllib.request
        from generate import FORBIDDEN_MESSAGE, isolated_runtime, preview

        with isolated_runtime() as (importer, registry):
            from django.db import connection, transaction
            from django_resume.models import Resume

            for raw in [b'{"basics":{},"basics":{}}', b'{"basics":{"name":NaN}}',
                        b'\\xff', b'{', b'[]']:
                result = preview(raw, True, importer, registry)
                assert not result["report"]["valid"], raw
                assert result["plugin_data"] is None, raw
            calls = {
                "cursor": lambda: connection.cursor(),
                "ensure_connection": lambda: connection.ensure_connection(),
                "create": lambda: Resume.objects.create(name="n", slug="s"),
                "save": lambda: Resume(name="n", slug="s").save(),
                "exists": lambda: Resume.objects.filter(slug="s").exists(),
                "fetch": lambda: list(Resume.objects.all()),
                "atomic": lambda: transaction.atomic().__enter__(),
                "socket": lambda: socket.create_connection(("example.invalid", 80)),
                "dns": lambda: socket.getaddrinfo("example.invalid", 80),
                "http": lambda: http.client.HTTPConnection("example.invalid").connect(),
                "urlopen": lambda: urllib.request.urlopen("https://example.invalid"),
                "popen": lambda: subprocess.Popen(["never-run"]),
                "system": lambda: os.system("never-run"),
                "url_loader": lambda: importer.load_document_url("https://x.invalid"),
                "file_loader": lambda: importer.load_document("never.json"),
                "import": lambda: importer.import_resume_document(
                    {}, owner=None, slug="synthetic"
                ),
                "import_file": lambda: importer.import_resume_file(
                    "never.json", owner=None, slug="synthetic"
                ),
                "owner": lambda: importer.get_owner("synthetic"),
            }
            for name, call in calls.items():
                try:
                    call()
                except RuntimeError as error:
                    assert str(error) == FORBIDDEN_MESSAGE, (name, error)
                else:
                    raise AssertionError(f"{name} side effect escaped")
        """
    )


def test_refuses_preconfigured_settings():
    run_isolated(
        """
        from django.conf import settings
        from generate import isolated_runtime

        settings.configure()
        try:
            with isolated_runtime():
                pass
        except RuntimeError as error:
            assert "fresh isolated" in str(error)
        else:
            raise AssertionError("borrowed existing settings")
        """
    )
