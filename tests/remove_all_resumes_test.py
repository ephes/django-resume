"""Synthetic administrative deletion tests."""

from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import CommandError, call_command
from django.db import DatabaseError, transaction
from django.db.models import QuerySet
from django.db.models.signals import post_delete

from django_resume.models import Resume


@pytest.fixture
def resumes(django_user_model):
    return [
        Resume.objects.create(
            owner=django_user_model.objects.create_user(username=f"owner-{i}"),
            slug=f"synthetic-{i}",
            name=f"Synthetic {i}",
        )
        for i in range(2)
    ]


@pytest.mark.django_db
def test_remove_all_defaults_to_count_only(resumes):
    out = StringIO()
    call_command("remove_all_resumes", stdout=out)
    assert Resume.objects.count() == 2
    assert "2" in out.getvalue()
    assert "--delete-all-resumes" in out.getvalue()


@pytest.mark.django_db
def test_explicit_flag_deletes_every_owners_resume(resumes):
    out = StringIO()
    call_command("remove_all_resumes", "--delete-all-resumes", stdout=out)
    assert not Resume.objects.exists()
    assert "Deleted 2 resumes" in out.getvalue()


@pytest.mark.django_db(transaction=True)
def test_confirmed_delete_rolls_back_on_database_failure(resumes):
    failures = []

    def fail_after_delete(sender, instance, **kwargs):
        assert transaction.get_connection().in_atomic_block
        assert not Resume.objects.exists()
        failures.append(instance.pk)
        raise DatabaseError("injected deletion failure")

    original_delete = QuerySet.delete

    def delete_in_transaction(queryset):
        assert transaction.get_connection().in_atomic_block
        return original_delete(queryset)

    post_delete.connect(fail_after_delete, sender=Resume)
    try:
        with patch.object(QuerySet, "delete", delete_in_transaction):
            with pytest.raises(
                CommandError, match="deletion rolled back.*injected deletion failure"
            ):
                call_command("remove_all_resumes", "--delete-all-resumes")
    finally:
        post_delete.disconnect(fail_after_delete, sender=Resume)
    assert failures
    assert set(Resume.objects.values_list("pk", flat=True)) == {r.pk for r in resumes}


class ReadReplicaRouter:
    def db_for_read(self, model, **hints):
        return "unconfigured-replica"

    def db_for_write(self, model, **hints):
        return "default"


@pytest.mark.django_db
def test_preview_and_delete_use_same_write_database(resumes, settings):
    settings.DATABASE_ROUTERS = [ReadReplicaRouter()]
    out = StringIO()
    call_command("remove_all_resumes", stdout=out)
    assert "2 resumes" in out.getvalue()
    with patch.object(transaction, "atomic", wraps=transaction.atomic) as atomic:
        call_command("remove_all_resumes", "--delete-all-resumes", stdout=out)
    assert any(call.kwargs == {"using": "default"} for call in atomic.call_args_list)
    assert not Resume.objects.using("default").exists()
