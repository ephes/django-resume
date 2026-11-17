"""Persistent recovery authority for a filesystem plugin's complete generation."""

import hashlib
import json
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from django.core.management.base import CommandError


def intent_path(paths: list[Path]) -> Path:
    root = Path(os.path.commonpath([str(path.parent) for path in paths]))
    return root / f".django-resume-plugin-{paths[0].stem}.intent.json"


def require_recovered(paths: list[Path]) -> None:
    intent = intent_path(paths)
    if intent.exists() or intent.is_symlink():
        raise CommandError(
            f"Interrupted plugin publication: {intent}; run recover_plugin "
            f"{paths[0].stem} --action status before another mutation"
        )


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            result.update(chunk)
    return result.hexdigest()


def copy_sibling(source: Path, target: Path, kind: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.{kind}-", dir=target.parent)
    os.close(fd)
    result = Path(name)
    try:
        shutil.copy2(source, result)
    except BaseException:
        result.unlink(missing_ok=True)
        raise
    return result


def sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


class Publication:
    def __init__(self, paths: list[Path]):
        self.paths = paths
        self.intent = intent_path(paths)
        self.data: dict = {"version": 1, "operation": "create", "files": []}

    def prepare(
        self, staged: dict[Path, Path | None] | None, database: str | None = None
    ) -> None:
        if database is not None:
            from django.db import connections

            selected = connections[database].settings_dict
            self.data["operation"] = "remove"
            self.data["database"] = {
                "alias": database,
                "engine": selected["ENGINE"],
                "name": str(selected["NAME"]),
                "outcome": "unknown",
            }
        try:
            for path in self.paths:
                if path.exists() and not path.is_file():
                    raise CommandError(f"Plugin target is not a regular file: {path}")
                entry = {"path": str(path), "old": None, "new": None}
                self.data["files"].append(entry)
                for key, source in [
                    ("old", path if path.exists() else None),
                    ("new", staged[path] if staged is not None else None),
                ]:
                    if source is not None:
                        copy = copy_sibling(
                            source, path, "backup" if key == "old" else "new"
                        )
                        entry[key] = str(copy)
                        entry[f"{key}_sha256"] = digest(copy)
            # Publish the intent before touching any installed file. The atomic
            # rename means a killed writer never exposes half a JSON document.
            fd, name = tempfile.mkstemp(
                prefix=".plugin-intent-", dir=self.intent.parent
            )
            with os.fdopen(fd, "w") as output:
                json.dump(self.data, output)
                output.flush()
                os.fsync(output.fileno())
            Path(name).replace(self.intent)
            sync_directory(self.intent.parent)
        except BaseException:
            if not self.intent.exists():
                self.cleanup()
            raise

    def load(self) -> None:
        try:
            if self.intent.is_symlink() or self.intent.stat().st_size > 131072:
                raise ValueError("invalid intent file")
            self.data = json.loads(self.intent.read_text())
            if self.data["version"] != 1 or self.data["operation"] not in {
                "create",
                "remove",
            }:
                raise ValueError("unsupported intent")
            entries = self.data["files"]
            if [entry["path"] for entry in entries] != [
                str(path) for path in self.paths
            ]:
                raise ValueError("target set does not match")
            for path, entry in zip(self.paths, entries):
                for key, kind in [("old", "backup"), ("new", "new")]:
                    if entry[key] is None:
                        if key == "new" and self.data["operation"] == "create":
                            raise ValueError("missing new generation")
                        continue
                    copy = Path(entry[key])
                    if (
                        copy.parent != path.parent
                        or not copy.name.startswith(f".{path.name}.{kind}-")
                        or copy.is_symlink()
                        or not copy.is_file()
                        or digest(copy) != entry[f"{key}_sha256"]
                    ):
                        raise ValueError(f"invalid recovery copy: {copy}")
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise CommandError(
                f"Cannot read recovery intent {self.intent}: {error}"
            ) from error

    def apply(self, generation: str) -> None:
        # Keep the authority copies intact, so interruption during recovery is
        # itself recoverable by repeating exactly the same command.
        for path, entry in reversed(list(zip(self.paths, self.data["files"]))):
            source = entry[generation]
            if source is None:
                path.unlink(missing_ok=True)
            else:
                copy = copy_sibling(Path(source), path, "backup-restore")
                try:
                    copy.replace(path)
                finally:
                    copy.unlink(missing_ok=True)

    def cleanup(self) -> None:
        from ._file_rollback import cleanup_backups

        copies: dict[Path, Path | None] = {
            Path(entry[key]): Path(entry[key])
            for entry in self.data["files"]
            for key in ["old", "new"]
            if entry[key] is not None
        }
        cleanup_backups(copies)

    def retire(self) -> None:
        self.intent.unlink()
        self.cleanup()


@contextmanager
def publication_files(
    paths: list[Path],
    staged: dict[Path, Path | None] | None,
    *,
    database: str | None = None,
):
    publication = Publication(paths)
    publication.prepare(staged, database)
    try:
        yield publication
    except BaseException as error:
        try:
            publication.apply("old")
        except OSError as restore_error:
            raise CommandError(
                f"{error}; rollback incomplete; recover using {publication.intent}: "
                f"{restore_error}; backups: {publication.data['files']}"
            ) from error
        publication.retire()
        raise
    else:
        publication.retire()
