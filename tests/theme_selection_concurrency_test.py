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


@pytest.mark.skipif(
    connection.vendor != "sqlite", reason="SQLite independent-connection fixture"
)
@pytest.mark.parametrize("catalog", [True, False])
def test_selection_rechecks_owner_after_install_from_independent_connection(
    file_database, user, django_user_model, client, settings, monkeypatch, catalog
):
    from django.urls import reverse

    user.save()
    new_owner = django_user_model.objects.create(username="new-owner")
    resume = Resume.objects.create(name="Synthetic", slug="transfer", owner=user)
    preserved = {
        "new_owner": {"revision": 2},
        "json_resume": {"theme": {"key": "flat"}},
    }
    settings.DJANGO_RESUME_JSON_RESUME_ALLOW_CATALOG_THEME_INSTALL = True
    settings.DJANGO_RESUME_JSON_RESUME_ALLOW_DYNAMIC_THEME_INSTALL = True
    transferred = Event()

    def transfer():
        with sqlite3.connect(file_database, timeout=1) as writer:
            writer.execute(
                "UPDATE django_resume_resume SET owner_id=?, integration_data=? WHERE id=?",
                [new_owner.pk, json.dumps(preserved), resume.pk],
            )
        transferred.set()

    def gated_install(*args):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(transfer).result(timeout=5)
        assert transferred.is_set()
        return themes.catalog_theme("even")

    monkeypatch.setattr(
        "django_resume.views.install_catalog_theme"
        if catalog
        else "django_resume.views.install_theme",
        gated_install,
    )
    monkeypatch.setattr("django_resume.views.search_themes", lambda query: [])
    client.force_login(user)
    route = "json-resume-theme-use" if catalog else "json-resume-theme-install"
    kwargs = {"slug": resume.slug, **({"key": "even"} if catalog else {})}
    response = client.post(
        reverse(f"django_resume:{route}", kwargs=kwargs),
        {"package": "jsonresume-theme-even"},
    )
    assert transferred.is_set()
    assert response.status_code == 404
    resume.refresh_from_db()
    assert resume.owner_id == new_owner.pk
    assert resume.integration_data == preserved


@pytest.mark.django_db
@pytest.mark.parametrize("catalog", [True, False])
def test_stale_theme_setter_refuses_former_owner(user, django_user_model, catalog):
    user.save()
    resume = Resume.objects.create(name="Synthetic", slug="stale-owner", owner=user)
    new_owner = django_user_model.objects.create(username="new-owner")
    Resume.objects.filter(pk=resume.pk).update(owner=new_owner)
    with pytest.raises(themes.JsonResumeThemeError, match="owner"):
        if catalog:
            themes.set_selected_catalog_theme(resume, "even", expected_owner_id=user.pk)
        else:
            themes.set_selected_theme(
                resume, "jsonresume-theme-even", expected_owner_id=user.pk
            )
    resume.refresh_from_db()
    assert resume.integration_data == {}
