import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_slug
from django.db import IntegrityError, transaction

from ...interchange.coordinator import (
    PathConflictError,
    build_document,
    collect_adapters,
)
from ...interchange.conflicts import detect_path_conflicts
from ...interchange.pointer import get_pointer, has_pointer
from ...interchange.report import ImportReport
from ...models import Resume
from ...plugins import plugin_registry
from .validation import validate_document

FORMAT_ID = "json_resume"
MAX_INPUT_BYTES = 2 * 1024 * 1024


class JsonResumeImportError(ValueError):
    """Raised when a JSON Resume document cannot be imported."""


@dataclass
class JsonResumeImport:
    resume: Resume | None
    report: ImportReport


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise JsonResumeImportError(f"Duplicate JSON object key {key!r}")
        result[key] = value
    return result


def load_document(path: str | Path) -> dict:
    input_path = Path(path)
    try:
        if input_path.stat().st_size > MAX_INPUT_BYTES:
            raise JsonResumeImportError(
                f"Input exceeds maximum size of {MAX_INPUT_BYTES} bytes"
            )
        with input_path.open(encoding="utf-8") as handle:
            document = json.load(handle, object_pairs_hook=_reject_duplicate_keys)
    except OSError as exc:
        raise JsonResumeImportError(f"Could not read {input_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise JsonResumeImportError(f"Invalid JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise JsonResumeImportError("JSON Resume document must be an object")
    return document


def _validate_restored_plugin_data(plugin_data: object) -> list[str]:
    if not isinstance(plugin_data, dict):
        return ["meta.django_resume.plugin_data must be an object"]
    errors = []
    for plugin_name, payload in plugin_data.items():
        if not isinstance(plugin_name, str):
            errors.append("meta.django_resume.plugin_data keys must be strings")
        if not isinstance(payload, dict):
            errors.append(
                f"meta.django_resume.plugin_data.{plugin_name} must be an object"
            )
            continue
        if "flat" in payload and not isinstance(payload["flat"], dict):
            errors.append(
                f"meta.django_resume.plugin_data.{plugin_name}.flat must be an object"
            )
        if "items" in payload:
            if not isinstance(payload["items"], list):
                errors.append(
                    f"meta.django_resume.plugin_data.{plugin_name}.items must be a list"
                )
            elif not all(isinstance(item, dict) for item in payload["items"]):
                errors.append(
                    "meta.django_resume.plugin_data."
                    f"{plugin_name}.items must contain objects"
                )
    return errors


def _collect_adapter_plugin_data(document: dict, registry) -> tuple[dict, ImportReport]:
    plugin_data = {}
    report = ImportReport()
    adapters = []
    for plugin in registry.get_all_plugins():
        get_adapters = getattr(plugin, "get_import_adapters", None)
        adapter = get_adapters().get(FORMAT_ID) if callable(get_adapters) else None
        if adapter is None:
            report.omitted_plugins[plugin.name] = f"no {FORMAT_ID} import adapter"
            continue
        adapters.append((plugin.name, adapter))

    claims: dict[str, list[str]] = {}
    for plugin_name, adapter in adapters:
        source_paths = getattr(adapter, "source_paths", None)
        if source_paths is None:
            raise JsonResumeImportError(
                f"Import adapter for plugin {plugin_name!r} has no source_paths"
            )
        for path in source_paths:
            claims.setdefault(path, []).append(plugin_name)
    conflict = detect_path_conflicts(claims)
    if conflict is not None:
        if conflict.kind == "duplicate":
            names = ", ".join(conflict.claimers or [])
            raise JsonResumeImportError(
                f"Multiple import adapters claim source path {conflict.path!r}: {names}"
            )
        if conflict.parent is not None and conflict.child is not None:
            raise JsonResumeImportError(
                f"Overlapping import source paths {conflict.parent!r} "
                f"and {conflict.child!r}"
            )

    for plugin_name, adapter in adapters:
        if not any(has_pointer(document, path) for path in adapter.source_paths):
            report.omitted_plugins[plugin_name] = "source paths absent"
            continue
        result = adapter.import_data(document)
        report.notes.extend(result.notes)
        if result.plugin_data:
            plugin_data[plugin_name] = result.plugin_data
            report.mapped_plugins.append(plugin_name)
        else:
            report.omitted_plugins[plugin_name] = "adapter produced no plugin data"
    report.mapped_plugins.sort()
    report.omitted_plugins = dict(sorted(report.omitted_plugins.items()))
    return plugin_data, report


def _report_restored_plugin_data(plugin_data: dict) -> ImportReport:
    return ImportReport(restored_plugins=sorted(plugin_data))


def _build_source_adapter_document(
    *,
    plugin_data: dict,
    owner,
    slug: str,
    name: str,
    registry,
) -> tuple[dict | None, list[str]]:
    shadow_resume = Resume(
        name=name,
        slug=slug,
        owner=owner,
        plugin_data=deepcopy(plugin_data),
        integration_data={},
    )
    try:
        resolved, _omitted = collect_adapters(
            registry.get_all_plugins(), shadow_resume, FORMAT_ID
        )
        document, _notes = build_document(resolved)
    except PathConflictError as exc:
        return None, [
            "source JSON Resume document was not stored for exact re-export "
            f"because export adapters conflict: {exc}"
        ]
    return document, []


def _validate_resume_metadata(*, slug: str, name: str) -> None:
    slug_max_length = cast(int, Resume._meta.get_field("slug").max_length)
    if len(slug) > slug_max_length:
        raise JsonResumeImportError(
            f"Resume slug exceeds maximum length of {slug_max_length} characters"
        )
    try:
        validate_slug(slug)
    except ValidationError as exc:
        raise JsonResumeImportError(f"Invalid resume slug {slug!r}") from exc

    name_max_length = cast(int, Resume._meta.get_field("name").max_length)
    if len(name) > name_max_length:
        raise JsonResumeImportError(
            f"Resume name exceeds maximum length of {name_max_length} characters"
        )


def import_resume_document(
    document: dict,
    *,
    owner,
    slug: str,
    name: str | None = None,
    registry=None,
    restore_django_resume_data: bool = True,
) -> JsonResumeImport:
    """Create a new resume from a JSON Resume document."""
    registry = registry or plugin_registry
    errors = validate_document(document)
    if errors:
        return JsonResumeImport(
            resume=None,
            report=ImportReport(valid=False, validation_errors=errors),
        )
    if Resume.objects.filter(slug=slug).exists():
        raise JsonResumeImportError(f"A resume with slug {slug!r} already exists")

    django_resume_meta_value = get_pointer(document, "/meta/django_resume", None)
    if django_resume_meta_value is None:
        django_resume_meta = {}
    elif isinstance(django_resume_meta_value, dict):
        django_resume_meta = django_resume_meta_value
    else:
        return JsonResumeImport(
            resume=None,
            report=ImportReport(
                valid=False,
                validation_errors=["meta.django_resume must be an object"],
            ),
        )
    restored_plugin_data = django_resume_meta.get("plugin_data")
    if restore_django_resume_data and "plugin_data" in django_resume_meta:
        envelope_errors = _validate_restored_plugin_data(restored_plugin_data)
        if envelope_errors:
            return JsonResumeImport(
                resume=None,
                report=ImportReport(valid=False, validation_errors=envelope_errors),
            )
        restored_plugin_data = cast(dict, restored_plugin_data)
        plugin_data = deepcopy(restored_plugin_data)
        report = _report_restored_plugin_data(plugin_data)
        report.notes.append("restored plugin data from meta.django_resume.plugin_data")
    else:
        plugin_data, report = _collect_adapter_plugin_data(document, registry)

    resume_name = name or get_pointer(document, "/basics/name", "") or slug
    _validate_resume_metadata(slug=slug, name=resume_name)
    json_resume_state: dict[str, Any] = {"source_plugin_data": deepcopy(plugin_data)}
    if restore_django_resume_data or "plugin_data" not in django_resume_meta:
        json_resume_state["source_document"] = deepcopy(document)
    else:
        report.notes.append(
            "did not store source JSON Resume document for exact re-export because "
            "meta.django_resume.plugin_data was ignored"
        )
    integration_data: dict[str, Any] = {"json_resume": json_resume_state}
    source_adapter_document, source_notes = _build_source_adapter_document(
        plugin_data=plugin_data,
        owner=owner,
        slug=slug,
        name=resume_name,
        registry=registry,
    )
    report.notes.extend(source_notes)
    if source_adapter_document is not None:
        integration_data["json_resume"]["source_adapter_document"] = (
            source_adapter_document
        )
        if "source_document" in integration_data["json_resume"]:
            report.notes.append(
                "stored source JSON Resume document for exact re-export while mapped "
                "projection and plugin data remain unchanged"
            )
    preserved_extensions = django_resume_meta.get("preserved_extensions")
    if isinstance(preserved_extensions, list):
        integration_data["json_resume"]["preserved_extensions"] = deepcopy(
            preserved_extensions
        )
        report.notes.append("stored meta.django_resume.preserved_extensions")

    try:
        with transaction.atomic():
            resume = Resume.objects.create(
                name=resume_name,
                slug=slug,
                owner=owner,
                plugin_data=plugin_data,
                integration_data=integration_data,
            )
    except IntegrityError as exc:
        raise JsonResumeImportError(
            f"A resume with slug {slug!r} already exists"
        ) from exc
    return JsonResumeImport(resume=resume, report=report)


def import_resume_file(
    path: str | Path,
    *,
    owner,
    slug: str,
    name: str | None = None,
    registry=None,
    restore_django_resume_data: bool = True,
) -> JsonResumeImport:
    document = load_document(path)
    return import_resume_document(
        document,
        owner=owner,
        slug=slug,
        name=name,
        registry=registry,
        restore_django_resume_data=restore_django_resume_data,
    )


def get_owner(username: str):
    user_model = get_user_model()
    try:
        return user_model.objects.get(**{user_model.USERNAME_FIELD: username})
    except user_model.DoesNotExist as exc:
        raise JsonResumeImportError(
            f"No user found with username {username!r}"
        ) from exc
