import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from django.db import connection, connections, transaction
from django.db.models import QuerySet

from django_resume.formats.json_resume import themes
from django_resume.models import Resume
from . import plugin_removal_concurrency_test

file_database = plugin_removal_concurrency_test.file_database


@pytest.mark.django_db
@pytest.mark.parametrize("catalog", [True, False])
def test_theme_selection_preserves_committed_integration_from_stale_instance(
    user, catalog
):
    user.save()
    resume = Resume.objects.create(
        name="Synthetic",
        slug="synthetic",
        owner=user,
        integration_data={"json_resume": {"preserved": "before"}},
    )
    stale = Resume.objects.get(pk=resume.pk)
    updated = {
        "other_integration": {"revision": 2},
        "json_resume": {"preserved": "after"},
    }
    Resume.objects.filter(pk=resume.pk).update(integration_data=updated)
    if catalog:
        themes.set_selected_catalog_theme(stale, "even")
    else:
        themes.set_selected_theme(stale, "jsonresume-theme-even")
    resume.refresh_from_db()
    assert resume.integration_data["other_integration"] == {"revision": 2}
    assert resume.integration_data["json_resume"]["preserved"] == "after"
    assert (
        resume.integration_data["json_resume"]["theme"]["package"]
        == "jsonresume-theme-even"
    )
    assert stale.integration_data == resume.integration_data


@pytest.mark.skipif(connection.vendor != "sqlite", reason="SQLite snapshot conflict")
def test_sqlite_concurrent_integration_edit_is_controlled(
    file_database, user, monkeypatch
):
    user.save()
    resume = Resume.objects.create(name="Synthetic", slug="synthetic", owner=user)
    updated = {"other_integration": {"revision": 2}}
    original_get = QuerySet.get
    wrote = []

    def edit_after_locked_read(queryset, *args, **kwargs):
        row = original_get(queryset, *args, **kwargs)
        if queryset.model is Resume and queryset.query.select_for_update and not wrote:
            with sqlite3.connect(file_database, timeout=0) as writer:
                writer.execute(
                    "UPDATE django_resume_resume SET integration_data=? WHERE id=?",
                    [json.dumps(updated), resume.pk],
                )
            wrote.append(True)
        return row

    monkeypatch.setattr(QuerySet, "get", edit_after_locked_read)
    with pytest.raises(themes.JsonResumeThemeError, match="retry"):
        themes.set_selected_catalog_theme(resume, "even")
    assert wrote == [True]
    assert resume.integration_data == {}
    resume.refresh_from_db()
    assert resume.integration_data == updated


@pytest.mark.django_db
def test_theme_selection_reports_conditional_update_conflict(user, monkeypatch):
    user.save()
    resume = Resume.objects.create(name="Synthetic", slug="synthetic", owner=user)
    attempted = []

    def conflict(queryset, **kwargs):
        attempted.append(True)
        return 0

    monkeypatch.setattr(QuerySet, "update", conflict)
    with pytest.raises(themes.JsonResumeThemeError, match="retry"):
        themes.set_selected_theme(resume, "jsonresume-theme-even")
    assert attempted == [True]
    assert resume.integration_data == {}
    resume.refresh_from_db()
    assert resume.integration_data == {}


@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="PostgreSQL row-lock interleaving"
)
@pytest.mark.django_db(transaction=True)
def test_selection_waits_for_integration_writer_and_preserves_commit(user):
    user.save()
    resume = Resume.objects.create(name="Synthetic", slug="synthetic", owner=user)
    writer_locked, release, selecting, selected = [Event() for _ in range(4)]

    def edit_integration():
        try:
            with transaction.atomic():
                current = Resume.objects.select_for_update().get(pk=resume.pk)
                current.integration_data = {"other_integration": {"revision": 2}}
                current.save(update_fields=["integration_data"])
                writer_locked.set()
                if not release.wait(10):
                    raise RuntimeError("test did not release writer")
        finally:
            connections.close_all()

    def select_theme():
        try:
            selecting.set()
            themes.set_selected_catalog_theme(resume, "even")
            selected.set()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(edit_integration)
        selector = None
        try:
            assert writer_locked.wait(5)
            selector = pool.submit(select_theme)
            assert selecting.wait(5)
            assert not selected.wait(0.2)
        finally:
            release.set()
        writer.result(timeout=10)
        assert selector is not None
        selector.result(timeout=10)
    resume.refresh_from_db()
    assert resume.integration_data["other_integration"] == {"revision": 2}
    assert resume.integration_data["json_resume"]["theme"]["key"] == "even"
