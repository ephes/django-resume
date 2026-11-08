"""Shared validation for theme names used in template paths."""

import re


def is_valid_theme_name(value: object) -> bool:
    """Allow one nonempty ASCII path segment, including custom theme names."""
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]+", value) is not None
