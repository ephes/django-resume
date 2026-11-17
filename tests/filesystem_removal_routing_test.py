"""Filesystem and plugin-data removal share the selected writer transaction."""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DatabaseError, connections

from django_resume.models import Resume, ResumeManager
from tests.management_commands_test import plugin_files


class AlternateWriter:
    def __init__(self):
        self.calls = []

    def db_for_read(self, model, **hints):
        return "default"

    def db_for_write(self, model, **hints):
        self.calls.append(model)
        return "other"


@pytest.fixture
def routed_plugin(tmp_path, monkeypatch, django_user_model, settings):
    monkeypatch.chdir(tmp_path)
    owner = django_user_model.objects.db_manager("other").create_user(
        username="synthetic-owner"
    )
    original = {"safe_plugin": {"title": "Synthetic"}, "about": {"title": "Keep"}}
    for slug in ("first", "second"):
        Resume.objects.using("other").create(
            name=slug, slug=slug, owner=owner, plugin_data=original
        )
    paths = plugin_files(tmp_path)
    contents = [b"synthetic code", b"synthetic content", b"synthetic form"]
    for path, content in zip(paths, contents):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    router = AlternateWriter()
    settings.DATABASE_ROUTERS = [router]
    return paths, contents, original, router


@pytest.mark.django_db(databases=["other"], transaction=True)
def test_removal_uses_writer_once_without_accessing_default(routed_plugin):
    paths, _, _, router = routed_plugin
    call_command("remove_plugin_by_name", "safe_plugin")
    assert router.calls == [Resume]
    assert not any(path.exists() for path in paths)
    assert list(
        Resume.objects.using("other").values_list("plugin_data", flat=True)
    ) == [
        {"about": {"title": "Keep"}},
        {"about": {"title": "Keep"}},
    ]


@pytest.mark.django_db(databases=["default", "other"], transaction=True)
def test_failure_after_manager_returns_restores_files_and_all_rows(
    routed_plugin, monkeypatch
):
    paths, contents, original, router = routed_plugin
    remove = ResumeManager.remove_plugin_data_by_name
    changed = []

    def fail_after_mutation(manager, plugin_name):
        remove(manager, plugin_name)
        changed.extend(
            Resume.objects.using("other").values_list("plugin_data", flat=True)
        )
        assert not any(path.exists() for path in paths)
        raise DatabaseError("synthetic failure after removal")

    monkeypatch.setattr(
        ResumeManager, "remove_plugin_data_by_name", fail_after_mutation
    )
    with pytest.raises(CommandError, match="synthetic failure after removal"):
        call_command("remove_plugin_by_name", "safe_plugin")
    assert changed == [{"about": {"title": "Keep"}}] * 2
    assert router.calls == [Resume]
    assert [path.read_bytes() for path in paths] == contents
    assert (
        list(Resume.objects.using("other").values_list("plugin_data", flat=True))
        == [original] * 2
    )


@pytest.mark.django_db(databases=["other"], transaction=True)
def test_selected_commit_failure_retains_intent_for_uncertain_outcome(
    routed_plugin, monkeypatch
):
    from django_resume.management.commands._plugin_publication import intent_path

    paths, contents, original, router = routed_plugin
    commits = []

    def fail_commit():
        commits.append(True)
        assert not any(path.exists() for path in paths)
        assert (
            list(Resume.objects.using("other").values_list("plugin_data", flat=True))
            == [{"about": {"title": "Keep"}}] * 2
        )
        raise DatabaseError("synthetic selected commit failure")

    with monkeypatch.context() as patch:
        patch.setattr(connections["other"], "commit", fail_commit)
        with pytest.raises(
            CommandError, match="synthetic selected commit failure.*outcome uncertain"
        ):
            call_command("remove_plugin_by_name", "safe_plugin")
    assert commits == [True]
    assert router.calls == [Resume]
    # A failed COMMIT may still have committed (e.g. a dropped connection):
    # files stay removed and the intent blocks mutation until verified.
    assert not any(path.exists() for path in paths)
    assert intent_path(paths).is_file()
    with pytest.raises(CommandError, match="Interrupted plugin publication"):
        call_command("remove_plugin_by_name", "safe_plugin")
    assert (
        list(Resume.objects.using("other").values_list("plugin_data", flat=True))
        == [original] * 2
    )
    call_command(
        "recover_plugin",
        "safe_plugin",
        action="restore",
        database_outcome="rolled-back",
    )
    assert [path.read_bytes() for path in paths] == contents
    assert not intent_path(paths).exists()
