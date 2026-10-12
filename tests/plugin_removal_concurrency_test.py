import json
import sqlite3

import pytest
from django.db import DatabaseError, connections
from django.db.models import QuerySet

from django_resume.models import Resume


@pytest.fixture
def file_database(tmp_path, monkeypatch, transactional_db):
    original = connections["default"]
    original.ensure_connection()
    path = tmp_path / "race.sqlite3"
    with sqlite3.connect(path) as target:
        original.connection.backup(target)
        target.execute("PRAGMA journal_mode=WAL")
    isolated = original.copy()
    isolated.settings_dict = {**original.settings_dict, "NAME": str(path)}
    monkeypatch.setattr(connections._connections, "default", isolated)
    try:
        yield path
    finally:
        isolated.close()


def test_removal_reports_concurrent_sqlite_edit_without_losing_data(
    file_database, monkeypatch, user
):
    user.save()
    resume = Resume.objects.create(
        name="Race",
        slug="race",
        owner=user,
        plugin_data={"about": {"title": "old"}, "skills": {"items": ["old"]}},
    )
    edited = {"about": {"title": "old"}, "skills": {"items": ["new"]}}
    original_iter = QuerySet.__iter__
    edits = []

    def edit_after_read(queryset):
        rows = list(original_iter(queryset))
        if queryset.model is Resume and not edits:
            with sqlite3.connect(file_database, timeout=0) as writer:
                writer.execute(
                    "UPDATE django_resume_resume SET plugin_data = ? WHERE id = ?",
                    [json.dumps(edited), resume.pk],
                )
            edits.append(True)
        return iter(rows)

    monkeypatch.setattr(QuerySet, "__iter__", edit_after_read)
    with pytest.raises(DatabaseError):
        Resume.objects.remove_plugin_data_by_name("about")
    assert edits == [True]
    resume.refresh_from_db()
    assert resume.plugin_data == edited
    Resume.objects.remove_plugin_data_by_name("about")
    resume.refresh_from_db()
    assert resume.plugin_data == {"skills": {"items": ["new"]}}


@pytest.mark.django_db
def test_conditional_update_conflict_rolls_back_all_removals(user, monkeypatch):
    user.save()
    data = {"about": {"title": "old"}, "skills": {"items": ["keep"]}}
    for slug in ["first", "second"]:
        Resume.objects.create(name=slug, slug=slug, owner=user, plugin_data=data)
    original_update = QuerySet.update
    attempts = []

    def conflict_on_second(queryset, **kwargs):
        attempts.append(True)
        if len(attempts) == 2:
            return 0
        return original_update(queryset, **kwargs)

    monkeypatch.setattr(QuerySet, "update", conflict_on_second)
    with pytest.raises(DatabaseError, match="changed during removal"):
        Resume.objects.remove_plugin_data_by_name("about")
    assert len(attempts) == 2
    assert all(resume.plugin_data == data for resume in Resume.objects.all())


class ReadReplicaRouter:
    def db_for_read(self, model, **hints):
        return "replica"

    def db_for_write(self, model, **hints):
        return "default"


class MissingWriteRouter:
    def db_for_read(self, model, **hints):
        return "missing"

    def db_for_write(self, model, **hints):
        return "missing"


@pytest.mark.django_db
def test_removal_reads_and_writes_the_routed_write_database(user, settings):
    user.save()
    resume = Resume.objects.create(
        name="Routed",
        slug="routed",
        owner=user,
        plugin_data={"about": {"title": "old"}, "skills": {"items": ["keep"]}},
    )
    # The "replica" alias is not configured: any query routed there fails.
    settings.DATABASE_ROUTERS = [ReadReplicaRouter()]
    assert Resume.objects.db == "replica"

    Resume.objects.remove_plugin_data_by_name("about")

    settings.DATABASE_ROUTERS = []
    resume.refresh_from_db()
    assert resume.plugin_data == {"skills": {"items": ["keep"]}}


@pytest.mark.django_db
def test_removal_honors_an_explicitly_bound_manager_database(user, settings):
    user.save()
    resume = Resume.objects.create(
        name="Bound",
        slug="bound",
        owner=user,
        plugin_data={"about": {"title": "old"}, "skills": {"items": ["keep"]}},
    )
    settings.DATABASE_ROUTERS = [MissingWriteRouter()]

    Resume.objects.db_manager("default").remove_plugin_data_by_name("about")

    settings.DATABASE_ROUTERS = []
    resume.refresh_from_db()
    assert resume.plugin_data == {"skills": {"items": ["keep"]}}
