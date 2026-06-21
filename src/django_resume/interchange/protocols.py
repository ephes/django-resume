from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

# A single contribution: (RFC 6901 JSON Pointer, value), e.g. ("/basics/name", "Jane").
Contribution = tuple[str, Any]


@dataclass(frozen=True)
class AdapterExport:
    """What an adapter produces for one resume."""

    contributions: list[Contribution]
    notes: list[str] = field(default_factory=list)


@runtime_checkable
class ExportAdapter(Protocol):
    # Fine-grained JSON Pointers this adapter writes.
    owned_paths: tuple[str, ...]
    # Subset of owned_paths that are array-valued and may be contributed to by
    # more than one adapter; their list values are concatenated by the coordinator.
    multivalued_paths: tuple[str, ...]

    def export(self, facts: dict) -> AdapterExport:
        """Map structured facts to contributions for one resume."""
        ...
