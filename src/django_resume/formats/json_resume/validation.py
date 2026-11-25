import json
import re
from itertools import islice
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

from jsonschema import ValidationError
from jsonschema.validators import extend, validator_for

_SCHEMA_PATH = Path(__file__).parent / "schema" / "schema.json"


@lru_cache(maxsize=1)
def _schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


MAX_NESTING_DEPTH = 64
MAX_VALIDATION_ERRORS = 20
MAX_LOCATION_LENGTH = 160
MAX_MESSAGE_LENGTH = 256


def _type_errors(validator, types, instance, schema):
    allowed = [types] if isinstance(types, str) else types
    if not any(validator.is_type(instance, kind) for kind in allowed):
        yield ValidationError(
            f"Value is not of type {', '.join(repr(kind) for kind in allowed)}."
        )


def _pattern_errors(validator, pattern, instance, schema):
    if validator.is_type(instance, "string") and not re.search(pattern, instance):
        yield ValidationError("Value does not match the required pattern.")


def _additional_property_errors(validator, allowed, instance, schema):
    # The pinned schema uses boolean additionalProperties and no
    # patternProperties. Avoid constructing/sorting a set of all extra names.
    if allowed or not validator.is_type(instance, "object"):
        return
    properties = schema.get("properties", {})
    for key in instance:
        if key not in properties:
            yield ValidationError("Additional property is not allowed.", path=[key])


@lru_cache(maxsize=1)
def _diagnostic_validator():
    schema = _schema()
    # These are the pinned schema's error-producing keywords. Keep the public
    # jsonschema traversal/type semantics, but never format input values into
    # ValidationError.message (the stock handlers do so before yielding).
    validator_cls = extend(
        validator_for(schema),
        {
            "type": _type_errors,
            "pattern": _pattern_errors,
            "additionalProperties": _additional_property_errors,
        },
    )
    return validator_cls(schema)


def _error_location(path) -> str:
    location = ""
    for part in path:
        component = str(part)[:MAX_LOCATION_LENGTH]
        location += ("/" if location else "") + component
        if len(location) > MAX_LOCATION_LENGTH:
            return location[: MAX_LOCATION_LENGTH - 1] + "…"
    return location or "<root>"


def validate_document(document: dict) -> list[str]:
    """Validate against the pinned schema, stopping at 20 errors.

    Errors follow stable schema/input traversal order, with paths limited to
    160 characters and messages to 256. Reaching the budget adds a conservative
    omission notice without asking the validator to inspect another item.
    Structural validation only: format keywords (email, uri) are not enforced.
    """
    messages = [
        f"{_error_location(error.path)}: {error.message}"[:MAX_MESSAGE_LENGTH]
        for error in islice(
            _diagnostic_validator().iter_errors(document), MAX_VALIDATION_ERRORS
        )
    ]
    if len(messages) == MAX_VALIDATION_ERRORS:
        messages.append("Further validation errors may be omitted (limit 20).")
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
