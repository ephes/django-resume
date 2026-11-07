"""Sibling backups for the three filesystem plugin outputs."""

import os
import logging
import hashlib
import getpass
import stat
import shutil
import tempfile
import time
from contextlib import ExitStack, contextmanager
from pathlib import Path

from django.core.management.base import CommandError
from filelock import FileLock, Timeout


logger = logging.getLogger(__name__)
WRITER_LOCK_TIMEOUT = 10


def _lock_path(path: Path) -> Path:
    uid = os.getuid() if hasattr(os, "getuid") else None
    account = (
        str(uid)
        if uid is not None
        else hashlib.sha256(os.fsencode(getpass.getuser())).hexdigest()
    )
    directory = Path(tempfile.gettempdir()) / f"django-resume-plugin-locks-{account}"
    directory.mkdir(mode=0o700, exist_ok=True)
    info = directory.lstat()
    if not stat.S_ISDIR(info.st_mode) or (
        uid is not None and (info.st_uid != uid or info.st_mode & 0o077)
    ):
        raise CommandError(
            f"Unsafe plugin lock directory; use a private TMPDIR: {directory}"
        )
    identity = os.path.normcase(str(path.resolve()))
    digest = hashlib.sha256(os.fsencode(identity)).hexdigest()
    return directory / f"{digest}.lock"


@contextmanager
def backup_files(paths: list[Path]):
    # Per-target locks also serialize overlapping target sets. Filelock owns
    # lock-file lifecycle; do not manually unlink a cooperating writer's lock.
    deadline = time.monotonic() + WRITER_LOCK_TIMEOUT
    with ExitStack() as locks:
        for path in sorted({path.resolve() for path in paths}):
            try:
                locks.enter_context(
                    FileLock(
                        _lock_path(path),
                        timeout=max(0, deadline - time.monotonic()),
                        mode=0o600,
                    )
                )
            except Timeout as error:
                raise CommandError(f"Plugin writer busy; retry: {path}") from error
        with _backup_files(paths):
            yield


@contextmanager
def _backup_files(paths: list[Path]):
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
                try:
                    logger.warning(
                        "Could not remove temporary plugin file %s (%s)",
                        str(backup)[:4096],
                        type(error).__name__[:80],
                    )
                except Exception:
                    # A diagnostic handler must not change the command outcome.
                    pass
