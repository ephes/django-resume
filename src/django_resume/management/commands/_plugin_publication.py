"""Persistent recovery authority for a filesystem plugin's complete generation."""

import hashlib
import json
import os
import shutil
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path

from django.core.management.base import CommandError

INTENT_LIMIT = 131072
_READ_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_BINARY", 0)
)


class _PreparedTargetChanged(CommandError):
    pass


class _NewGenerationChanged(CommandError):
    pass


def project_root() -> Path:
    # Commands resolve their targets below the current project directory.
    # Anchor the intent there even when ``templates`` or ``core/plugins`` is a
    # symlink to another tree, never in a shared ancestor of the targets.
    return Path.cwd().resolve()


def target_bases() -> set[Path]:
    root = project_root()
    return {root, (root / "core/plugins").resolve(), (root / "templates").resolve()}


def intent_path(paths: list[Path]) -> Path:
    return project_root() / f".django-resume-plugin-{paths[0].stem}.intent.json"


def require_recovered(paths: list[Path]) -> None:
    intent = intent_path(paths)
    if intent.exists() or intent.is_symlink():
        raise CommandError(
            f"Interrupted plugin publication: {intent}; run recover_plugin "
            f"{paths[0].stem} --action status before another mutation"
        )


def open_regular(path: Path) -> tuple[int, os.stat_result]:
    """Open ``path`` itself, without following links or blocking on FIFOs."""
    if path.is_symlink():
        raise ValueError(f"not a regular file: {path}")
    fd = os.open(path, _READ_FLAGS)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"not a regular file: {path}")
    except BaseException:
        os.close(fd)
        raise
    return fd, info


def digest(path: Path) -> str:
    result = hashlib.sha256()
    fd, _ = open_regular(path)
    try:
        for chunk in iter(lambda: os.read(fd, 65536), b""):
            result.update(chunk)
    finally:
        os.close(fd)
    return result.hexdigest()


def target_state(path: Path) -> str | None:
    """Digest of an installed regular target, or ``None`` when it is absent."""
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("not a regular file")
    state = digest(path)
    after = path.lstat()
    if (
        before.st_dev != after.st_dev
        or before.st_ino != after.st_ino
        or before.st_size != after.st_size
        or before.st_mtime_ns != after.st_mtime_ns
        or before.st_ctime_ns != after.st_ctime_ns
    ):
        raise ValueError("target changed while reading")
    return state


def _intent_stamp(info: os.stat_result) -> tuple[int, ...]:
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def read_intent(path: Path) -> tuple[bytes, tuple[int, ...]]:
    """Read one bounded regular intent and capture its identity."""
    fd, before = open_regular(path)
    try:
        if before.st_size > INTENT_LIMIT:
            raise ValueError(f"intent exceeds {INTENT_LIMIT} bytes")
        chunks: list[bytes] = []
        remaining = INTENT_LIMIT + 1
        while remaining:
            chunk = os.read(fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    raw = b"".join(chunks)
    if len(raw) > INTENT_LIMIT:
        raise ValueError(f"intent exceeds {INTENT_LIMIT} bytes")
    stamp = _intent_stamp(after)
    if (
        len(raw) != after.st_size
        or _intent_stamp(before) != stamp
        or _intent_stamp(path.lstat()) != stamp
    ):
        raise ValueError("intent changed while reading")
    return raw, stamp


def _validated(data: object) -> dict:
    # Shape checks only; ``load`` verifies paths and copies against the targets.
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        raise ValueError("malformed intent")
    if data.get("version") != 1 or data.get("operation") not in ("create", "remove"):
        raise ValueError("unsupported intent")
    for entry in data["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("malformed intent entry")
        for key in ["old", "new"]:
            if entry.get(key) is not None and not (
                isinstance(entry[key], str)
                and isinstance(entry.get(f"{key}_sha256"), str)
            ):
                raise ValueError("malformed intent entry")
    return data


def copy_sibling(source: Path, target: Path, kind: str) -> Path:
    fd, name = tempfile.mkstemp(prefix=f".{target.name}.{kind}-", dir=target.parent)
    os.close(fd)
    result = Path(name)
    try:
        shutil.copy2(source, result)
        sync_file(result)
    except BaseException:
        result.unlink(missing_ok=True)
        raise
    return result


def sync_file(path: Path) -> None:
    with path.open("rb") as source:
        os.fsync(source.fileno())


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
        # The exact bytes admitted by ``load``, also shown by ``status``.
        self.raw: bytes | None = None
        self._intent_stamp: tuple[int, ...] | None = None
        self._attempted: set[Path] = set()
        # Set by the removal body immediately before its transaction commits.
        # A later failure cannot prove a rollback, so files are not restored.
        self.commit_attempted = False

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
            if staged is not None:
                for source in staged.values():
                    if source is not None:
                        sync_file(source)
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
            # Persist bytes and sibling names, including freshly created parent
            # directories, before granting the intent any recovery authority.
            self.sync_targets()
            self.write_intent()
        except BaseException as error:
            if not self.intent.exists():
                self.cleanup()
                raise
            if isinstance(error, OSError):
                # The intent is visible (e.g. its directory sync failed), so it
                # blocks further mutations although no installed file changed.
                hint = (
                    " (the database was not touched: --database-outcome rolled-back)"
                    if self.data["operation"] == "remove"
                    else ""
                )
                raise CommandError(
                    f"Plugin files unchanged, but recovery intent retained: "
                    f"{self.intent}; run recover_plugin {self.paths[0].stem} "
                    f"--action status, then --action restore{hint}: {error}"
                ) from error
            raise

    def _require_old(self, path: Path, entry: dict) -> None:
        expected = entry["old_sha256"] if entry["old"] is not None else None
        message = f"Plugin target changed from its recorded old generation: {path}"
        try:
            current = target_state(path)
        except (OSError, ValueError) as error:
            raise _PreparedTargetChanged(f"{message} ({error})") from error
        if current != expected:
            raise _PreparedTargetChanged(message)

    def _require_new(self, path: Path, entry: dict, description: str) -> None:
        message = f"Plugin {description}: {path}"
        try:
            current = target_state(path)
        except (OSError, ValueError) as error:
            raise _NewGenerationChanged(f"{message} ({error})") from error
        if current != entry["new_sha256"]:
            raise _NewGenerationChanged(message)

    def verify_installed(self) -> None:
        for path, entry in zip(self.paths, self.data["files"]):
            self._require_new(path, entry, "installed generation differs from intent")

    def publish(self, staged: dict[Path, Path | None] | None = None) -> None:
        targets = list(zip(self.paths, self.data["files"]))
        # Refuse the full set before mutating it, then narrow the recheck to
        # the next target because an editor can save outside our writer locks.
        for path, entry in targets:
            self._require_old(path, entry)
        for path, entry in targets:
            self._require_old(path, entry)
            if staged is None and entry["old"] is None:
                continue
            source = staged[path] if staged is not None else None
            if staged is not None:
                assert source is not None
                self._require_new(
                    source, entry, "stage changed from its recorded new generation"
                )
            # Record the attempt before the syscall, which can be interrupted
            # after it changed the target.
            self._attempted.add(path)
            if source is None:
                path.unlink(missing_ok=True)
            else:
                source.replace(path)

    def sync_targets(self) -> None:
        # Sync each target directory and its ancestors up to the project root,
        # so freshly created parents (e.g. ``core`` and ``core/plugins``) are
        # durable. A base symlinked outside the root stops at that resolved
        # base instead of walking shared ancestors.
        root = self.intent.parent
        directories = {root}
        outside_stops = {
            base for base in target_bases() if not base.is_relative_to(root)
        }
        for path in self.paths:
            parent = path.parent
            while True:
                if parent.exists():
                    directories.add(parent)
                if parent == root or parent in outside_stops or parent == parent.parent:
                    break
                parent = parent.parent
        first_error: OSError | None = None
        for directory in sorted(directories, key=lambda p: (-len(p.parts), str(p))):
            try:
                sync_directory(directory)
            except OSError as error:
                if first_error is None:
                    first_error = error
        if first_error is not None:
            raise first_error

    def write_intent(self) -> None:
        # Atomic JSON publication: never expose a partially written intent.
        fd, name = tempfile.mkstemp(prefix=".plugin-intent-", dir=self.intent.parent)
        temporary = Path(name)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(
                    self.raw
                    if self.raw is not None
                    else json.dumps(self.data).encode("utf-8")
                )
                output.flush()
                os.fsync(output.fileno())
            if self.raw is None:
                temporary.replace(self.intent)
            else:
                # A recovery retirement sync failed. Restore the admitted
                # bytes only if no replacement has appeared in the meantime.
                os.link(temporary, self.intent)
            sync_directory(self.intent.parent)
        finally:
            temporary.unlink(missing_ok=True)

    def load(self) -> None:
        self.raw = None
        self._intent_stamp = None
        try:
            self.raw, stamp = read_intent(self.intent)
            data = _validated(json.loads(self.raw.decode("utf-8")))
            entries = data["files"]
            if [entry["path"] for entry in entries] != [
                str(path) for path in self.paths
            ]:
                raise ValueError("target set does not match")
            for path, entry in zip(self.paths, entries):
                for key, kind in [("old", "backup"), ("new", "new")]:
                    if entry[key] is None:
                        if key == "new" and data["operation"] == "create":
                            raise ValueError("missing new generation")
                        continue
                    copy = Path(entry[key])
                    try:
                        valid = (
                            copy.parent == path.parent
                            and copy.name.startswith(f".{path.name}.{kind}-")
                            and digest(copy) == entry[f"{key}_sha256"]
                        )
                    except (OSError, ValueError) as error:
                        raise ValueError(
                            f"invalid recovery copy: {copy} ({error})"
                        ) from error
                    if not valid:
                        raise ValueError(f"invalid recovery copy: {copy}")
        except (OSError, ValueError, KeyError, TypeError, RecursionError) as error:
            raise CommandError(
                f"Cannot read recovery intent {self.intent}: {error}"
            ) from error
        self.data = data
        self._intent_stamp = stamp

    def _intent_conflict(self) -> CommandError:
        return CommandError(
            f"Refusing plugin recovery: recovery intent changed at {self.intent}; "
            f"preserve the intent and recovery copies and inspect with "
            f"recover_plugin {self.paths[0].stem} --action status"
        )

    def _require_admitted_intent(self) -> None:
        if self._intent_stamp is None:
            return  # Internal rollback uses the intent it prepared itself.
        try:
            raw, stamp = read_intent(self.intent)
        except (OSError, ValueError) as error:
            raise self._intent_conflict() from error
        if raw != self.raw or stamp != self._intent_stamp:
            raise self._intent_conflict()

    def recorded(self, entry: dict) -> set[str | None]:
        # An absent generation is recorded as ``None``: the target is missing.
        return {
            entry[f"{key}_sha256"] if entry[key] is not None else None
            for key in ["old", "new"]
        }

    def admit(self, targets: list[tuple[Path, dict]]) -> None:
        """Refuse unless every target holds a generation this intent recorded.

        Anything else (an owner edit, a replacement file, a link, a directory
        or another special file) is a third generation recovery cannot own.
        """
        unexpected = []
        for path, entry in targets:
            try:
                state = target_state(path)
            except (OSError, ValueError) as error:
                unexpected.append(f"{path} ({error})")
                continue
            if state not in self.recorded(entry):
                unexpected.append(str(path))
        if unexpected:
            raise CommandError(
                f"Refusing plugin recovery: neither recorded generation is "
                f"installed at {', '.join(unexpected)} (changed after the "
                f"interrupted command?). "
                f"Nothing was changed by this check; {self.intent} and its "
                f"recovery copies are retained. Move each changed target aside, "
                f"put back its recorded old or new copy (or remove it where that "
                f"generation is absent), repeat recovery, then reapply the change."
            )

    def apply(self, generation: str, *, attempted_only: bool = False) -> None:
        # Keep the authority copies intact, so interruption during recovery is
        # itself recoverable by repeating exactly the same command. Admit the
        # complete target set first, then recheck each target and its staged
        # authority bytes immediately before replacing it.
        targets = list(zip(self.paths, self.data["files"]))
        self._require_admitted_intent()
        self.admit(targets)
        for path, entry in reversed(targets):
            if attempted_only and path not in self._attempted:
                continue
            source = entry[generation]
            if source is None:
                self.admit([(path, entry)])
                self._require_admitted_intent()
                path.unlink(missing_ok=True)
            else:
                copy = copy_sibling(Path(source), path, "backup-restore")
                try:
                    if digest(copy) != entry[f"{generation}_sha256"]:
                        raise CommandError(
                            f"Refusing plugin recovery: recovery copy changed "
                            f"while staging {path}; {self.intent} is retained"
                        )
                    self.admit([(path, entry)])
                    self._require_admitted_intent()
                    copy.replace(path)
                finally:
                    copy.unlink(missing_ok=True)
        self.sync_targets()

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
        self._require_admitted_intent()
        self.intent.unlink()
        try:
            sync_directory(self.intent.parent)
        except OSError:
            # The installed generation is complete, but retirement is uncertain.
            # Re-establish the visible blocker and retain every authority copy.
            try:
                self.write_intent()
            except FileExistsError as conflict:
                raise self._intent_conflict() from conflict
            except OSError:
                pass
            raise
        if self._intent_stamp is not None:
            try:
                self.intent.lstat()
            except FileNotFoundError:
                pass
            else:
                raise self._intent_conflict()
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
        if publication.commit_attempted:
            # A commit failure (e.g. a dropped connection) or an interruption
            # during commit may follow a committed deletion: keep the intent.
            if not isinstance(error, Exception):
                raise
            raise CommandError(
                f"{error}; database outcome uncertain after commit attempt; "
                f"plugin files stay removed; retain {publication.intent}, verify "
                f"the database and run recover_plugin {paths[0].stem} with "
                f"--database-outcome"
            ) from error
        if isinstance(error, _NewGenerationChanged) or (
            isinstance(error, _PreparedTargetChanged) and publication._attempted
        ):
            hint = (
                "; after verifying the rollback, use --database-outcome rolled-back"
                if database is not None
                else ""
            )
            raise CommandError(
                f"{error}; recovery intent retained: {publication.intent}; "
                f"run recover_plugin {paths[0].stem} --action status{hint}"
            ) from error
        try:
            if not isinstance(error, _PreparedTargetChanged):
                publication.apply("old", attempted_only=True)
            publication.retire()
        except (OSError, CommandError) as restore_error:
            raise CommandError(
                f"{error}; rollback incomplete; recover using {publication.intent}: "
                f"{restore_error}; backups: {publication.data['files']}"
            ) from error
        raise
    else:
        # A directory-sync failure after publication (or database commit) is
        # not a prepublication error: never restore blindly across this boundary.
        try:
            publication.sync_targets()
            if staged is not None:
                publication.verify_installed()
            publication.retire()
        except _NewGenerationChanged as error:
            raise CommandError(
                f"{error}; recovery intent retained: {publication.intent}; "
                f"run recover_plugin {paths[0].stem} --action status"
            ) from error
        except OSError as error:
            hint = (
                "; the removal transaction committed: use --action finish "
                "--database-outcome committed"
                if publication.data["operation"] == "remove"
                else ""
            )
            raise CommandError(
                f"Plugin files visible but durability uncertain; retain "
                f"{publication.intent} and its recovery copies{hint}: {error}"
            ) from error
