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
