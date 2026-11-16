"""Rendered private output needs current authority on the captured database."""

from types import SimpleNamespace
from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import connection, connections
from django.test import RequestFactory

from django_resume import views
from django_resume.models import Resume
from .plugin_removal_concurrency_test import file_database  # noqa: F401


@pytest.fixture
def render_database(request, transactional_db):
    if connection.vendor == "sqlite":
        return request.getfixturevalue("file_database")
    return None


@pytest.mark.django_db(databases=["default", "other"])
@pytest.mark.parametrize("preview", [True, False])
@pytest.mark.parametrize("change", ["transfer", "delete", "stable"])
def test_render_rechecks_original_database_owner(
    preview, change, settings, django_user_model, monkeypatch
):
    for alias in ("default", "other"):
        owner = django_user_model.objects.db_manager(alias).create(username="owner")
        Resume.objects.using(alias).create(
            pk=1, slug="synthetic", name="Synthetic", owner=owner
        )
    owner = django_user_model.objects.using("other").get(username="owner")
    next_owner = django_user_model.objects.db_manager("other").create(
        username="next-owner"
    )

    class Router:
        def db_for_read(self, model, **hints):
            return "other"

    settings.DATABASE_ROUTERS = [Router()]

    def render(resume, *args):
        # Force a subsequent unrouted lookup onto a misleading unchanged row.
        settings.DATABASE_ROUTERS = []
        if change == "transfer":
            Resume.objects.using("other").filter(pk=resume.pk).update(owner=next_owner)
        elif change == "delete":
            Resume.objects.using("other").filter(pk=resume.pk).delete()
        return SimpleNamespace(html="synthetic-private-html")

    monkeypatch.setattr(views, "_ensure_catalog_theme", lambda entry: None)
    monkeypatch.setattr(views, "render_catalog_theme", render)
    monkeypatch.setattr(views, "render_selected_theme", render)
    request = RequestFactory().post("/") if preview else RequestFactory().get("/")
    request.user = owner
    view = (
        views.preview_json_resume_catalog_theme
        if preview
        else views.render_json_resume_theme
    )
    response = view(request, "synthetic", **({"key": "even"} if preview else {}))
    assert response.status_code == (200 if change == "stable" else 404)
    assert (b"synthetic-private-html" in response.content) == (change == "stable")
    assert "no-store" in response["Cache-Control"]
    if change == "transfer":
        settings.DATABASE_ROUTERS = [Router()]
        request.user = next_owner
        fresh = view(request, "synthetic", **({"key": "even"} if preview else {}))
        assert fresh.status_code == 200
        assert b"synthetic-private-html" in fresh.content


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("preview", [True, False])
@pytest.mark.parametrize("change", ["transfer", "delete"])
def test_render_barrier_rechecks_committed_writer(
    render_database, user, django_user_model, monkeypatch, preview, change
):
    user.save()
    next_owner = django_user_model.objects.create(username="next-owner")
    row = Resume.objects.create(slug="synthetic", name="Synthetic", owner=user)

    def mutate():
        if render_database is not None:
            import sqlite3

            with sqlite3.connect(render_database, timeout=1) as writer:
                if change == "transfer":
                    writer.execute(
                        "UPDATE django_resume_resume SET owner_id=? WHERE id=?",
                        [next_owner.pk, row.pk],
                    )
                else:
                    writer.execute(
                        "DELETE FROM django_resume_resume WHERE id=?", [row.pk]
                    )
        else:
            try:
                rows = Resume.objects.filter(pk=row.pk)
                rows.update(owner=next_owner) if change == "transfer" else rows.delete()
            finally:
                connections.close_all()

    def render(resume, *args):
        with ThreadPoolExecutor(max_workers=1) as pool:
            pool.submit(mutate).result(timeout=5)
        return SimpleNamespace(html="synthetic-private-html")

    monkeypatch.setattr(views, "_ensure_catalog_theme", lambda entry: None)
    monkeypatch.setattr(views, "render_catalog_theme", render)
    monkeypatch.setattr(views, "render_selected_theme", render)
    request = RequestFactory().post("/") if preview else RequestFactory().get("/")
    request.user = user
    view = (
        views.preview_json_resume_catalog_theme
        if preview
        else views.render_json_resume_theme
    )
    response = view(request, row.slug, **({"key": "even"} if preview else {}))
    assert response.status_code == 404
    assert b"synthetic-private-html" not in response.content
