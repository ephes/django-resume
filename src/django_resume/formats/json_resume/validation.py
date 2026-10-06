import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from jsonschema.validators import validator_for

_SCHEMA_PATH = Path(__file__).parent / "schema" / "schema.json"


@lru_cache(maxsize=1)
def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_document(document: dict) -> list[str]:
    """Validate ``document`` against the pinned schema.

    Returns a list of human-readable error strings ([] if valid). Structural
    validation only: ``format`` keywords (email, uri) are not enforced, so
    relative media URLs and similar pass. ``pattern`` keywords (e.g. dates) are
    enforced.
    """
    schema = _schema()
    validator_cls = validator_for(schema)
    validator = validator_cls(schema)
    errors = sorted(
        validator.iter_errors(document), key=lambda e: list(map(str, e.path))
    )
    messages: list[str] = []
    for error in errors:
        location = "/".join(str(part) for part in error.path) or "<root>"
        messages.append(f"{location}: {error.message}")
    return messages


_DATE_REF = "#/definitions/iso8601"


@lru_cache(maxsize=1)
def _section_date_fields() -> dict[str, tuple[str, ...]]:
    """Map each array section to its item fields typed as schema dates."""
    fields: dict[str, tuple[str, ...]] = {}
    for section, definition in _schema().get("properties", {}).items():
        item_properties = (definition.get("items") or {}).get("properties") or {}
        date_fields = tuple(
            sorted(
                name
                for name, item_schema in item_properties.items()
                if item_schema.get("$ref") == _DATE_REF
            )
        )
        if definition.get("type") == "array" and date_fields:
            fields[section] = date_fields
    return fields


def drop_empty_dates(document: dict) -> tuple[dict, list[str]]:
    """Treat empty optional item dates as absent before schema validation.

    Editors often write ``"endDate": ""`` for an ongoing position. Every
    schema date is optional, and the pinned date pattern rejects the empty
    string, so such a value carries no date and would otherwise refuse the
    whole document. Returns the document (a copy only when something was
    dropped) and one report note per dropped value. Non-empty invalid dates
    are left for validation to reject.
    """
    notes: list[str] = []
    result = document
    for section, date_fields in _section_date_fields().items():
        items = document.get(section)
        if not isinstance(items, list):
            continue
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            for field in date_fields:
                value = item.get(field)
                if not isinstance(value, str) or value.strip():
                    continue
                if result is document:
                    result = deepcopy(document)
                del result[section][index][field]
                notes.append(
                    f"{section}[{index}].{field} is an empty string; treated as absent"
                )
    return result, notes
