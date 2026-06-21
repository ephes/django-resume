from dataclasses import dataclass

from ...interchange.coordinator import build_document, collect_adapters
from ...interchange.report import ExportReport
from ...models import Resume
from ...plugins import plugin_registry
from .validation import validate_document

FORMAT_ID = "json_resume"


@dataclass
class JsonResumeExport:
    document: dict
    report: ExportReport


def export_resume(resume: Resume, *, registry=None) -> JsonResumeExport:
    """Assemble, validate, and report a JSON Resume document for ``resume``.

    Raises ``PathConflictError`` (from the coordinator) on adapter
    misconfiguration; callers decide how to surface that.
    """
    registry = registry or plugin_registry
    plugins = registry.get_all_plugins()
    resolved, omitted = collect_adapters(plugins, resume, FORMAT_ID)
    document, notes = build_document(resolved)
    errors = validate_document(document)
    report = ExportReport(
        mapped_plugins=sorted(item.plugin_name for item in resolved),
        omitted_plugins=dict(sorted(omitted.items())),
        notes=notes,
        valid=not errors,
        validation_errors=errors,
    )
    return JsonResumeExport(document=document, report=report)
