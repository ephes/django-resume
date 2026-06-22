from dataclasses import dataclass
from typing import Any

from .conflicts import detect_path_conflicts
from .pointer import set_pointer
from .protocols import AdapterExport, ExportAdapter


class PathConflictError(Exception):
    """Raised when adapters claim the same non-multivalued JSON Pointer."""


@dataclass
class ResolvedAdapter:
    plugin_name: str
    adapter: ExportAdapter
    facts: dict


def collect_adapters(
    plugins: list, resume, format_id: str = "json_resume"
) -> tuple[list[ResolvedAdapter], dict[str, str]]:
    """Resolve adapters for ``format_id`` from registered plugins.

    Returns (resolved adapters with facts, {omitted plugin name: reason}).
    """
    resolved: list[ResolvedAdapter] = []
    omitted: dict[str, str] = {}
    for plugin in plugins:
        get_adapters = getattr(plugin, "get_export_adapters", None)
        adapter = get_adapters().get(format_id) if callable(get_adapters) else None
        if adapter is None:
            omitted[plugin.name] = f"no {format_id} adapter"
            continue
        facts = plugin.get_structured_data(resume)
        resolved.append(ResolvedAdapter(plugin.name, adapter, facts))
    return resolved, omitted


def _check_conflicts(resolved: list[ResolvedAdapter]) -> None:
    claims: dict[str, list[str]] = {}
    multivalued_claims: dict[str, list[bool]] = {}
    for item in resolved:
        multivalued = set(item.adapter.multivalued_paths)
        for path in item.adapter.owned_paths:
            claims.setdefault(path, []).append(item.plugin_name)
            multivalued_claims.setdefault(path, []).append(path in multivalued)
    # Identical-path claims are allowed only if every claimer marks it multivalued.
    scalar_claims = {
        path: claimers
        for path, claimers in claims.items()
        if len(claimers) > 1 and not all(multivalued_claims[path])
    }
    conflict = detect_path_conflicts(scalar_claims)
    if conflict is not None and conflict.kind == "duplicate":
        names = ", ".join(conflict.claimers or [])
        raise PathConflictError(
            f"Multiple adapters claim non-multivalued path {conflict.path!r}: {names}"
        )
    # Ancestor/descendant overlaps between *different* paths are always an error:
    # an adapter owning a parent object would overwrite another's child writes.
    conflict = detect_path_conflicts(
        {path: [claimers[0]] for path, claimers in claims.items()}
    )
    if conflict is not None and conflict.kind == "overlap":
        if conflict.parent is not None and conflict.child is not None:
            raise PathConflictError(
                f"Overlapping write paths {conflict.parent!r} and {conflict.child!r}"
            )


def build_document(resolved: list[ResolvedAdapter]) -> tuple[dict, list[str]]:
    """Assemble a document from adapter contributions.

    Raises PathConflictError before assembly on identical non-multivalued claims
    or ancestor/descendant path overlaps, and during assembly if an adapter
    contributes a pointer it did not declare in ``owned_paths``. Multivalued
    (array) paths claimed by several adapters are concatenated in order.
    """
    _check_conflicts(resolved)
    notes: list[str] = []
    scalars: dict[str, Any] = {}
    arrays: dict[str, list] = {}
    for item in resolved:
        owned = set(item.adapter.owned_paths)
        multivalued = set(item.adapter.multivalued_paths)
        result: AdapterExport = item.adapter.export(item.facts)
        notes.extend(result.notes)
        for pointer, value in result.contributions:
            if pointer not in owned:
                raise PathConflictError(
                    f"Adapter {item.plugin_name!r} contributed undeclared path "
                    f"{pointer!r}"
                )
            if pointer in multivalued:
                arrays.setdefault(pointer, []).extend(value)
            else:
                scalars[pointer] = value
    document: dict[str, Any] = {}
    for pointer, value in scalars.items():
        set_pointer(document, pointer, value)
    for pointer, value in arrays.items():
        set_pointer(document, pointer, value)
    return document, notes
