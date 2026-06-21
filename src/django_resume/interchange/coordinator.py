from dataclasses import dataclass
from typing import Any

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


def _is_ancestor(ancestor: str, descendant: str) -> bool:
    """True if ``descendant`` is ``ancestor`` itself or nested beneath it."""
    return descendant == ancestor or descendant.startswith(ancestor + "/")


def _check_conflicts(resolved: list[ResolvedAdapter]) -> None:
    # claims: path -> list of (plugin_name, is_multivalued)
    claims: dict[str, list[tuple[str, bool]]] = {}
    for item in resolved:
        multivalued = set(item.adapter.multivalued_paths)
        for path in item.adapter.owned_paths:
            claims.setdefault(path, []).append((item.plugin_name, path in multivalued))
    # Identical-path claims are allowed only if every claimer marks it multivalued.
    for path, claimers in claims.items():
        if len(claimers) > 1 and not all(is_mv for _, is_mv in claimers):
            names = ", ".join(name for name, _ in claimers)
            raise PathConflictError(
                f"Multiple adapters claim non-multivalued path {path!r}: {names}"
            )
    # Ancestor/descendant overlaps between *different* paths are always an error:
    # an adapter owning a parent object would overwrite another's child writes.
    paths = sorted(claims)
    for index, parent in enumerate(paths):
        for child in paths[index + 1 :]:
            if parent != child and _is_ancestor(parent, child):
                raise PathConflictError(
                    f"Overlapping write paths {parent!r} and {child!r}"
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
