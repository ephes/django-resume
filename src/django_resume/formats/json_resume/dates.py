import re

# JSON Resume v1.0.0 "iso8601" pattern: YYYY-MM-DD | YYYY-MM | YYYY.
_DATE_RE = re.compile(
    r"^([1-2][0-9]{3}-[0-1][0-9]-[0-3][0-9]|[1-2][0-9]{3}-[0-1][0-9]|[1-2][0-9]{3})$"
)


def is_valid_resume_date(value: str) -> bool:
    """True if ``value`` matches the JSON Resume iso8601 date pattern."""
    return bool(_DATE_RE.match(value or ""))
