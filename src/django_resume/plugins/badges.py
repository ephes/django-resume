"""The shared editor/import badge domain and loss-aware legacy reads."""

import json

from django import forms

MAX_BADGES = 1024
MAX_BADGE_LENGTH = 1024


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


def display_badges(
    value: object, *, notes: list[str] | None = None, field: str = "badges"
) -> list[str]:
    """Omit invalid legacy values without exposing or changing the source."""
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
    return [
        badge
        for badge in value[:MAX_BADGES]
        if isinstance(badge, str) and len(badge) <= MAX_BADGE_LENGTH
    ]


class BadgesField(forms.JSONField):
    def clean(self, value):
        badges = super().clean(value)
        if badges is None and value in (None, "", []):
            return []
        validate_badges(badges)
        return badges
