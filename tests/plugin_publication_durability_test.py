"""Fault the real publication I/O boundaries; all inputs are temporary source."""

import json
import os
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from tests.management_commands_test import plugin_bundle
from tests.plugin_file_ownership_test import _paths


@pytest.fixture
def tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for path in _paths(tmp_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("old")
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    return tmp_path


def test_all_generation_bytes_are_synced_before_first_replacement(tree, monkeypatch):
    from django_resume.management.commands import _plugin_publication as publication

    synced = set()
    fsync, replace = os.fsync, Path.replace
    targets = _paths(tree)

    def record(fd):
        info = os.fstat(fd)
        synced.add((info.st_dev, info.st_ino))
        return fsync(fd)

    def checked_replace(source, target):
        if target in targets and ".stage-" in source.name:
            intent = json.loads(publication.intent_path(targets).read_text())
            files = [source] + [
                Path(entry[key]) for entry in intent["files"] for key in ["old", "new"]
            ]
            assert all((p.stat().st_dev, p.stat().st_ino) in synced for p in files)
        return replace(source, target)

    monkeypatch.setattr(os, "fsync", record)
    monkeypatch.setattr(Path, "replace", checked_replace)
    call_command("create_plugin_from_stdin", stdout=StringIO())


@pytest.mark.parametrize("failure", range(1, 10))
def test_each_generation_file_sync_failure_is_prepublication(
    tree, monkeypatch, failure
):
    from django_resume.management.commands import _plugin_publication as publication

    sync = publication.sync_file
    calls = 0

    def fail(path):
        nonlocal calls
        calls += 1
        if calls == failure:
            raise OSError("synthetic file sync failure")
        return sync(path)

    monkeypatch.setattr(publication, "sync_file", fail)
    with pytest.raises(CommandError, match="synthetic file sync failure"):
        call_command("create_plugin_from_stdin", stdout=StringIO())
    assert calls == failure
    assert [path.read_text() for path in _paths(tree)] == ["old"] * 3
    assert not list(tree.rglob("*.intent.json"))
    assert not list(tree.rglob(".*.backup-*"))
    assert not list(tree.rglob(".*.new-*"))
    assert not list(tree.rglob(".*.stage-*"))


def test_intent_file_sync_failure_keeps_installed_generation(tree, monkeypatch):
    import stat

    fsync = os.fsync
    files = 0

    def fail(fd):
        nonlocal files
        if stat.S_ISREG(os.fstat(fd).st_mode):
            files += 1
            # Three stages and six authority copies precede the intent.
            if files == 10:
                raise OSError("synthetic intent sync failure")
        return fsync(fd)

    monkeypatch.setattr(os, "fsync", fail)
    with pytest.raises(CommandError, match="synthetic intent sync failure"):
        call_command("create_plugin_from_stdin", stdout=StringIO())
    assert [path.read_text() for path in _paths(tree)] == ["old"] * 3
    assert not list(tree.rglob("*.intent.json"))
    assert not list(tree.rglob(".plugin-intent-*"))


def test_fault_every_directory_sync_retains_truthful_outcome(tmp_path, monkeypatch):
    from django_resume.management.commands import _plugin_publication as publication

    sync, replace = publication.sync_directory, Path.replace

    def run(root, failure=None):
        paths = _paths(root)
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("old")
        directories, replaced = [], []
        tripped = False

        def record_sync(directory):
            nonlocal tripped
            directories.append(directory)
            if len(directories) == failure:
                tripped = True
                raise OSError("synthetic directory sync failure")
            return sync(directory)

        def record_replace(source, target):
            result = replace(source, target)
            if target in paths and ".stage-" in source.name:
                replaced.append(target)
            return result

        with monkeypatch.context() as patch:
            patch.chdir(root)
            patch.setattr("sys.stdin", StringIO(plugin_bundle()))
            patch.setattr(publication, "sync_directory", record_sync)
            patch.setattr(Path, "replace", record_replace)
            if failure is None:
                call_command("create_plugin_from_stdin", stdout=StringIO())
                # Parent directory entries must be synced before intent retirement.
                assert set(path.parent for path in paths) <= set(directories)
                return len(directories)
            with pytest.raises(CommandError) as error:
                call_command("create_plugin_from_stdin", stdout=StringIO())
            assert tripped
            intent = publication.intent_path(paths)
            if replaced:
                assert "visible but durability uncertain" in str(error.value)
                assert len(replaced) == 3
                assert all("new" in path.read_text() for path in paths)
                assert intent.is_file()
            else:
                assert [path.read_text() for path in paths] == ["old"] * 3
            if intent.exists():
                record = json.loads(intent.read_text())
                assert all(
                    Path(entry[key]).is_file()
                    for entry in record["files"]
                    for key in ["old", "new"]
                )
                patch.setattr("sys.stdin", StringIO(plugin_bundle()))
                with pytest.raises(
                    CommandError, match="[Ii]nterrupted plugin publication"
                ):
                    call_command("create_plugin_from_stdin", stdout=StringIO())
                # Restore/finish are both deterministic even after uncertain sync.
                call_command(
                    "recover_plugin", "safe_plugin", action="finish", stdout=StringIO()
                )
                assert all("new" in path.read_text() for path in paths)
            return len(directories)

    count = run(tmp_path / "baseline")
    assert count > 3
    for boundary in range(1, count + 1):
        run(tmp_path / f"fault-{boundary}", failure=boundary)


@pytest.mark.parametrize("failure", [1, 2, 3])
def test_each_replace_failure_restores_synced_old_generation(
    tree, monkeypatch, failure
):
    replace = Path.replace
    calls = 0

    def fail(source, target):
        nonlocal calls
        if target in _paths(tree) and ".stage-" in source.name:
            calls += 1
            if calls == failure:
                raise OSError("synthetic replace failure")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(CommandError, match="synthetic replace failure"):
        call_command("create_plugin_from_stdin", stdout=StringIO())
    assert [path.read_text() for path in _paths(tree)] == ["old"] * 3
    assert not list(tree.rglob("*.intent.json"))


@pytest.mark.django_db(transaction=True)
def test_remove_rejects_enclosing_application_transaction(tree):
    from django.db import transaction

    with transaction.atomic():
        with pytest.raises(RuntimeError, match="durable atomic block cannot be nested"):
            call_command("remove_plugin_by_name", "safe_plugin", stdout=StringIO())
    assert [path.read_text() for path in _paths(tree)] == ["old"] * 3
    assert not list(tree.glob("*.intent.json"))


def test_rollback_retirement_sync_failure_names_retained_authority(tree, monkeypatch):
    from django_resume.management.commands import _plugin_publication as publication

    sync, replace = publication.sync_directory, Path.replace
    failed = False

    def fail_replace(source, target):
        nonlocal failed
        if target == _paths(tree)[1] and not failed:
            failed = True
            raise OSError("primary replacement failure")
        return replace(source, target)

    def fail_retirement(directory):
        if failed and not publication.intent_path(_paths(tree)).exists():
            raise OSError("retirement sync failure")
        return sync(directory)

    monkeypatch.setattr(Path, "replace", fail_replace)
    monkeypatch.setattr(publication, "sync_directory", fail_retirement)
    with pytest.raises(
        CommandError, match="primary replacement failure; rollback incomplete"
    ) as error:
        call_command("create_plugin_from_stdin", stdout=StringIO())
    assert [path.read_text() for path in _paths(tree)] == ["old"] * 3
    intent_path = publication.intent_path(_paths(tree))
    assert str(intent_path) in str(error.value)
    intent = json.loads(intent_path.read_text())
    assert all(
        Path(entry[key]).is_file()
        for entry in intent["files"]
        for key in ["old", "new"]
    )


def test_visible_intent_sync_failure_names_retained_blocker(tree, monkeypatch):
    from django_resume.management.commands import _plugin_publication as publication

    sync = publication.sync_directory
    intent = publication.intent_path(_paths(tree))

    def fail(directory):
        if intent.exists():
            raise OSError("synthetic intent directory sync failure")
        return sync(directory)

    monkeypatch.setattr(publication, "sync_directory", fail)
    with pytest.raises(CommandError) as error:
        call_command("create_plugin_from_stdin", stdout=StringIO())
    message = str(error.value)
    assert "synthetic intent directory sync failure" in message
    assert "Plugin files unchanged, but recovery intent retained" in message
    assert str(intent) in message
    assert "recover_plugin safe_plugin --action status" in message
    assert "--database-outcome" not in message
    assert [path.read_text() for path in _paths(tree)] == ["old"] * 3
    assert intent.is_file()
    monkeypatch.setattr(publication, "sync_directory", sync)
    call_command("recover_plugin", "safe_plugin", action="restore", stdout=StringIO())
    assert [path.read_text() for path in _paths(tree)] == ["old"] * 3
    assert not intent.exists()


@pytest.mark.django_db(transaction=True)
def test_visible_removal_intent_hint_names_untouched_database(tree, monkeypatch):
    from django_resume.management.commands import _plugin_publication as publication

    sync = publication.sync_directory
    intent = publication.intent_path(_paths(tree))

    def fail(directory):
        if intent.exists():
            raise OSError("synthetic intent directory sync failure")
        return sync(directory)

    monkeypatch.setattr(publication, "sync_directory", fail)
    with pytest.raises(CommandError, match="--database-outcome rolled-back"):
        call_command("remove_plugin_by_name", "safe_plugin", stdout=StringIO())
    assert [path.read_text() for path in _paths(tree)] == ["old"] * 3
    monkeypatch.setattr(publication, "sync_directory", sync)
    call_command(
        "recover_plugin",
        "safe_plugin",
        action="restore",
        database_outcome="rolled-back",
        stdout=StringIO(),
    )
    assert [path.read_text() for path in _paths(tree)] == ["old"] * 3
    assert not intent.exists()


@pytest.mark.django_db(transaction=True)
def test_committed_removal_sync_failure_names_finish_assertion(tree, monkeypatch):
    from django_resume.management.commands import _plugin_publication as publication

    sync = publication.sync_directory
    intent = publication.intent_path(_paths(tree))

    def fail(directory):
        if intent.exists() and not any(path.exists() for path in _paths(tree)):
            raise OSError("synthetic post-commit sync failure")
        return sync(directory)

    monkeypatch.setattr(publication, "sync_directory", fail)
    with pytest.raises(
        CommandError,
        match="committed: use --action finish --database-outcome committed",
    ):
        call_command("remove_plugin_by_name", "safe_plugin", stdout=StringIO())
    assert intent.is_file()
    monkeypatch.setattr(publication, "sync_directory", sync)
    call_command(
        "recover_plugin",
        "safe_plugin",
        action="finish",
        database_outcome="committed",
        stdout=StringIO(),
    )
    assert not any(path.exists() for path in _paths(tree))
    assert not intent.exists()


def test_symlinked_templates_keep_intent_in_project_root(tmp_path, monkeypatch):
    from django_resume.management.commands import _plugin_publication as publication

    project = tmp_path / "project"
    shared = tmp_path / "shared-templates"
    (project / "core/plugins").mkdir(parents=True)
    shared.mkdir()
    (project / "templates").symlink_to(shared, target_is_directory=True)
    monkeypatch.chdir(project)
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    root = project.resolve()
    intent = root / ".django-resume-plugin-safe_plugin.intent.json"
    sync, replace = publication.sync_directory, Path.replace
    synced, seen = [], []

    def record_sync(directory):
        synced.append(Path(directory).resolve())
        return sync(directory)

    def checked_replace(source, target):
        if ".stage-" in source.name:
            seen.append(intent.is_file())
        return replace(source, target)

    monkeypatch.setattr(publication, "sync_directory", record_sync)
    monkeypatch.setattr(Path, "replace", checked_replace)
    call_command("create_plugin_from_stdin", stdout=StringIO())
    assert seen == [True] * 3
    assert not intent.exists()
    assert not list(tmp_path.glob("*.intent.json"))
    resolved_shared = shared.resolve()
    assert all(
        directory == root
        or directory.is_relative_to(root)
        or directory.is_relative_to(resolved_shared)
        for directory in synced
    )
    assert resolved_shared in synced
    assert (shared / "django_resume/plugins/safe_plugin/plain/form.html").is_file()


def test_fresh_project_syncs_every_created_parent(tmp_path, monkeypatch):
    from django_resume.management.commands import _plugin_publication as publication

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    root = tmp_path.resolve()
    sync = publication.sync_directory
    synced = set()

    def record_sync(directory):
        synced.add(Path(directory).resolve())
        return sync(directory)

    monkeypatch.setattr(publication, "sync_directory", record_sync)
    call_command("create_plugin_from_stdin", stdout=StringIO())
    # Every directory whose entry list gained a created child must be synced.
    expected = {root, root / "core", root / "core/plugins", root / "templates"}
    plain = root / "templates/django_resume/plugins/safe_plugin/plain"
    expected |= {plain, *[p for p in plain.parents if p.is_relative_to(root)]}
    assert expected <= synced
