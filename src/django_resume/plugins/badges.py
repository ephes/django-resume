"""The shared editor/import badge domain and loss-aware legacy reads."""

import json

from django import forms

MAX_BADGES = 1024
MAX_BADGE_LENGTH = 1024
MAX_BADGE_TEXT = 65536


def validate_badges(badges: object) -> None:
    if not isinstance(badges, list):
        raise forms.ValidationError("Badges must be a list of strings.")
    if len(badges) > MAX_BADGES:
        raise forms.ValidationError(f"Allow at most {MAX_BADGES} badges.")
    if any(not isinstance(badge, str) for badge in badges):
        raise forms.ValidationError("Badges must be a list of strings.")
    if any(len(badge) > MAX_BADGE_LENGTH for badge in badges):
        raise forms.ValidationError(
            f"Each badge allows at most {MAX_BADGE_LENGTH} characters."
        )

    if sum(map(len, badges)) > MAX_BADGE_TEXT:
        raise forms.ValidationError(
            f"Badge text allows at most {MAX_BADGE_TEXT} characters in total."
        )


def editor_badges_json(form: forms.Form) -> str:
    """Keep the whole draft for browser admission, including refused legacy data."""
    value = (
        form.data.get(form.add_prefix("badges"))
        if form.is_bound
        else form.initial.get("badges", form.fields["badges"].initial)
    )
    if value is None or value == "":
        value = []
    if isinstance(value, str):
        # Bound JSON is already encoded; invalid JSON must reach browser refusal.
        return value
    return json.dumps(value)


def validate_stored_badges(badges: object) -> None:
    """Private round-trip payloads: also accept the legacy stored shapes that
    ``display_badges`` reads without a note (``None`` and a JSON-encoded valid
    list), so an unchanged export re-imports."""
    if badges is None:
        return
    if isinstance(badges, str):
        try:
            badges = json.loads(badges)
        except (ValueError, RecursionError):
            raise forms.ValidationError("Badges must be a list of strings.") from None
    validate_badges(badges)


def display_badges(
    value: object, *, notes: list[str] | None = None, field: str = "badges"
) -> list[str]:
    """Omit invalid legacy values without exposing or changing the source."""
    if value is None:
        # Blank legacy JSONField input was stored as null: an empty list.
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, RecursionError):
            value = None
    try:
        validate_badges(value)
    except forms.ValidationError:
        if notes is not None:
            notes.append(f"{field}: invalid or excess badges omitted")
    if not isinstance(value, list):
        return []
    result: list[str] = []
    total = 0
    for badge in value[:MAX_BADGES]:
        if not isinstance(badge, str) or len(badge) > MAX_BADGE_LENGTH:
            continue
        total += len(badge)
        if total > MAX_BADGE_TEXT:
            break
        result.append(badge)
    return result


class BadgesField(forms.JSONField):
    def clean(self, value):
        badges = super().clean(value)
        if badges is None and value in (None, "", []):
            return []
        validate_badges(badges)
        return badges
