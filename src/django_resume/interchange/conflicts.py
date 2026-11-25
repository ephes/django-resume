from dataclasses import dataclass

from .pointer import validate_pointer


@dataclass(frozen=True)
class PathConflict:
    kind: str
    path: str
    claimers: list[str] | None = None
    parent: str | None = None
    child: str | None = None


def is_ancestor_path(ancestor: str, descendant: str) -> bool:
    """True if ``descendant`` is ``ancestor`` itself or nested beneath it."""
    return descendant == ancestor or descendant.startswith(ancestor + "/")


def detect_path_conflicts(claims: dict[str, list[str]]) -> PathConflict | None:
    """Return the first duplicate or ancestor/descendant path conflict."""
    for path in claims:
        validate_pointer(path)
    for path, claimers in claims.items():
        if len(claimers) > 1:
            return PathConflict(kind="duplicate", path=path, claimers=claimers)

    first_overlap: tuple[str, str] | None = None
    for child in claims:
        boundary = child.find("/", 1)
        while boundary != -1:
            parent = child[:boundary]
            if parent in claims:
                # The shortest matching prefix sorts first for this child.
                # Choose the first pair in parent-then-child order overall.
                candidate = (parent, child)
                if first_overlap is None or candidate < first_overlap:
                    first_overlap = candidate
                break
            boundary = child.find("/", boundary + 1)
    if first_overlap is not None:
        parent, child = first_overlap
        return PathConflict(kind="overlap", path=parent, parent=parent, child=child)
    return None
