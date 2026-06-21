from typing import Any


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
