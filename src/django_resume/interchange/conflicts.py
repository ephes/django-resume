from dataclasses import dataclass


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
    for path, claimers in claims.items():
        if len(claimers) > 1:
            return PathConflict(kind="duplicate", path=path, claimers=claimers)

    paths = sorted(claims)
    for index, parent in enumerate(paths):
        for child in paths[index + 1 :]:
            if parent != child and is_ancestor_path(parent, child):
                return PathConflict(
                    kind="overlap", path=parent, parent=parent, child=child
                )
    return None
