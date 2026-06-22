from typing import Any


_MISSING = object()


def set_pointer(document: dict, pointer: str, value: Any) -> None:
    """Set ``value`` at an RFC 6901 JSON Pointer, creating intermediate objects.

    Only object steps are supported. Array *values* are set whole at a leaf
    pointer such as ``/work``. Pointers used by django-resume contain no ``~``
    or embedded ``/``, so pointer-escaping is intentionally not implemented.
    """
    if not pointer.startswith("/"):
        raise ValueError(f"JSON Pointer must start with '/': {pointer!r}")
    parts = pointer[1:].split("/")
    target = document
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    target[parts[-1]] = value


def get_pointer(document: dict, pointer: str, default: Any = None) -> Any:
    """Return the value at an RFC 6901 JSON Pointer or ``default`` if absent."""
    if not pointer.startswith("/"):
        raise ValueError(f"JSON Pointer must start with '/': {pointer!r}")
    if pointer == "/":
        return document
    target: Any = document
    for part in pointer[1:].split("/"):
        if not isinstance(target, dict) or part not in target:
            return default
        target = target[part]
    return target


def has_pointer(document: dict, pointer: str) -> bool:
    """True when ``pointer`` exists in ``document``."""
    return get_pointer(document, pointer, _MISSING) is not _MISSING
