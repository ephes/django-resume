from dataclasses import dataclass
from copy import deepcopy

from ...interchange.coordinator import build_document, collect_adapters
from ...interchange.report import ExportReport
from ...models import Resume
from ...plugins import plugin_registry
from .validation import validate_document

FORMAT_ID = "json_resume"
DJANGO_RESUME_META_VERSION = 1


@dataclass
class JsonResumeExport:
    document: dict
    report: ExportReport


def _source_document_for_unchanged_import(
    resume: Resume, document: dict
) -> dict | None:
    integration_data = resume.integration_data
    if not isinstance(integration_data, dict):
        return None
    json_resume_state = integration_data.get("json_resume", {})
    if not isinstance(json_resume_state, dict):
        return None
    source_document = json_resume_state.get("source_document")
    source_adapter_document = json_resume_state.get("source_adapter_document")
    source_plugin_data = json_resume_state.get("source_plugin_data")
    if not isinstance(source_document, dict) or not isinstance(
        source_adapter_document, dict
    ):
        return None
    if document != source_adapter_document:
        return None
    if (
        not isinstance(source_plugin_data, dict)
        or resume.plugin_data != source_plugin_data
    ):
        return None
    return deepcopy(source_document)


def export_resume(resume: Resume, *, registry=None) -> JsonResumeExport:
    """Assemble, validate, and report a JSON Resume document for ``resume``.

    Raises ``PathConflictError`` (from the coordinator) on adapter
    misconfiguration; callers decide how to surface that.
    """
    registry = registry or plugin_registry
    plugins = registry.get_all_plugins()
    resolved, omitted = collect_adapters(plugins, resume, FORMAT_ID)
    document, notes = build_document(resolved)
    source_document = _source_document_for_unchanged_import(resume, document)
    if source_document is not None:
        document = source_document
        notes.append(
            "re-exported unchanged source JSON Resume document because plugin data "
            "is unchanged"
        )
    else:
        django_resume_meta = {
            "version": DJANGO_RESUME_META_VERSION,
            "plugin_data": deepcopy(resume.plugin_data),
        }
        integration_data = resume.integration_data
        if not isinstance(integration_data, dict):
            integration_data = {}
        json_resume_state = integration_data.get("json_resume", {})
        if not isinstance(json_resume_state, dict):
            json_resume_state = {}
        preserved_extensions = json_resume_state.get("preserved_extensions")
        if isinstance(preserved_extensions, list):
            django_resume_meta["preserved_extensions"] = deepcopy(preserved_extensions)
        document.setdefault("meta", {})["django_resume"] = django_resume_meta
    errors = validate_document(document)
    report = ExportReport(
        mapped_plugins=sorted(item.plugin_name for item in resolved),
        omitted_plugins=dict(sorted(omitted.items())),
        notes=notes,
        valid=not errors,
        validation_errors=errors,
    )
    return JsonResumeExport(document=document, report=report)
