"""Synthetic cross-process command writers; use spawn on every platform."""

import multiprocessing
import os
from pathlib import Path
from io import StringIO

import pytest


def _writer(root, operation, plugin, started, paused, release, finished, results):
    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
    import django

    django.setup()
    from django.conf import settings
    from django.core.management import call_command

    # Each child uses the same real, synthetic SQLite database.
    settings.DATABASES["default"]["NAME"] = str(Path(root) / "fixture.sqlite3")
    os.chdir(root)
    if operation == "failing_create":
        replace = Path.replace

        def fail_after_first(path, target):
            result = replace(path, target)
            if ".stage-" in path.name and Path(target).suffix == ".py":
                paused.set()
                if not release.wait(20):
                    raise RuntimeError("test rendezvous timed out")
                raise OSError("late synthetic failure")
            return result

        Path.replace = fail_after_first
    started.set()
    try:
        if operation == "remove":
            call_command("remove_plugin_by_name", plugin, stdout=StringIO())
        else:
            import sys

            sys.stdin = StringIO(
                f"==={plugin}===\n==={plugin}.py===\nnew python\n"
                f"===django_resume/plugins/{plugin}/plain/content.html===\nnew content\n"
                f"===django_resume/plugins/{plugin}/plain/form.html===\nnew form"
            )
            call_command("create_plugin_from_stdin", stdout=StringIO())
        results.put("ok")
    except Exception as error:
        results.put(str(error))
    finally:
        finished.set()


def _paths(root, plugin="safe_plugin"):
    return [
        root / f"core/plugins/{plugin}.py",
        root / f"templates/django_resume/plugins/{plugin}/plain/content.html",
        root / f"templates/django_resume/plugins/{plugin}/plain/form.html",
    ]


@pytest.mark.parametrize(
    "operation,plugin",
    [("create", "safe_plugin"), ("remove", "safe_plugin"), ("create", "independent")],
)
def test_cooperating_writers_serialize_rollback(tmp_path, operation, plugin):
    import sqlite3

    # The remove manager only needs this empty table; no shared pytest DB.
    with sqlite3.connect(tmp_path / "fixture.sqlite3") as database:
        database.execute(
            "CREATE TABLE django_resume_resume (id integer primary key, plugin_data text)"
        )
    for path in _paths(tmp_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("old")
    context = multiprocessing.get_context("spawn")
    paused, release = context.Event(), context.Event()
    processes = []
    queues = []

    def launch(action, name):
        started, finished, results = context.Event(), context.Event(), context.Queue()
        process = context.Process(
            target=_writer,
            args=(
                str(tmp_path),
                action,
                name,
                started,
                paused,
                release,
                finished,
                results,
            ),
        )
        processes.append(process)
        queues.append(results)
        process.start()
        assert started.wait(20)
        return finished, results

    try:
        _, first = launch("failing_create", "safe_plugin")
        assert paused.wait(20)
        finished, second = launch(operation, plugin)
        if plugin == "independent":
            assert finished.wait(20), "unrelated plugin blocked"
        else:
            assert not finished.wait(1), "writer bypassed the active rollback lock"
        release.set()
        for process in processes:
            process.join(20)
            assert process.exitcode == 0
        assert "late synthetic failure" in first.get(timeout=5)
        assert second.get(timeout=5) == "ok"
        if operation == "remove":
            assert not any(path.exists() for path in _paths(tmp_path))
        else:
            assert [path.read_text().strip() for path in _paths(tmp_path, plugin)] == [
                "new python",
                "new content",
                "new form",
            ]
            if plugin == "independent":
                assert [path.read_text() for path in _paths(tmp_path)] == ["old"] * 3
    finally:
        release.set()
        for process in processes:
            if process.is_alive():
                process.terminate()
            process.join(5)
        for results in queues:
            results.close()


@pytest.mark.parametrize("phase", ["preparation", "body", "success"])
def test_backup_cleanup_cannot_replace_outcome(tmp_path, monkeypatch, phase):
    import shutil
    import warnings

    from django_resume.management.commands._file_rollback import backup_files

    paths = [tmp_path / "one", tmp_path / "two"]
    for path in paths:
        path.write_text("original")
    unlink, copy = Path.unlink, shutil.copy2
    diagnostics = []

    def fail_unlink(path, *args, **kwargs):
        if ".backup-" in path.name:
            diagnostics.append(str(path))
            raise OSError("synthetic unlink failure")
        return unlink(path, *args, **kwargs)

    def fail_copy(source, target):
        if source == paths[1]:
            raise OSError("primary preparation failure")
        return copy(source, target)

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    if phase == "preparation":
        monkeypatch.setattr(shutil, "copy2", fail_copy)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        if phase == "success":
            with backup_files(paths):
                paths[0].write_text("published")
            assert paths[0].read_text() == "published"
        else:
            expected = OSError if phase == "preparation" else ValueError
            with pytest.raises(expected, match=f"primary {phase} failure"):
                with backup_files(paths):
                    paths[0].write_text("partial")
                    raise ValueError("primary body failure")
            assert paths[0].read_text() == "original"
    assert diagnostics
    if phase != "body":
        assert list(tmp_path.glob(".*.backup-*"))


def test_backup_cleanup_names_leftovers(tmp_path, monkeypatch, caplog):
    from django_resume.management.commands._file_rollback import cleanup_backups

    leftover = tmp_path / ".plugin.backup-synthetic"
    leftover.write_text("recovery")
    monkeypatch.setattr(
        Path, "unlink", lambda *a, **k: (_ for _ in ()).throw(OSError("failed"))
    )
    cleanup_backups({tmp_path / "plugin": leftover})
    assert str(leftover) in caplog.text
    assert leftover.read_text() == "recovery"


def test_backup_cleanup_survives_broken_diagnostic_handler(tmp_path, monkeypatch):
    from django_resume.management.commands import _file_rollback as rollback

    def fail(*args, **kwargs):
        raise OSError("synthetic handler failure")

    monkeypatch.setattr(Path, "unlink", fail)
    monkeypatch.setattr(rollback.logger, "warning", fail)
    rollback.cleanup_backups({tmp_path / "plugin": tmp_path / ".backup"})


def test_busy_writer_times_out_before_mutation_and_releases_locks(
    tmp_path, monkeypatch
):
    from django.core.management.base import CommandError
    from filelock import FileLock
    from django_resume.management.commands import _file_rollback as rollback

    paths = [tmp_path / "a", tmp_path / "z"]
    for path in paths:
        path.write_text("original")
    monkeypatch.setattr(rollback, "WRITER_LOCK_TIMEOUT", 0.05)
    with FileLock(rollback._lock_path(paths[1])):
        with pytest.raises(CommandError, match="writer busy"):
            with rollback.backup_files(paths):
                pytest.fail("busy command must not mutate")
        # The earlier lock was unwound even though the last lock timed out.
        with FileLock(rollback._lock_path(paths[0]), timeout=0):
            pass
    assert [path.read_text() for path in paths] == ["original"] * 2
    assert not list(tmp_path.glob(".*.backup-*"))


@pytest.mark.django_db
def test_remove_absent_plugin_leaves_project_tree_untouched(tmp_path, monkeypatch):
    from django.core.management import call_command

    monkeypatch.chdir(tmp_path)
    call_command("remove_plugin_by_name", "absent")
    assert not list(tmp_path.iterdir())


def test_busy_create_cleans_staged_outputs(tmp_path, monkeypatch):
    from django.core.management import call_command
    from django.core.management.base import CommandError
    from filelock import FileLock
    from django_resume.management.commands import _file_rollback as rollback
    from tests.management_commands_test import plugin_bundle

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    monkeypatch.setattr(rollback, "WRITER_LOCK_TIMEOUT", 0.05)
    paths = _paths(tmp_path)
    with FileLock(rollback._lock_path(paths[0])):
        with pytest.raises(CommandError, match="writer busy"):
            call_command("create_plugin_from_stdin")
    assert not any(path.exists() for path in paths)
    assert not list(tmp_path.rglob(".*.stage-*"))
    assert not list(tmp_path.rglob(".*.backup-*"))


@pytest.mark.parametrize(
    "unsafe", ["foreign_owner", "public_permissions", "not_directory"]
)
def test_lock_directory_refuses_unsafe_posix_metadata(tmp_path, monkeypatch, unsafe):
    import stat
    from types import SimpleNamespace
    from django.core.management.base import CommandError
    from django_resume.management.commands import _file_rollback as rollback

    info = SimpleNamespace(st_uid=123, st_mode=stat.S_IFDIR | 0o700)
    if unsafe == "foreign_owner":
        info.st_uid = 456
    elif unsafe == "public_permissions":
        info.st_mode |= 0o020
    else:
        info.st_mode = stat.S_IFLNK | 0o700
    # Synthetic POSIX metadata keeps these refusal tests platform-independent.
    monkeypatch.setattr(rollback.os, "getuid", lambda: 123, raising=False)
    monkeypatch.setattr(rollback.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: None)
    monkeypatch.setattr(Path, "lstat", lambda *a, **k: info)
    with pytest.raises(CommandError, match="Unsafe plugin lock directory"):
        rollback._lock_path(tmp_path / "plugin.py")


def test_lock_directory_is_separate_from_plugin_outputs(tmp_path, monkeypatch):
    from django_resume.management.commands import _file_rollback as rollback

    monkeypatch.setattr(rollback.tempfile, "gettempdir", lambda: str(tmp_path))
    target = tmp_path / "project/core/plugins/absent.py"
    lock = rollback._lock_path(target)
    assert lock.parent.is_dir()
    assert not target.parent.exists()
    assert lock == rollback._lock_path(target)
