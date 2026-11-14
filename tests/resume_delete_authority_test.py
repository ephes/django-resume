"""Deletion must authorize the current writer-side owner."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from django.db import connection, connections, transaction
from django.db.models import QuerySet
from django.urls import reverse

from django_resume.models import Resume


class ReadReplicaRouter:
    def db_for_read(self, model, **hints):
        return "replica" if model is Resume else "default"

    def db_for_write(self, model, **hints):
        return "default"


@pytest.mark.django_db
def test_delete_uses_locked_write_lookup(client, resume, settings, monkeypatch):
    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    settings.DATABASE_ROUTERS = [ReadReplicaRouter()]
    original_get = QuerySet.get
    lookups = []

    def inspect(queryset, *args, **kwargs):
        if queryset.model is Resume:
            lookups.append((queryset.db, queryset.query.select_for_update))
        return original_get(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "get", inspect)
    response = client.delete(reverse("resume:delete", kwargs={"slug": resume.slug}))
    assert response.status_code == 200
    assert lookups == [("default", True)]
    assert not Resume.objects.using("default").filter(pk=resume.pk).exists()


@pytest.mark.skipif(connection.vendor != "postgresql", reason="PostgreSQL row locks")
@pytest.mark.django_db(transaction=True)
def test_delete_waits_for_owner_transfer(client, user, django_user_model, monkeypatch):
    user.save()
    next_owner = django_user_model.objects.create(username="synthetic-next-owner")
    resume = Resume.objects.create(name="Synthetic", slug="transfer-delete", owner=user)
    client.force_login(user)
    written, release, lookup, read = [Event() for _ in range(4)]
    locked_lookup = []
    original_get = QuerySet.get

    def inspect(queryset, *args, **kwargs):
        if queryset.model is Resume:
            locked_lookup.append(queryset.query.select_for_update)
            lookup.set()
            row = original_get(queryset, *args, **kwargs)
            read.set()
            return row
        return original_get(queryset, *args, **kwargs)

    monkeypatch.setattr(QuerySet, "get", inspect)

    def transfer():
        try:
            with transaction.atomic():
                Resume.objects.filter(pk=resume.pk).update(owner=next_owner)
                written.set()
                assert release.wait(10)
        finally:
            connections.close_all()

    def delete():
        try:
            return client.delete(reverse("resume:delete", kwargs={"slug": resume.slug}))
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        writer = pool.submit(transfer)
        try:
            assert written.wait(5)
            deletion = pool.submit(delete)
            assert lookup.wait(5)
            # In the old implementation ensure the stale read has actually
            # completed before committing the owner transfer. A locked lookup
            # must instead remain blocked until that commit.
            if locked_lookup == [False]:
                assert read.wait(5)
            else:
                assert not read.wait(0.2)
            assert not deletion.done()
        finally:
            release.set()
        writer.result(timeout=10)
        response = deletion.result(timeout=10)
    assert response.status_code == 403
    resume.refresh_from_db()
    assert resume.owner_id == next_owner.pk
