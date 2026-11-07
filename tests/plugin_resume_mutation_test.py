from tests.editor_helpers import revision_data

import pytest
from django.test import RequestFactory

from django_resume.plugins.base import LockedResumeMutationMixin
from django_resume.models import Resume


class DummyMutationView(LockedResumeMutationMixin):
    @staticmethod
    def check_permissions(request, resume) -> bool:
        return request.user == resume.owner


@pytest.mark.django_db(databases=["default", "other"])
@pytest.mark.parametrize(
    "editor",
    [
        "simple-inline",
        "simple-admin",
        "list-inline",
        "list-admin",
        "flat-inline",
        "flat-admin",
        "delete-inline",
        "delete-admin",
        "callback",
    ],
)
@pytest.mark.parametrize("fail", [False, True])
def test_editor_uses_one_routed_transaction(
    editor, fail, settings, django_user_model, monkeypatch
):
    from django.db import connections
    from django_resume.plugins.identity import IdentityPlugin
    from django_resume.plugins.education import EducationPlugin

    for alias in ("default", "other"):
        owner = django_user_model.objects.db_manager(alias).create_user(
            username="owner", is_staff=True
        )
        Resume.objects.using(alias).create(
            id=1,
            name="Synthetic",
            slug="synthetic",
            owner=owner,
            plugin_data={"sentinel": alias},
        )
    owner = django_user_model.objects.using("other").get(username="owner")
    request = RequestFactory().post(
        "/",
        {"name": "New name", "id": "", "school_name": "School", "title": "New title"},
    )
    request.user = owner
    calls = []

    class WriteRouter:
        def db_for_write(self, model, **hints):
            if model is Resume:
                calls.append(hints)
                return "other"

        def db_for_read(self, model, **hints):
            return "other"

    settings.DATABASE_ROUTERS = [WriteRouter()]
    identity, education = IdentityPlugin(), EducationPlugin()
    targets = {
        "simple-inline": (identity.inline, "post_view"),
        "simple-admin": (identity.admin, "post_view"),
        "list-inline": (education.inline, "post_item_view"),
        "list-admin": (education.admin, "post_item_view"),
        "flat-inline": (education.inline, "post_edit_flat_view"),
        "flat-admin": (education.admin, "post_flat_view"),
        "delete-inline": (education.inline, "delete_item_view"),
        "delete-admin": (education.admin, "delete_item_view"),
        "callback": (DummyMutationView(), "mutate_resume_plugin_data"),
    }
    view, method = targets[editor]
    if editor not in ("callback", "delete-inline", "delete-admin"):
        scope = (
            "flat"
            if editor.startswith("flat")
            else "item:"
            if editor.startswith("list")
            else "simple"
        )
        request.POST = revision_data(
            view, Resume.objects.using("other").get(pk=1), request.POST.dict(), scope
        )
    saved = []
    original_save = view.save_plugin_data

    def save(row):
        assert row._state.db == "other"
        assert connections["other"].in_atomic_block
        original_save(row)
        saved.append(True)
        if fail:
            raise RuntimeError("synthetic failure after write")

    monkeypatch.setattr(view, "save_plugin_data", save)
    # URL generation is unrelated to the transaction and plugin registration.
    for name in dir(view):
        if name.startswith("get_") and name.endswith("url"):
            monkeypatch.setattr(view, name, lambda *a, **kw: "/synthetic/")
    args = [request, 1]
    if editor.startswith("delete"):
        args.append("missing")
    elif editor == "callback":
        args.append(lambda row: row.plugin_data.update({"changed": True}))
    if fail:
        with pytest.raises(RuntimeError, match="synthetic failure after write"):
            getattr(view, method)(*args)
    else:
        getattr(view, method)(*args)
    assert saved == [True]  # prove the injected failure was reached
    assert calls == [{"resume_id": 1}]
    assert Resume.objects.using("default").get(pk=1).plugin_data == {
        "sentinel": "default"
    }
    result = Resume.objects.using("other").get(pk=1)
    assert result.plugin_data["sentinel"] == "other"
    if fail:
        assert result.plugin_data == {"sentinel": "other"}


@pytest.mark.django_db(databases=["default", "other"], transaction=True)
def test_routed_mutations_serialize_on_postgres(settings, django_user_model):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event
    from types import SimpleNamespace
    from django.db import connections, close_old_connections

    if connections["other"].vendor != "postgresql":
        pytest.skip("PostgreSQL row-lock interleaving")
    owner = django_user_model.objects.db_manager("other").create_user(
        username="lock-owner"
    )
    row = Resume.objects.using("other").create(name="Lock", slug="lock", owner=owner)

    class Router:
        def db_for_write(self, model, **hints):
            return "other"

        def db_for_read(self, model, **hints):
            return "other"

    settings.DATABASE_ROUTERS = [Router()]
    first_locked, second_select, release = Event(), Event(), Event()

    def worker(key):
        close_old_connections()
        try:

            def observe(execute, sql, params, many, context):
                if key == "second" and "FOR UPDATE" in sql:
                    second_select.set()
                return execute(sql, params, many, context)

            def mutate(resume):
                if key == "first":
                    first_locked.set()
                    assert release.wait(10)
                resume.plugin_data[key] = True

            with connections["other"].execute_wrapper(observe):
                DummyMutationView().mutate_resume_plugin_data(
                    SimpleNamespace(user=owner), row.pk, mutate
                )
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(worker, "first")
        try:
            assert first_locked.wait(10)
            second = pool.submit(worker, "second")
            assert second_select.wait(10)
            assert not second.done()
        finally:
            release.set()
        first.result(timeout=10)
        second.result(timeout=10)
    row.refresh_from_db(using="other")
    assert row.plugin_data == {"first": True, "second": True}
