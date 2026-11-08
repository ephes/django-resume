from typing import Any


_MISSING = object()


def validate_pointer(pointer: str) -> None:
    """Admit nonempty object keys separated by slashes, without RFC 6901 escapes."""
    if (
        not isinstance(pointer, str)
        or not pointer.startswith("/")
        or "~" in pointer
        or any(not part for part in pointer[1:].split("/"))
    ):
        raise ValueError(
            "Object pointer requires nonempty /-separated keys without ~ escapes"
        )


def set_pointer(document: dict, pointer: str, value: Any) -> None:
    """Set a supported object pointer, creating intermediate objects."""
    validate_pointer(pointer)
    parts = pointer[1:].split("/")
    target = document
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def get_pointer(document: dict, pointer: str, default: Any = None) -> Any:
    """Return the value at a supported object pointer or ``default`` if absent."""
    validate_pointer(pointer)
    target: Any = document
    for part in pointer[1:].split("/"):
        if not isinstance(target, dict) or part not in target:
            return default
        target = target[part]
    return target


def has_pointer(document: dict, pointer: str) -> bool:
    """True when ``pointer`` exists in ``document``."""
    return get_pointer(document, pointer, _MISSING) is not _MISSING
