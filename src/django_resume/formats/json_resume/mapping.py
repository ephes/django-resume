"""Shared helpers for plugin-owned JSON Resume import adapters."""

from collections.abc import Iterable


def description_with_highlights(description: object, highlights: object) -> str:
    """Join a description and ``highlights`` as Markdown bullet lines.

    django-resume item descriptions are Markdown, so JSON Resume highlights
    become ``- `` lines after the description instead of being dropped.
    """
    parts = []
    if isinstance(description, str) and description:
        parts.append(description)
    if isinstance(highlights, list):
        bullet_lines = [
            "- " + highlight.replace("\n", " ")
            for highlight in highlights
            if isinstance(highlight, str) and highlight
        ]
        if bullet_lines:
            parts.append("\n".join(bullet_lines))
    return "\n\n".join(parts)


def _is_filled(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def unimported_item_fields(
    subject: str, entry: dict, consumed: Iterable[str]
) -> list[str]:
    """Return a loss note for filled ``entry`` keys an adapter does not consume.

    ``subject`` names the entry in the note, e.g. ``"work entry 'Acme'"``.
    ``consumed`` lists the keys the adapter maps or reports itself. Empty
    values are not reported because dropping them loses nothing.
    """
    consumed_keys = set(consumed)
    dropped = sorted(
        key
        for key, value in entry.items()
        if key not in consumed_keys and _is_filled(value)
    )
    if not dropped:
        return []
    return [
        f"{subject} field(s) {', '.join(dropped)} not imported; no django-resume field"
    ]
