from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from django_resume.models import Resume


def test_create_plugin_from_stdin_rejects_unsafe_plugin_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(
            "\n".join(
                [
                    "===../../escape===",
                    "===../../escape.py===",
                    "print('escape')",
                    "===django_resume/plugins/../../escape/plain/content.html===",
                    "<div>escape</div>",
                    "===django_resume/plugins/../../escape/plain/form.html===",
                    "<form></form>",
                ]
            )
        ),
    )

    with pytest.raises(CommandError, match="Invalid plugin name"):
        call_command("create_plugin_from_stdin")

    assert not (tmp_path / "escape.py").exists()


def test_create_plugin_from_stdin_creates_files_for_valid_plugin_name(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    plugin_name = "safe_plugin"
    monkeypatch.setattr(
        "sys.stdin",
        StringIO(
            "\n".join(
                [
                    f"==={plugin_name}===",
                    f"==={plugin_name}.py===",
                    "print('safe')",
                    f"===django_resume/plugins/{plugin_name}/plain/content.html===",
                    "<div>safe</div>",
                    f"===django_resume/plugins/{plugin_name}/plain/form.html===",
                    "<form></form>",
                ]
            )
        ),
    )

    call_command("create_plugin_from_stdin")

    assert (
        tmp_path / "core" / "plugins" / f"{plugin_name}.py"
    ).read_text().strip() == "print('safe')"
    assert (
        tmp_path
        / "templates"
        / "django_resume"
        / "plugins"
        / plugin_name
        / "plain"
        / "content.html"
    ).read_text().strip() == "<div>safe</div>"


@pytest.mark.django_db
def test_remove_plugin_by_name_rejects_unsafe_plugin_name(tmp_path, monkeypatch, user):
    monkeypatch.chdir(tmp_path)
    user.save()
    Resume.objects.create(
        name="Test Resume",
        slug="test-resume",
        owner=user,
        plugin_data={"safe_plugin": {"title": "Safe"}},
    )
    outside_file = tmp_path / "keep.txt"
    outside_file.write_text("keep")

    with pytest.raises(CommandError, match="Invalid plugin name"):
        call_command("remove_plugin_by_name", "../../keep")

    assert outside_file.read_text() == "keep"
    assert Resume.objects.get(slug="test-resume").plugin_data == {
        "safe_plugin": {"title": "Safe"}
    }


@pytest.mark.django_db
def test_remove_plugin_by_name_removes_plugin_files_and_resume_data(
    tmp_path, monkeypatch, user
):
    monkeypatch.chdir(tmp_path)
    user.save()
    plugin_name = "safe_plugin"
    Resume.objects.create(
        name="Test Resume",
        slug="test-resume",
        owner=user,
        plugin_data={plugin_name: {"title": "Safe"}, "about": {"title": "About"}},
    )
    plugin_file = tmp_path / "core" / "plugins" / f"{plugin_name}.py"
    content_template = (
        tmp_path
        / "templates"
        / "django_resume"
        / "plugins"
        / plugin_name
        / "plain"
        / "content.html"
    )
    form_template = (
        tmp_path
        / "templates"
        / "django_resume"
        / "plugins"
        / plugin_name
        / "plain"
        / "form.html"
    )
    plugin_file.parent.mkdir(parents=True, exist_ok=True)
    content_template.parent.mkdir(parents=True, exist_ok=True)
    plugin_file.write_text("print('safe')")
    content_template.write_text("<div>safe</div>")
    form_template.write_text("<form></form>")

    call_command("remove_plugin_by_name", plugin_name)

    assert not plugin_file.exists()
    assert not content_template.exists()
    assert not form_template.exists()
    assert Resume.objects.get(slug="test-resume").plugin_data == {
        "about": {"title": "About"}
    }


def plugin_files(tmp_path):
    return [
        tmp_path / "core/plugins/safe_plugin.py",
        tmp_path / "templates/django_resume/plugins/safe_plugin/plain/content.html",
        tmp_path / "templates/django_resume/plugins/safe_plugin/plain/form.html",
    ]


@pytest.fixture
def stored_plugin(tmp_path, monkeypatch, user, db):
    monkeypatch.chdir(tmp_path)
    user.save()
    resume = Resume.objects.create(
        name="Test",
        slug="test",
        owner=user,
        plugin_data={"safe_plugin": {"title": "Safe"}, "about": {"title": "About"}},
    )
    paths = plugin_files(tmp_path)
    for index, path in enumerate(paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"original {index}".encode())
    return resume, paths


@pytest.mark.parametrize("target", [1, 2])
def test_remove_preflights_all_paths(stored_plugin, tmp_path, target):
    resume, paths = stored_plugin
    original_data = resume.plugin_data.copy()
    outside = tmp_path / "outside.html"
    outside.write_bytes(b"outside")
    paths[target].unlink()
    paths[target].symlink_to(outside)
    with pytest.raises(CommandError, match="escapes"):
        call_command("remove_plugin_by_name", "safe_plugin")
    resume.refresh_from_db()
    assert resume.plugin_data == original_data
    assert paths[0].read_bytes() == b"original 0"
    assert paths[target].is_symlink()
    assert outside.read_bytes() == b"outside"


def test_remove_restores_files_and_data_on_unlink_failure(stored_plugin, monkeypatch):
    from pathlib import Path

    resume, paths = stored_plugin
    original_data = resume.plugin_data.copy()
    unlink = Path.unlink
    failures = []

    def fail_second(path, *args, **kwargs):
        if path == paths[1]:
            failures.append(path)
            raise OSError("injected unlink failure")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_second)
    with pytest.raises(CommandError, match="injected unlink failure"):
        call_command("remove_plugin_by_name", "safe_plugin")
    assert failures == [paths[1]]
    resume.refresh_from_db()
    assert resume.plugin_data == original_data
    assert [path.read_bytes() for path in paths] == [
        b"original 0",
        b"original 1",
        b"original 2",
    ]


def test_remove_restores_files_on_database_failure(stored_plugin, monkeypatch):
    resume, paths = stored_plugin
    original_data = resume.plugin_data.copy()
    from django_resume.models import ResumeManager

    remove = ResumeManager.remove_plugin_data_by_name

    def fail_after_update(manager, name):
        remove(manager, name)
        raise RuntimeError("injected database failure")

    monkeypatch.setattr(ResumeManager, "remove_plugin_data_by_name", fail_after_update)
    with pytest.raises(RuntimeError, match="database failure"):
        call_command("remove_plugin_by_name", "safe_plugin")
    resume.refresh_from_db()
    assert resume.plugin_data == original_data
    assert all(path.exists() for path in paths)


def plugin_bundle(omit=None):
    sections = {
        "safe_plugin.py": "print('new')",
        "django_resume/plugins/safe_plugin/plain/content.html": "<div>new</div>",
        "django_resume/plugins/safe_plugin/plain/form.html": "<form>new</form>---explanation",
    }
    return "===safe_plugin===\n" + "\n".join(
        f"==={name}===\n{source}" for name, source in sections.items() if name != omit
    )


@pytest.mark.parametrize(
    "missing",
    [
        "safe_plugin.py",
        "django_resume/plugins/safe_plugin/plain/content.html",
        "django_resume/plugins/safe_plugin/plain/form.html",
    ],
)
def test_create_rejects_missing_sections_without_writing(
    stored_plugin, monkeypatch, missing
):
    _, paths = stored_plugin
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle(omit=missing)))
    with pytest.raises(CommandError, match="Missing required section"):
        call_command("create_plugin_from_stdin")
    assert [path.read_bytes() for path in paths] == [
        b"original 0",
        b"original 1",
        b"original 2",
    ]


@pytest.mark.parametrize("target", [1, 2])
def test_create_preflights_all_paths(stored_plugin, tmp_path, monkeypatch, target):
    _, paths = stored_plugin
    outside = tmp_path / "outside.html"
    outside.write_bytes(b"outside")
    paths[target].unlink()
    paths[target].symlink_to(outside)
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    with pytest.raises(CommandError, match="escapes"):
        call_command("create_plugin_from_stdin")
    assert paths[0].read_bytes() == b"original 0"
    assert paths[target].is_symlink()
    assert outside.read_bytes() == b"outside"


@pytest.mark.parametrize("existing", [False, True])
def test_create_rolls_back_replacement_failure(tmp_path, monkeypatch, existing):
    from pathlib import Path

    monkeypatch.chdir(tmp_path)
    paths = plugin_files(tmp_path)
    if existing:
        for index, path in enumerate(paths):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"original {index}".encode())
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    replace = Path.replace
    failures = []

    def fail_second(path, target):
        if target == paths[1] and not failures:
            failures.append(target)
            raise OSError("injected replacement failure")
        return replace(path, target)

    monkeypatch.setattr(Path, "replace", fail_second)
    with pytest.raises(CommandError, match="replacement failure"):
        call_command("create_plugin_from_stdin")
    assert failures == [paths[1]]
    if existing:
        assert [path.read_bytes() for path in paths] == [
            b"original 0",
            b"original 1",
            b"original 2",
        ]
    else:
        assert not any(path.exists() for path in paths)
    assert not list(tmp_path.rglob(".*.backup-*"))
    assert not list(tmp_path.rglob(".*.stage-*"))


def test_create_replaces_complete_bundle(stored_plugin, monkeypatch):
    _, paths = stored_plugin
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    call_command("create_plugin_from_stdin")
    assert [path.read_text().strip() for path in paths] == [
        "print('new')",
        "<div>new</div>",
        "<form>new</form>",
    ]


@pytest.mark.parametrize("bundle", ["", "not a bundle", "===safe_plugin==="])
def test_create_rejects_malformed_bundle(tmp_path, monkeypatch, bundle):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", StringIO(bundle))
    with pytest.raises(CommandError):
        call_command("create_plugin_from_stdin")
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "command", ["create_plugin_from_stdin", "remove_plugin_by_name"]
)
def test_plugin_commands_reject_aliased_targets(stored_plugin, monkeypatch, command):
    _, paths = stored_plugin
    paths[2].unlink()
    paths[2].symlink_to(paths[1])
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    args = ("safe_plugin",) if command == "remove_plugin_by_name" else ()
    with pytest.raises(CommandError, match="distinct files"):
        call_command(command, *args)
    assert paths[0].read_bytes() == b"original 0"
    assert paths[1].read_bytes() == b"original 1"
    assert paths[2].is_symlink()


@pytest.mark.parametrize(
    "command", ["create_plugin_from_stdin", "remove_plugin_by_name"]
)
def test_plugin_commands_leave_originals_on_backup_failure(
    stored_plugin, monkeypatch, command
):
    import shutil

    _, paths = stored_plugin
    copy = shutil.copy2
    failures = []

    def fail_copy(source, target):
        if source == paths[1]:
            failures.append(source)
            raise OSError("injected backup failure")
        return copy(source, target)

    monkeypatch.setattr(shutil, "copy2", fail_copy)
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    args = ("safe_plugin",) if command == "remove_plugin_by_name" else ()
    with pytest.raises(CommandError, match="backup failure"):
        call_command(command, *args)
    assert failures == [paths[1]]
    assert [path.read_bytes() for path in paths] == [
        b"original 0",
        b"original 1",
        b"original 2",
    ]
    assert not list(paths[0].parents[2].rglob(".*.backup-*"))


def test_remove_reports_retained_backup_on_restore_failure(stored_plugin, monkeypatch):
    from pathlib import Path

    resume, paths = stored_plugin
    original_data = resume.plugin_data.copy()
    unlink = Path.unlink
    replace = Path.replace
    failures = []

    def fail_unlink(path, *args, **kwargs):
        if path == paths[1]:
            failures.append("unlink")
            raise OSError("injected unlink failure")
        return unlink(path, *args, **kwargs)

    def fail_restore(path, target):
        if target == paths[0]:
            failures.append("restore")
            raise OSError("injected restore failure")
        return replace(path, target)

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    monkeypatch.setattr(Path, "replace", fail_restore)
    with pytest.raises(CommandError, match="rollback incomplete") as error:
        call_command("remove_plugin_by_name", "safe_plugin")
    assert failures == ["unlink", "restore"]
    resume.refresh_from_db()
    assert resume.plugin_data == original_data
    backups = list(paths[0].parent.glob(".safe_plugin.py.backup-*"))
    assert len(backups) == 1
    assert str(backups[0]) in str(error.value)
    assert backups[0].read_bytes() == b"original 0"
    assert paths[1].read_bytes() == b"original 1"
    assert paths[2].read_bytes() == b"original 2"


@pytest.mark.parametrize(
    "extra",
    [
        "===safe_plugin.py===\nsecond copy",
        "===unknown.html===\nextra",
    ],
)
def test_create_rejects_duplicate_and_unknown_sections(
    stored_plugin, monkeypatch, extra
):
    _, paths = stored_plugin
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle() + "\n" + extra))
    with pytest.raises(CommandError, match="Unexpected or duplicate"):
        call_command("create_plugin_from_stdin")
    assert [path.read_bytes() for path in paths] == [
        b"original 0",
        b"original 1",
        b"original 2",
    ]


def test_create_new_files_respect_umask(tmp_path, monkeypatch):
    import os

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    previous_umask = os.umask(0o027)
    try:
        call_command("create_plugin_from_stdin")
    finally:
        os.umask(previous_umask)
    assert [path.stat().st_mode & 0o777 for path in plugin_files(tmp_path)] == [
        0o640
    ] * 3


@pytest.mark.parametrize(
    "command", ["create_plugin_from_stdin", "remove_plugin_by_name"]
)
def test_plugin_commands_restore_on_keyboard_interrupt(
    stored_plugin, monkeypatch, command
):
    from pathlib import Path

    resume, paths = stored_plugin
    original_data = resume.plugin_data.copy()
    monkeypatch.setattr("sys.stdin", StringIO(plugin_bundle()))
    method = "replace" if command == "create_plugin_from_stdin" else "unlink"
    original = getattr(Path, method)
    interruptions = []

    def interrupt_second(path, *args, **kwargs):
        target = args[0] if method == "replace" else path
        if target == paths[1] and not interruptions:
            interruptions.append(target)
            raise KeyboardInterrupt
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, method, interrupt_second)
    args = ("safe_plugin",) if command == "remove_plugin_by_name" else ()
    with pytest.raises(KeyboardInterrupt):
        call_command(command, *args)
    assert interruptions == [paths[1]]
    resume.refresh_from_db()
    assert resume.plugin_data == original_data
    assert [path.read_bytes() for path in paths] == [
        b"original 0",
        b"original 1",
        b"original 2",
    ]


@pytest.mark.django_db
def test_remove_reports_database_conflict_and_restores_files(
    stored_plugin, monkeypatch
):
    from django.db import DatabaseError
    from django_resume.models import ResumeManager

    resume, paths = stored_plugin
    original_data = resume.plugin_data.copy()
    original_files = [path.read_bytes() for path in paths]
    remove = ResumeManager.remove_plugin_data_by_name

    def conflict_after_update(manager, name):
        remove(manager, name)
        raise DatabaseError("injected conflict")

    monkeypatch.setattr(
        ResumeManager, "remove_plugin_data_by_name", conflict_after_update
    )
    with pytest.raises(CommandError, match="injected conflict"):
        call_command("remove_plugin_by_name", "safe_plugin")
    resume.refresh_from_db()
    assert resume.plugin_data == original_data
    assert [path.read_bytes() for path in paths] == original_files
