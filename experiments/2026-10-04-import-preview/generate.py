"""Synthetic create-import preview built from the current JSON Resume importer.

Read-only prototype: it reuses the production byte parser, pinned schema
validator and pure plugin-mapping/report helpers, then writes a static HTML
page and a JSON report for fixed invented fixtures. It has no creation path.
"""

import argparse
import html
import json
import os
import shutil
from contextlib import ExitStack, contextmanager
from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures.json"
CALLER = {
    "slug": "synthetic-alex-preview",
    "name": "Synthetic preview resume",
    "owner": "synthetic-owner (simulated, not authenticated)",
}
MODES = {
    "restore": "Restore envelope (default)",
    "portable": "Portable only",
}
FIXTURE_LABELS = {
    "lossy": "Lossy portable document",
    "envelope": "Private envelope document",
    "invalid": "Invalid document",
    "invalid-envelope": "Malformed envelope document",
}
FORBIDDEN_MESSAGE = "Forbidden preview side effect"
# Exact strings the production create path appends after mapping. Kept here only
# to label them as source-retention notes; tests check them against production.
STORED_SOURCE_NOTE = (
    "stored source JSON Resume document for exact re-export while mapped "
    "projection and plugin data remain unchanged"
)
IGNORED_SOURCE_NOTE = (
    "did not store source JSON Resume document for exact re-export because "
    "meta.django_resume.plugin_data was ignored"
)
PRESERVED_EXTENSIONS_NOTE = "stored meta.django_resume.preserved_extensions"


def forbidden(*args, **kwargs):
    raise RuntimeError(FORBIDDEN_MESSAGE)


def _network_and_process_targets():
    targets = [
        "socket.create_connection",
        "socket.socket.connect",
        "socket.socket.connect_ex",
        "socket.getaddrinfo",
        "urllib.request.urlopen",
        "http.client.HTTPConnection.connect",
        "subprocess.Popen",
        "os.system",
    ]
    for name in ("execv", "execve", "posix_spawn", "posix_spawnp", "startfile"):
        if hasattr(os, name):
            targets.append(f"os.{name}")
    return targets


@contextmanager
def isolated_runtime():
    """Configure throwaway settings and make side-effect seams raise.

    Must run in a fresh interpreter: it never borrows a project's settings or
    database. The dummy database engine plus patched connection, cursor, ORM
    read/write and transaction seams make any database access fail loudly.
    """
    from django.conf import settings

    if settings.configured:
        raise RuntimeError("Run the preview in a fresh isolated Python process")
    settings.configure(
        SECRET_KEY="synthetic-preview-only",
        USE_TZ=True,
        INSTALLED_APPS=[
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django_resume",
        ],
        DATABASES={"default": {"ENGINE": "django.db.backends.dummy"}},
        ROOT_URLCONF="django_resume.urls",
        STATIC_URL="/static/",
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "APP_DIRS": True,
            }
        ],
    )
    import django

    with ExitStack() as stack:
        for target in _network_and_process_targets():
            stack.enter_context(patch(target, forbidden))
        django.setup()
        from django.db import models, transaction
        from django.db.backends.base.base import BaseDatabaseWrapper
        from django.db.backends.dummy.base import DatabaseWrapper as DummyWrapper
        from django.db.backends.utils import CursorWrapper

        from django_resume.formats.json_resume import importer
        from django_resume.plugins import plugin_registry

        seams = [
            (BaseDatabaseWrapper, "connect"),
            (BaseDatabaseWrapper, "ensure_connection"),
            (BaseDatabaseWrapper, "cursor"),
            (DummyWrapper, "ensure_connection"),
            (DummyWrapper, "_cursor"),
            (CursorWrapper, "execute"),
            (CursorWrapper, "executemany"),
            (models.Model, "save"),
            (models.Model, "delete"),
            (models.QuerySet, "create"),
            (models.QuerySet, "bulk_create"),
            (models.QuerySet, "update"),
            (models.QuerySet, "delete"),
            (models.QuerySet, "exists"),
            (models.QuerySet, "_fetch_all"),
            (transaction.Atomic, "__enter__"),
            (importer, "import_resume_document"),
            (importer, "import_resume_file"),
            (importer, "load_document_url"),
            (importer, "load_document"),
            (importer, "get_owner"),
        ]
        for owner, name in seams:
            stack.enter_context(patch.object(owner, name, forbidden))
        yield importer, plugin_registry


def _adapter_source_roots(importer, registry):
    roots = set()
    for plugin in registry.get_all_plugins():
        get_adapters = getattr(plugin, "get_import_adapters", None)
        adapters = get_adapters() if callable(get_adapters) else {}
        adapter = adapters.get(importer.FORMAT_ID)
        if adapter is not None:
            roots.update(path.split("/")[1] for path in adapter.source_paths)
    return roots


def _invalid(result, errors):
    from django_resume.interchange.report import ImportReport

    result["report"] = asdict(ImportReport(valid=False, validation_errors=errors))
    result["source_retention"] = (
        "Not applicable: invalid input produces no creation payload."
    )
    return result


def preview(raw, restore, importer, registry):
    """Return the pre-create summary production create would report.

    Follows the order of ``importer.import_resume_document`` but stops before
    the slug-existence query and ``Resume.objects.create``. Owner and slug are
    simulated, so slug availability is reported as unknown.
    """
    from django_resume.interchange.pointer import get_pointer

    mode = "restore" if restore else "portable"
    result = {
        "caller": dict(CALLER),
        "mode": mode,
        "mode_label": MODES[mode],
        "name": None,
        "plugin_data": None,
        "mapping": None,
        "mapping_notes": [],
        "retention_notes": [],
        "unmapped_sections": [],
        "ignored_portable_sections": [],
        "slug_availability": "unknown (prototype does not query any database)",
        "creation": "unavailable in this prototype",
    }
    try:
        document = importer.load_document_bytes(raw, source="synthetic fixture")
    except importer.JsonResumeImportError as error:
        return _invalid(result, [str(error)])
    errors = importer.validate_document(document)
    if errors:
        return _invalid(result, errors)
    meta = get_pointer(document, "/meta/django_resume", None)
    if meta is None:
        meta = {}
    elif not isinstance(meta, dict):
        return _invalid(result, ["meta.django_resume must be an object"])
    if restore and "plugin_data" in meta:
        envelope_errors = importer._validate_restored_plugin_data(meta["plugin_data"])
        if envelope_errors:
            return _invalid(result, envelope_errors)
        plugin_data = deepcopy(meta["plugin_data"])
        report = importer._report_restored_plugin_data(plugin_data)
        report.notes.append("restored plugin data from meta.django_resume.plugin_data")
        result["mapping"] = (
            "The private envelope replaces portable adapter mapping. This is unsigned "
            "structural restoration, not verified identity or approval."
        )
        result["ignored_portable_sections"] = sorted(
            set(document) - {"meta", "$schema"}
        )
    else:
        plugin_data, report = importer._collect_adapter_plugin_data(document, registry)
        result["mapping"] = (
            "Portable fields map through the existing plugin import adapters. "
            "Fields named in the warnings are not available for plugin editing."
        )
        roots = _adapter_source_roots(importer, registry)
        result["unmapped_sections"] = sorted(
            set(document) - roots - {"meta", "$schema"}
        )
    result["mapping_notes"] = list(report.notes)
    resume_name = (
        CALLER["name"] or get_pointer(document, "/basics/name", "") or CALLER["slug"]
    )
    importer._validate_resume_metadata(slug=CALLER["slug"], name=resume_name)
    retention_notes = []
    keeps_source = restore or "plugin_data" not in meta
    if not keeps_source:
        retention_notes.append(IGNORED_SOURCE_NOTE)
    # Production helper: builds the export projection on an unsaved model only.
    projection, projection_notes = importer._build_source_adapter_document(
        plugin_data=plugin_data,
        owner=None,
        slug=CALLER["slug"],
        name=resume_name,
        registry=registry,
    )
    retention_notes.extend(projection_notes)
    if projection is not None and keeps_source:
        retention_notes.append(STORED_SOURCE_NOTE)
    if isinstance(meta.get("preserved_extensions"), list):
        retention_notes.append(PRESERVED_EXTENSIONS_NOTE)
    report.notes.extend(retention_notes)
    if keeps_source and projection is not None:
        retention = (
            "Production create would keep the parsed source document so an unchanged "
            "resume re-exports it exactly. This does not undo plugin-level loss: "
            "only the mapped fields above are editable."
        )
    elif keeps_source:
        retention = (
            "Production create would keep the parsed source, but exact unchanged "
            "re-export is unavailable because export adapters conflict."
        )
    else:
        retention = (
            "Portable-only mode ignores the private plugin_data, so production would "
            "not keep this source for exact re-export."
        )
    result.update(
        name=resume_name,
        plugin_data=plugin_data,
        retention_notes=retention_notes,
        source_retention=retention,
        report=asdict(report),
    )
    return result


def load_fixtures():
    return json.loads(FIXTURES.read_text(encoding="utf-8"))


def reports(importer, registry):
    return {
        name: {
            mode: preview(
                json.dumps(document).encode(), mode == "restore", importer, registry
            )
            for mode in MODES
        }
        for name, document in load_fixtures().items()
    }


def _e(value):
    return html.escape(str(value), quote=True)


def _list(values, empty="None."):
    values = list(values)
    if not values:
        return f'<p class="muted">{_e(empty)}</p>'
    return "<ul>" + "".join(f"<li>{_e(v)}</li>" for v in values) + "</ul>"


def _outline(plugin_data):
    items = []
    for plugin, payload in sorted(plugin_data.items()):
        filled = []
        if isinstance(payload, dict):
            filled = sorted(
                str(k) for k, v in payload.items() if v not in ("", None, [], {})
            )
        items.append(f"{plugin}: {', '.join(filled) if filled else 'no filled fields'}")
    return items


def _panel(fixture, mode, result):
    report = result["report"]
    valid = report["valid"]
    heading_id = f"h-{fixture}-{mode}"
    status = (
        '<p class="badge ok">Structurally valid</p>'
        if valid
        else '<p class="badge bad">Invalid input: nothing would be created</p>'
    )
    parts = [
        f'<article class="panel" data-fixture="{_e(fixture)}" data-mode="{_e(mode)}" '
        f'aria-labelledby="{_e(heading_id)}">',
        f'<h2 id="{_e(heading_id)}">{_e(FIXTURE_LABELS.get(fixture, fixture))}'
        f'<span class="sub">{_e(result["mode_label"])}</span></h2>',
        status,
        '<dl class="facts">',
        f"<dt>New resume name</dt><dd>{_e(result['name'] or CALLER['name'])}</dd>",
        f"<dt>Slug</dt><dd><code>{_e(CALLER['slug'])}</code> (availability unknown)</dd>",
        f"<dt>Source</dt><dd>Invented fixture <code>{_e(fixture)}</code></dd>",
        f"<dt>Owner</dt><dd>{_e(CALLER['owner'])}</dd>",
        "</dl>",
    ]
    if not valid:
        parts += [
            "<h3>Blocking validation errors</h3>",
            _list(report["validation_errors"]),
            '<p class="muted">No proposed creation payload is produced.</p>',
        ]
    else:
        parts += [
            f"<p>{_e(result['mapping'])}</p>",
            "<h3>Planned plugin content</h3>",
            _list(_outline(result["plugin_data"]), "No plugin data."),
            "<h3>Mapped by portable adapters</h3>",
            _list(report["mapped_plugins"]),
            "<h3>Restored from private envelope</h3>",
            _list(report["restored_plugins"]),
            "<h3>Loss from plugin mapping</h3>",
            _list(result["mapping_notes"], "No mapping notes."),
            "<h3>Source sections no adapter reads</h3>",
            _list(result["unmapped_sections"]),
        ]
        if result["ignored_portable_sections"]:
            parts += [
                "<h3>Portable sections ignored in restore mode</h3>",
                _list(result["ignored_portable_sections"]),
            ]
        parts += [
            "<h3>Source preservation for unchanged re-export</h3>",
            f"<p>{_e(result['source_retention'])}</p>",
            _list(result["retention_notes"]),
            "<details><summary>Plugins left empty and why</summary>",
            _list(f"{k}: {v}" for k, v in report["omitted_plugins"].items()),
            "</details>",
            "<details><summary>Planned plugin data (invented)</summary><pre>",
            _e(json.dumps(result["plugin_data"], indent=2, ensure_ascii=False)),
            "</pre></details>",
        ]
    parts.append("</article>")
    return "".join(parts)


STYLE = """
:root{--bg:#f4f6fa;--card:#fff;--fg:#172534;--muted:#55606e;--line:#d8dde6;
--ok:#155e2b;--okbg:#e3f4e8;--bad:#8a1c1c;--badbg:#fbe5e5;--accent:#1f4f8a}
@media (prefers-color-scheme:dark){:root{--bg:#11161d;--card:#1b222c;--fg:#e6ebf2;
--muted:#a5afbd;--line:#2f3946;--ok:#9fe0b0;--okbg:#173322;--bad:#f3b0b0;
--badbg:#3a1a1a;--accent:#8fb8f0}}
*{box-sizing:border-box}
body{margin:0 auto;max-width:760px;padding:16px;background:var(--bg);color:var(--fg);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
h1{font-size:1.5rem;margin:.5rem 0 1rem}h2{font-size:1.2rem;margin:0 0 .5rem}
h2 .sub{display:block;font-size:.9rem;font-weight:500;color:var(--muted)}
h3{font-size:1rem;margin:1.2rem 0 .3rem}
.card,.panel{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:16px;margin:16px 0}
[hidden]{display:none!important}
.controls label{display:block;font-weight:600;margin:0 0 12px}
select{display:block;width:100%;margin-top:4px;font:inherit;padding:10px;
border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}
select:focus-visible,summary:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-weight:600;margin:0}
.ok{color:var(--ok);background:var(--okbg)}.bad{color:var(--bad);background:var(--badbg)}
.facts{display:grid;grid-template-columns:max-content 1fr;gap:4px 12px;margin:12px 0}
.facts dt{color:var(--muted)}.facts dd{margin:0;overflow-wrap:anywhere}
ul{padding-left:1.2rem;margin:.3rem 0}li{margin:4px 0;overflow-wrap:anywhere}
.muted{color:var(--muted)}code{font-size:.9em;overflow-wrap:anywhere}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.85rem}
summary{cursor:pointer;margin-top:1rem;font-weight:600}
button{font:inherit;padding:12px 16px;width:100%;border-radius:8px}
@media (max-width:420px){.facts{grid-template-columns:1fr}.facts dd{margin-bottom:6px}}
"""

# Only toggles visibility of precomputed panels; it never maps or fetches data.
SCRIPT = """
(function(){
  var fixture=document.getElementById('fixture'),mode=document.getElementById('mode');
  var status=document.getElementById('status');
  function show(){
    document.querySelectorAll('article.panel').forEach(function(el){
      el.hidden=!(el.dataset.fixture===fixture.value&&el.dataset.mode===mode.value);
    });
    status.textContent='Showing '+fixture.options[fixture.selectedIndex].text+', '
      +mode.options[mode.selectedIndex].text+'. Nothing is created.';
  }
  document.querySelector('.controls').hidden=false;
  fixture.addEventListener('change',show);mode.addEventListener('change',show);show();
})();
"""


def render(data):
    fixture_options = "".join(
        f'<option value="{_e(name)}">{_e(FIXTURE_LABELS.get(name, name))}</option>'
        for name in data
    )
    mode_options = "".join(
        f'<option value="{_e(key)}">{_e(label)}</option>'
        for key, label in MODES.items()
    )
    panels = "".join(
        _panel(fixture, mode, result)
        for fixture, modes in data.items()
        for mode, result in modes.items()
    )
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>Import Preview Prototype</title>"
        f"<style>{STYLE}</style></head><body><main>"
        "<h1>Review before creating a resume</h1>"
        '<section class="card" aria-label="Prototype limits">'
        "<p><strong>Synthetic prototype. Invented fixtures only. "
        "Creation unavailable.</strong></p>"
        "<p>Reports come from the current importer's parser, pinned schema and plugin "
        "adapters. No existing resume is modified. Owner and slug are simulated; slug "
        "availability is unknown.</p>"
        "<p>Validation is structural only: email and URI formats are not checked. "
        "A restored private envelope is not identity verification, signed provenance "
        "or approval.</p></section>"
        '<section class="card controls" hidden aria-label="Choose a case">'
        '<label for="fixture">Example document'
        f'<select id="fixture">{fixture_options}</select></label>'
        f'<label for="mode">Import mode<select id="mode">{mode_options}</select></label>'
        '<p id="status" role="status" aria-live="polite"></p></section>'
        f"{panels}"
        '<button type="button" disabled aria-describedby="create-note">'
        "Create new resume</button>"
        '<p id="create-note" class="muted">Creation is not available in this '
        "prototype.</p>"
        f"</main><script>{SCRIPT}</script></body></html>\n"
    )


def generate(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    try:
        with isolated_runtime() as (importer, registry):
            data = reports(importer, registry)
        (output / "preview.html").write_text(render(data), encoding="utf-8")
        # Synthetic regression artifact: reports only, not the source documents.
        (output / "reports.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    except BaseException:
        shutil.rmtree(output)
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="New directory to create")
    generate(parser.parse_args().output)
