"""Crash/reopen regressions using synthetic files and spawned command processes."""

import json
import multiprocessing
import os
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from tests.plugin_file_ownership_test import _paths


def plugin_bundle():
    from tests.management_commands_test import plugin_bundle as bundle

    return bundle()


def _crashing_create(root, barrier, reached):
    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
    import django

    django.setup()
    import sys

    os.chdir(root)
    sys.stdin = StringIO(plugin_bundle())
    replace = Path.replace
    count = 0

    def pause(path, target):
        nonlocal count
        result = replace(path, target)
        if ".stage-" in path.name and Path(target) in _paths(Path(root)):
            count += 1
            if count == barrier:
                reached.set()
                # Parent kills us here: Python exception handlers cannot run.
                import time

                time.sleep(60)
        return result

    Path.replace = pause
    call_command("create_plugin_from_stdin", stdout=StringIO())


def _kill(context, target, args, reached):
    process = context.Process(target=target, args=args)
    process.start()
    try:
        assert reached.wait(20), "child did not reach crash barrier"
        process.kill()
        process.join(10)
        assert process.exitcode != 0
    finally:
        if process.is_alive():
            process.kill()
        process.join(5)


@pytest.mark.parametrize("barrier", [1, 2, 3])
@pytest.mark.parametrize("action", ["restore", "finish"])
def test_create_killed_between_replacements_requires_recovery(
    tmp_path, monkeypatch, barrier, action
):
    monkeypatch.chdir(tmp_path)
    paths = _paths(tmp_path)
    for index, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"old {index}")
    context = multiprocessing.get_context("spawn")
    reached = context.Event()
    _kill(context, _crashing_create, (str(tmp_path), barrier, reached), reached)
    visible = [path.read_bytes() for path in paths]
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    with pytest.raises(CommandError, match="[Ii]nterrupted plugin publication"):
        call_command("create_plugin_from_stdin", stdout=StringIO())
    assert [path.read_bytes() for path in paths] == visible
    intents = list(tmp_path.rglob("*.intent.json"))
    assert len(intents) == 1
    intent = json.loads(intents[0].read_text())
    for entry in intent["files"]:
        assert Path(entry["old"]).read_text().startswith("old ")
        assert Path(entry["new"]).is_file()
    call_command("recover_plugin", "safe_plugin", action=action, stdout=StringIO())
    if action == "restore":
        assert [path.read_text() for path in paths] == [f"old {i}" for i in range(3)]
    else:
        assert all("old " not in path.read_text() for path in paths)
    assert not list(tmp_path.rglob("*.intent.json"))
    # A fresh invocation is admitted only after explicit recovery.
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    call_command("create_plugin_from_stdin", stdout=StringIO())


def _crashing_remove(root, database, barrier, reached):
    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
    import django

    django.setup()
    from django.conf import settings
    from django.db import connections
    from django_resume.models import ResumeManager

    settings.DATABASES["default"] = database
    connections["default"].close()
    from django.db.utils import load_backend

    connections._connections.default = load_backend(database["ENGINE"]).DatabaseWrapper(
        database, "default"
    )
    os.chdir(root)
    import time

    def pause():
        reached.set()
        time.sleep(60)

    if barrier == "before_commit":
        remove = ResumeManager.remove_plugin_data_by_name

        def remove_then_pause(manager, *args, **kwargs):
            remove(manager, *args, **kwargs)
            pause()

        ResumeManager.remove_plugin_data_by_name = remove_then_pause
    else:
        connection = connections["default"]
        commit = connection.commit

        def commit_then_pause():
            commit()
            pause()

        connection.commit = commit_then_pause
    call_command("remove_plugin_by_name", "safe_plugin", stdout=StringIO())


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("barrier", ["before_commit", "after_commit"])
def test_remove_killed_at_database_boundary_keeps_explicit_recovery(
    tmp_path, monkeypatch, barrier, user
):
    from django.db import connections
    from django_resume.models import Resume

    connection = connections["default"]
    # Copy SQLite's in-memory test database to an isolated, reopenable file.
    # PostgreSQL uses the test database, shared with the spawned connection.
    isolated = None
    if connection.vendor == "sqlite":
        import sqlite3

        connection.ensure_connection()
        name = tmp_path / "fixture.sqlite3"
        with sqlite3.connect(name) as target:
            connection.connection.backup(target)
        isolated = connection.copy()
        isolated.settings_dict = {**connection.settings_dict, "NAME": str(name)}
        monkeypatch.setattr(connections._connections, "default", isolated)
        connection = isolated
    try:
        user.save()
        row = Resume.objects.create(
            name="Synthetic",
            slug="synthetic",
            owner=user,
            plugin_data={"safe_plugin": {"text": "synthetic"}, "keep": {}},
        )
        paths = _paths(tmp_path)
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("old code")
        context = multiprocessing.get_context("spawn")
        reached = context.Event()
        _kill(
            context,
            _crashing_remove,
            (str(tmp_path), connection.settings_dict, barrier, reached),
            reached,
        )
        row.refresh_from_db()
        committed = barrier == "after_commit"
        assert ("safe_plugin" not in row.plugin_data) == committed
        assert not any(path.exists() for path in paths)
        monkeypatch.chdir(tmp_path)
        with pytest.raises(CommandError, match="[Ii]nterrupted plugin publication"):
            call_command("remove_plugin_by_name", "safe_plugin", stdout=StringIO())
        intent = json.loads(next(tmp_path.glob("*.intent.json")).read_text())
        assert intent["operation"] == "remove"
        assert intent["database"]["alias"] == "default"
        assert intent["database"]["outcome"] == "unknown"
        assert all(
            Path(entry["old"]).read_text() == "old code" for entry in intent["files"]
        )
        action = "finish" if committed else "restore"
        with pytest.raises(CommandError, match="database-outcome"):
            call_command(
                "recover_plugin", "safe_plugin", action=action, stdout=StringIO()
            )
        call_command(
            "recover_plugin",
            "safe_plugin",
            action=action,
            database_outcome="committed" if committed else "rolled-back",
            stdout=StringIO(),
        )
        assert all(path.exists() for path in paths) == (not committed)
        row.refresh_from_db()
        assert ("safe_plugin" not in row.plugin_data) == committed
        assert not list(tmp_path.glob("*.intent.json"))
    finally:
        if isolated is not None:
            isolated.close()
