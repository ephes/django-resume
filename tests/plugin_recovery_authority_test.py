"""Recovery authority over installed targets; synthetic temporary files only."""

import io
import json
import multiprocessing
import os
import shutil
import stat
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from tests.plugin_file_ownership_test import _paths
from tests.plugin_publication_recovery_test import _crashing_create, _kill

INTENT_LIMIT = 131072


def _publication():
    from django_resume.management.commands import _plugin_publication

    return _plugin_publication


def _intent(root: Path) -> Path:
    return root / ".django-resume-plugin-safe_plugin.intent.json"


def _snapshot(root: Path) -> dict:
    result: dict = {}
    for path in sorted(root.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            result[str(path)] = ("link", os.readlink(path))
        elif stat.S_ISDIR(mode):
            result[str(path)] = "dir"
        elif stat.S_ISREG(mode):
            result[str(path)] = path.read_bytes()
        else:
            result[str(path)] = ("special", stat.S_IFMT(mode))
    return result


def _interrupted_create(root: Path, replaced: int = 1, existing: bool = True):
    """Run the real preparation, then stop after ``replaced`` installations."""
    paths = _paths(root)
    staged: dict[Path, Path | None] = {}
    for index, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        if existing:
            path.write_text(f"old {index}")
        stage = path.parent / f".{path.name}.stage-synthetic"
        stage.write_text(f"new {index}")
        staged[path] = stage
    _publication().Publication(paths).prepare(staged)
    for path in paths[:replaced]:
        source = staged[path]
        assert source is not None
        source.replace(path)
    for source in staged.values():
        assert source is not None
        source.unlink(missing_ok=True)
    return paths, json.loads(_intent(root).read_text())


def _interrupted_remove(root: Path):
    paths = _paths(root)
    for index, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"old {index}")
    _publication().Publication(paths).prepare(None, "default")
    for path in paths:
        path.unlink()
    return paths, json.loads(_intent(root).read_text())


def _recover(action: str, **options):
    call_command(
        "recover_plugin", "safe_plugin", action=action, stdout=StringIO(), **options
    )


# --- Intervening target edits (S05) -----------------------------------------


@pytest.mark.parametrize("action", ["restore", "finish"])
@pytest.mark.parametrize("edited", [0, 2])
def test_owner_edit_after_crash_is_never_overwritten(
    tmp_path, monkeypatch, action, edited
):
    monkeypatch.chdir(tmp_path)
    paths = _paths(tmp_path)
    for index, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"old {index}")
    context = multiprocessing.get_context("spawn")
    reached = context.Event()
    # The child dies after installing the first (new) target only.
    _kill(context, _crashing_create, (str(tmp_path), 1, reached), reached)
    intent = json.loads(_intent(tmp_path).read_text())
    paths[edited].write_text("OWNER EDIT AFTER CRASH")
    before = _snapshot(tmp_path)

    with pytest.raises(CommandError, match="neither recorded generation") as error:
        _recover(action)
    assert str(paths[edited]) in str(error.value)
    assert _snapshot(tmp_path) == before

    # Safe manual reconciliation: keep the edit elsewhere, put back a
    # recorded generation, then repeat recovery.
    kept = tmp_path / "owner-edit.keep"
    shutil.copy2(paths[edited], kept)
    generation = "new" if edited == 0 else "old"
    shutil.copy2(intent["files"][edited][generation], paths[edited])
    _recover(action)
    if action == "restore":
        assert [path.read_text() for path in paths] == [f"old {i}" for i in range(3)]
    else:
        assert all("old " not in path.read_text() for path in paths)
    assert kept.read_text() == "OWNER EDIT AFTER CRASH"
    assert not _intent(tmp_path).exists()


@pytest.mark.parametrize(
    "action,outcome", [("restore", "rolled-back"), ("finish", "committed")]
)
def test_removal_recovery_refuses_newly_created_replacement(
    tmp_path, monkeypatch, action, outcome
):
    monkeypatch.chdir(tmp_path)
    paths, intent = _interrupted_remove(tmp_path)
    paths[1].write_text("OWNER REPLACEMENT")
    before = _snapshot(tmp_path)
    with pytest.raises(CommandError, match="neither recorded generation"):
        _recover(action, database_outcome=outcome)
    assert _snapshot(tmp_path) == before
    paths[1].unlink()
    _recover(action, database_outcome=outcome)
    assert all(path.exists() for path in paths) == (action == "restore")
    assert not _intent(tmp_path).exists()


@pytest.mark.parametrize("kind", ["symlink", "directory", "fifo"])
@pytest.mark.parametrize("action", ["restore", "finish"])
def test_unexpected_target_kind_is_refused(tmp_path, monkeypatch, kind, action):
    if kind == "fifo" and not hasattr(os, "mkfifo"):
        pytest.skip("FIFOs unavailable")
    monkeypatch.chdir(tmp_path)
    paths, intent = _interrupted_create(tmp_path, replaced=1)
    target = paths[1]
    target.unlink()
    if kind == "symlink":
        # Even a link to the recorded bytes is a third generation.
        target.symlink_to(intent["files"][1]["old"])
    elif kind == "directory":
        target.mkdir()
    else:
        os.mkfifo(target)
    before = _snapshot(tmp_path)
    # A link resolves elsewhere, so the target set itself no longer matches.
    refusal = (
        "target set does not match"
        if kind == "symlink"
        else "neither recorded generation"
    )
    with pytest.raises(CommandError, match=refusal):
        _recover(action)
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("replaced", [0, 1, 2, 3])
@pytest.mark.parametrize("action", ["restore", "finish"])
@pytest.mark.parametrize("existing", [True, False])
def test_recognized_mixed_states_recover(
    tmp_path, monkeypatch, replaced, action, existing
):
    monkeypatch.chdir(tmp_path)
    paths, _ = _interrupted_create(tmp_path, replaced=replaced, existing=existing)
    _recover(action)
    if action == "finish":
        assert [path.read_text() for path in paths] == [f"new {i}" for i in range(3)]
    elif existing:
        assert [path.read_text() for path in paths] == [f"old {i}" for i in range(3)]
    else:
        assert not any(path.exists() for path in paths)
    assert not _intent(tmp_path).exists()
    assert not [p for p in tmp_path.rglob(".*-*") if p.is_file()]


def test_interrupted_restore_can_be_finished_instead(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths, _ = _interrupted_create(tmp_path, replaced=1)
    replace = Path.replace
    calls = 0

    def fail_second(source, target):
        nonlocal calls
        if ".backup-restore-" in source.name:
            calls += 1
            if calls == 2:
                raise OSError("synthetic interruption")
        return replace(source, target)

    monkeypatch.setattr(Path, "replace", fail_second)
    with pytest.raises(CommandError, match="Recovery incomplete"):
        _recover("restore")
    monkeypatch.setattr(Path, "replace", replace)
    # Last target restored to old, first still new: a recognized mixed state.
    assert paths[2].read_text() == "old 2"
    assert paths[0].read_text() == "new 0"
    _recover("finish")
    assert [path.read_text() for path in paths] == [f"new {i}" for i in range(3)]
    assert not _intent(tmp_path).exists()


def test_target_edited_during_recovery_stops_before_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths, _ = _interrupted_create(tmp_path, replaced=1)
    module = _publication()
    copy_sibling = module.copy_sibling
    edited = False

    def edit_while_staging(source, target, kind):
        nonlocal edited
        if not edited:
            edited = True
            paths[0].write_text("OWNER EDIT DURING RECOVERY")
        return copy_sibling(source, target, kind)

    monkeypatch.setattr(module, "copy_sibling", edit_while_staging)
    with pytest.raises(CommandError, match="neither recorded generation"):
        _recover("restore")
    monkeypatch.setattr(module, "copy_sibling", copy_sibling)
    assert paths[0].read_text() == "OWNER EDIT DURING RECOVERY"
    assert _intent(tmp_path).exists()
    assert not list(tmp_path.rglob("*.backup-restore-*"))
    paths[0].write_text("new 0")
    _recover("restore")
    assert [path.read_text() for path in paths] == [f"old {i}" for i in range(3)]


def test_authority_copy_changed_while_staging_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths, _ = _interrupted_create(tmp_path, replaced=1)
    module = _publication()
    copy_sibling = module.copy_sibling

    def corrupt(source, target, kind):
        copy = copy_sibling(source, target, kind)
        copy.write_text("synthetic corruption")
        return copy

    before = _snapshot(tmp_path)
    monkeypatch.setattr(module, "copy_sibling", corrupt)
    with pytest.raises(CommandError, match="recovery copy changed"):
        _recover("finish")
    assert _snapshot(tmp_path) == before


def test_in_process_rollback_refuses_third_generation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths = _paths(tmp_path)
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("old")
    staged: dict[Path, Path | None] = {}
    for path in paths:
        staged[path] = path.parent / f".{path.name}.stage-synthetic"
        staged[path].write_text("new")  # type: ignore[union-attr]
    with pytest.raises(CommandError, match="rollback incomplete") as error:
        with _publication().publication_files(paths, staged):
            paths[1].write_text("CONCURRENT OWNER EDIT")
            raise OSError("synthetic body failure")
    assert "neither recorded generation" in str(error.value)
    assert paths[1].read_text() == "CONCURRENT OWNER EDIT"
    assert _intent(tmp_path).exists()


# --- One bounded regular intent read (S06) ----------------------------------


def _recover_in_child(root, action, queue):
    os.environ["DJANGO_SETTINGS_MODULE"] = "tests.settings"
    import django

    django.setup()
    from django.core.management import call_command as command
    from django.core.management.base import CommandError as Refusal

    os.chdir(root)
    try:
        command("recover_plugin", "safe_plugin", action=action, stdout=StringIO())
        queue.put("ok")
    except Refusal as error:
        queue.put(f"CommandError: {error}")
    except BaseException as error:  # report, never hang the parent
        queue.put(f"{type(error).__name__}: {error}")


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="FIFOs unavailable")
@pytest.mark.parametrize("action", ["status", "restore", "finish"])
def test_fifo_intent_is_refused_without_blocking(tmp_path, monkeypatch, action):
    monkeypatch.chdir(tmp_path)
    _interrupted_create(tmp_path, replaced=1)
    _intent(tmp_path).unlink()
    os.mkfifo(_intent(tmp_path))
    before = _snapshot(tmp_path)
    context = multiprocessing.get_context("spawn")
    queue = context.Queue()
    process = context.Process(
        target=_recover_in_child, args=(str(tmp_path), action, queue)
    )
    process.start()
    try:
        process.join(15)
        assert not process.is_alive(), "recovery blocked on a FIFO intent"
        result = queue.get(timeout=5)
    finally:
        if process.is_alive():
            process.kill()
        process.join(5)
    assert result.startswith("CommandError: Cannot read recovery intent"), result
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("kind", ["symlink", "directory"])
@pytest.mark.parametrize("action", ["status", "restore"])
def test_nonregular_intent_is_refused(tmp_path, monkeypatch, kind, action):
    monkeypatch.chdir(tmp_path)
    _interrupted_create(tmp_path, replaced=1)
    intent = _intent(tmp_path)
    real = tmp_path / "elsewhere.json"
    intent.replace(real)
    if kind == "symlink":
        intent.symlink_to(real)
    else:
        intent.mkdir()
    before = _snapshot(tmp_path)
    output = StringIO()
    with pytest.raises(CommandError, match="Cannot read recovery intent"):
        call_command("recover_plugin", "safe_plugin", action=action, stdout=output)
    assert output.getvalue() == ""
    assert _snapshot(tmp_path) == before


def _pad(intent: Path, size: int) -> bytes:
    raw = intent.read_bytes()
    padded = raw + b" " * (size - len(raw))
    intent.write_bytes(padded)
    return padded


def test_intent_at_exact_limit_is_admitted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    paths, _ = _interrupted_create(tmp_path, replaced=1)
    padded = _pad(_intent(tmp_path), INTENT_LIMIT)
    output = StringIO()
    call_command("recover_plugin", "safe_plugin", action="status", stdout=output)
    assert output.getvalue() == padded.decode() + "\n"
    _recover("finish")
    assert [path.read_text() for path in paths] == [f"new {i}" for i in range(3)]


@pytest.mark.parametrize("action", ["status", "restore"])
def test_intent_over_limit_is_refused(tmp_path, monkeypatch, action):
    monkeypatch.chdir(tmp_path)
    _interrupted_create(tmp_path, replaced=1)
    _pad(_intent(tmp_path), INTENT_LIMIT + 1)
    before = _snapshot(tmp_path)
    output = StringIO()
    with pytest.raises(CommandError, match="Cannot read recovery intent"):
        call_command("recover_plugin", "safe_plugin", action=action, stdout=output)
    assert output.getvalue() == ""
    assert _snapshot(tmp_path) == before


def test_growth_after_size_check_cannot_exceed_byte_cap(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _interrupted_create(tmp_path, replaced=1)
    intent = _intent(tmp_path)
    # A valid record that grew beyond the cap after any size observation.
    _pad(intent, 4 * INTENT_LIMIT)
    identity = (intent.stat().st_dev, intent.stat().st_ino)

    def small(result):
        if (result.st_dev, result.st_ino) != identity:
            return result
        values = list(result[:10])
        values[stat.ST_SIZE] = 64
        return os.stat_result(values)

    fstat, path_stat = os.fstat, Path.stat
    monkeypatch.setattr(os, "fstat", lambda fd: small(fstat(fd)))
    monkeypatch.setattr(Path, "stat", lambda self, **kw: small(path_stat(self, **kw)))
    read, consumed = os.read, 0

    def counted(fd, size):
        nonlocal consumed
        chunk = read(fd, size)
        if (fstat(fd).st_dev, fstat(fd).st_ino) == identity:
            consumed += len(chunk)
        return chunk

    monkeypatch.setattr(os, "read", counted)
    before = _snapshot(tmp_path)
    with pytest.raises(CommandError, match="Cannot read recovery intent"):
        _recover("finish")
    assert consumed <= INTENT_LIMIT + 1
    assert _snapshot(tmp_path) == before


def test_intent_changed_while_reading_is_refused(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _interrupted_create(tmp_path, replaced=1)
    intent = _intent(tmp_path)
    identity = (intent.stat().st_dev, intent.stat().st_ino)
    read, appended = os.read, False

    def grow(fd, size):
        nonlocal appended
        chunk = read(fd, size)
        info = os.fstat(fd)
        if not appended and (info.st_dev, info.st_ino) == identity:
            appended = True
            with intent.open("ab") as output:
                output.write(b" " * 16)
        return chunk

    monkeypatch.setattr(os, "read", grow)
    before = _snapshot(tmp_path)
    with pytest.raises(CommandError, match="changed while reading"):
        _recover("restore")
    assert appended
    # Only the concurrent writer's append changed anything.
    before[str(intent)] += b" " * 16
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize(
    "payload",
    [
        b"[" * 60000,
        b'{"version": 1, ' * 4000,
        b"\xff\xfe not utf-8",
        b"[]",
        b'{"version": 1, "operation": "create", "files": [1, 2, 3]}',
        b'{"version": 1, "operation": "create", "files": "abc"}',
        b'{"version": 1, "operation": ["create"], "files": []}',
        b'{"version": 1, "operation": "create", "files": [{"path": "a\\u0000"}]}',
        b"1" * 5000,
    ],
    ids=[
        "deep-array",
        "deep-object",
        "not-utf8",
        "not-object",
        "entries-not-objects",
        "files-not-list",
        "operation-unhashable",
        "nul-path",
        "huge-integer",
    ],
)
@pytest.mark.parametrize("action", ["status", "restore", "finish"])
def test_malformed_or_excessive_intent_is_refused(
    tmp_path, monkeypatch, payload, action
):
    monkeypatch.chdir(tmp_path)
    _interrupted_create(tmp_path, replaced=1)
    _intent(tmp_path).write_bytes(payload)
    before = _snapshot(tmp_path)
    output = StringIO()
    with pytest.raises(CommandError, match="Cannot read recovery intent"):
        call_command("recover_plugin", "safe_plugin", action=action, stdout=output)
    if action == "status":
        # The admitted bytes are shown for manual reconciliation.
        assert output.getvalue() == payload.decode(errors="replace") + "\n"
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("valid", [True, False])
def test_status_reads_the_intent_exactly_once(tmp_path, monkeypatch, valid):
    monkeypatch.chdir(tmp_path)
    _, record = _interrupted_create(tmp_path, replaced=1)
    intent = _intent(tmp_path)
    if not valid:
        Path(record["files"][0]["old"]).unlink()
    opened = []
    os_open, io_open = os.open, io.open

    def count_os(path, *args, **kwargs):
        if Path(path) == intent:
            opened.append("os")
        return os_open(path, *args, **kwargs)

    def count_io(file, *args, **kwargs):
        if not isinstance(file, int) and Path(file) == intent:
            opened.append("io")
        return io_open(file, *args, **kwargs)

    monkeypatch.setattr(os, "open", count_os)
    monkeypatch.setattr(io, "open", count_io)
    output = StringIO()
    if valid:
        call_command("recover_plugin", "safe_plugin", action="status", stdout=output)
    else:
        with pytest.raises(CommandError, match="invalid recovery copy"):
            call_command(
                "recover_plugin", "safe_plugin", action="status", stdout=output
            )
    assert len(opened) == 1
    assert json.loads(output.getvalue()) == record


@pytest.mark.parametrize(
    ("boundary", "replace_file"),
    [("load", True), ("load", False), ("retire", True)],
    ids=["same-bytes-new-file", "edit-in-place", "before-retirement"],
)
def test_recovery_keeps_changed_intent_and_copies(
    tmp_path, monkeypatch, boundary, replace_file
):
    monkeypatch.chdir(tmp_path)
    paths, _ = _interrupted_create(tmp_path, replaced=1)
    intent = _intent(tmp_path)
    before = _snapshot(tmp_path)
    publication = _publication().Publication
    original = getattr(publication, boundary)
    replacement_bytes = before[str(intent)]
    if boundary == "retire" or not replace_file:
        replacement_bytes += b" "

    def change_intent(pending):
        if boundary == "load":
            original(pending)
        if replace_file:
            replacement = tmp_path / "replacement"
            replacement.write_bytes(replacement_bytes)
            replacement.replace(intent)
        else:
            intent.write_bytes(replacement_bytes)
        if boundary == "retire":
            original(pending)

    monkeypatch.setattr(publication, boundary, change_intent)
    output = StringIO()
    with pytest.raises(CommandError, match="recovery intent changed"):
        call_command("recover_plugin", "safe_plugin", action="finish", stdout=output)

    assert output.getvalue() == ""
    before[str(intent)] = replacement_bytes
    if boundary == "retire":
        for index, path in enumerate(paths):
            before[str(path)] = f"new {index}".encode()
    assert _snapshot(tmp_path) == before


@pytest.mark.parametrize("sync_fails", [False, True])
def test_recovery_keeps_intent_created_during_retirement_sync(
    tmp_path, monkeypatch, sync_fails
):
    monkeypatch.chdir(tmp_path)
    paths, _ = _interrupted_create(tmp_path, replaced=1)
    intent = _intent(tmp_path)
    before = _snapshot(tmp_path)
    replacement_bytes = before[str(intent)] + b" "
    sync_directory = _publication().sync_directory

    def replace_after_unlink(directory):
        if directory == intent.parent and not intent.exists():
            intent.write_bytes(replacement_bytes)
            if sync_fails:
                raise OSError("retirement sync failed")
        sync_directory(directory)

    monkeypatch.setattr(_publication(), "sync_directory", replace_after_unlink)
    output = StringIO()
    with pytest.raises(
        CommandError, match="recovery intent changed|retirement sync failed"
    ):
        call_command("recover_plugin", "safe_plugin", action="finish", stdout=output)

    assert output.getvalue() == ""
    before[str(intent)] = replacement_bytes
    for index, path in enumerate(paths):
        before[str(path)] = f"new {index}".encode()
    assert _snapshot(tmp_path) == before


def test_recovery_keeps_intent_replaced_between_recheck_and_retirement(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    paths, _ = _interrupted_create(tmp_path, replaced=1)
    intent = _intent(tmp_path)
    before = _snapshot(tmp_path)
    replacement_bytes = before[str(intent)] + b" "
    publication = _publication().Publication
    original_retire = publication.retire
    original_check = publication._require_admitted_intent
    retiring = False

    def retire(pending):
        nonlocal retiring
        retiring = True
        original_retire(pending)

    def check_then_replace(pending):
        original_check(pending)
        if retiring:
            # A replacement lands after the last check, right before the
            # intent is taken out of view.
            replacement = tmp_path / "replacement"
            replacement.write_bytes(replacement_bytes)
            replacement.replace(intent)

    monkeypatch.setattr(publication, "retire", retire)
    monkeypatch.setattr(publication, "_require_admitted_intent", check_then_replace)
    output = StringIO()
    with pytest.raises(CommandError, match="recovery intent changed"):
        call_command("recover_plugin", "safe_plugin", action="finish", stdout=output)

    assert output.getvalue() == ""
    before[str(intent)] = replacement_bytes
    for index, path in enumerate(paths):
        before[str(path)] = f"new {index}".encode()
    assert _snapshot(tmp_path) == before


def test_recovery_keeps_set_aside_intent_when_its_path_is_taken(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _interrupted_create(tmp_path, replaced=1)
    intent = _intent(tmp_path)
    admitted = intent.read_bytes()
    module = _publication()
    original_read = module.read_intent

    def read_aside(path):
        if ".retiring-" in path.name:
            # The pathname is reused while the changed intent is set aside.
            intent.write_bytes(admitted + b"  ")
            return b"changed", (0, 0, 0, 0, 0, 0)
        return original_read(path)

    monkeypatch.setattr(module, "read_intent", read_aside)
    with pytest.raises(CommandError, match="changed intent was kept at") as raised:
        call_command(
            "recover_plugin", "safe_plugin", action="finish", stdout=StringIO()
        )

    asides = list(tmp_path.glob(f"{intent.name}.retiring-*"))
    assert len(asides) == 1
    assert str(asides[0]) in str(raised.value)
    assert asides[0].read_bytes() == admitted
    assert intent.read_bytes() == admitted + b"  "
