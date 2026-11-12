from dataclasses import dataclass
from typing import Any

from .conflicts import detect_path_conflicts, is_ancestor_path
from .pointer import set_pointer, validate_pointer
from .protocols import AdapterExport, ExportAdapter


class PathConflictError(Exception):
    """Raised when adapters violate their declared contribution path contracts."""


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


def _check_conflicts(
    resolved: list[ResolvedAdapter], reserved_paths: tuple[str, ...] = ()
) -> None:
    for item in resolved:
        for path in (*item.adapter.owned_paths, *item.adapter.multivalued_paths):
            try:
                validate_pointer(path)
            except ValueError as exc:
                raise PathConflictError(
                    f"Adapter {item.plugin_name!r} declares an unsupported object pointer"
                ) from exc
            for reserved in reserved_paths:
                if is_ancestor_path(path, reserved) or is_ancestor_path(reserved, path):
                    raise PathConflictError(
                        f"Adapter {item.plugin_name!r} path {path!r} overlaps "
                        f"reserved path {reserved!r}"
                    )
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


def build_document(
    resolved: list[ResolvedAdapter], *, reserved_paths: tuple[str, ...] = ()
) -> tuple[dict, list[str]]:
    """Assemble a document from adapter contributions.

    Raises PathConflictError before assembly on identical non-multivalued claims,
    ancestor/descendant path overlaps, or a declared path equal to, inside or
    containing one of ``reserved_paths``, and during assembly if an adapter
    contributes an undeclared pointer, repeats a non-multivalued contribution,
    or contributes a non-list to a multivalued path. Multivalued (array) paths
    claimed by several adapters are concatenated in order.
    """
    _check_conflicts(resolved, reserved_paths)
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
                if not isinstance(value, list):
                    raise PathConflictError(
                        f"Adapter {item.plugin_name!r} must contribute a list "
                        f"for multivalued path {pointer!r}"
                    )
                arrays.setdefault(pointer, []).extend(value)
            else:
                if pointer in scalars:
                    raise PathConflictError(
                        f"Adapter {item.plugin_name!r} contributed non-multivalued "
                        f"path {pointer!r} more than once"
                    )
                scalars[pointer] = value
    document: dict[str, Any] = {}
    for pointer, value in scalars.items():
        set_pointer(document, pointer, value)
    for pointer, value in arrays.items():
        set_pointer(document, pointer, value)
    return document, notes
