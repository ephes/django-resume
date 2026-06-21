import json
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
