"""Sibling backups for the three filesystem plugin outputs."""

import os
import shutil
import tempfile
import warnings
from contextlib import contextmanager
from pathlib import Path

from django.core.management.base import CommandError


@contextmanager
def backup_files(paths: list[Path]):
    backups: dict[Path, Path | None] = {}
    try:
        for path in paths:
            if not path.exists():
                backups[path] = None
                continue
            if not path.is_file():
                raise CommandError(f"Plugin target is not a regular file: {path}")
            fd, name = tempfile.mkstemp(prefix=f".{path.name}.backup-", dir=path.parent)
            os.close(fd)
            backup_path = Path(name)
            backups[path] = backup_path
            shutil.copy2(path, backup_path)
    except BaseException:
        # Originals have not been touched yet.
        cleanup_backups(backups)
        raise

    try:
        yield
    except BaseException as error:
        failures = []
        for path, backup in reversed(list(backups.items())):
            try:
                if backup is None:
                    path.unlink(missing_ok=True)
                else:
                    backup.replace(path)
            except OSError as restore_error:
                failures.append(f"{path} (backup: {backup}): {restore_error}")
        if failures:
            raise CommandError(
                f"{error}; rollback incomplete; recover these files manually: "
                + "; ".join(failures)
            ) from error
        cleanup_backups(backups)
        raise
    else:
        cleanup_backups(backups)


def cleanup_backups(backups: dict[Path, Path | None]) -> None:
    for backup in backups.values():
        if backup is not None:
            try:
                backup.unlink(missing_ok=True)
            except OSError as error:
                warnings.warn(
                    f"Could not remove temporary plugin file {backup}: {error}",
                    RuntimeWarning,
                    stacklevel=2,
                )
