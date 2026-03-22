import re

from pathlib import Path

from django.core.management.base import CommandError


PLUGIN_NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def validate_plugin_name(plugin_name: str) -> str:
    if not PLUGIN_NAME_RE.fullmatch(plugin_name):
        raise CommandError(
            "Invalid plugin name. Use lowercase letters, numbers, and underscores only."
        )
    return plugin_name


def resolve_within(base_dir: Path, *parts: str) -> Path:
    resolved_base = base_dir.resolve()
    resolved_path = (base_dir.joinpath(*parts)).resolve()
    if resolved_path != resolved_base and resolved_base not in resolved_path.parents:
        raise CommandError("Resolved path escapes the expected directory.")
    return resolved_path
