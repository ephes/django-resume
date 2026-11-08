"""A committed competing request wins between validation and insert."""

from concurrent.futures import ThreadPoolExecutor

import pytest
from django.db import IntegrityError, connections
from django.test import Client
from django.urls import reverse

from django_resume.forms import ResumeForm
from django_resume.models import Resume


@pytest.mark.django_db(transaction=True)
def test_manual_create_slug_race_preserves_form_and_winner(
    client, django_user_model, monkeypatch
):
    loser = django_user_model.objects.create_user(username="loser")
    winner = django_user_model.objects.create_user(username="winner")
    client.force_login(loser)
    competing_client = Client()
    competing_client.force_login(winner)
    original_valid = ResumeForm.is_valid
    competed = []
    submitted_forms = []

    def post_competitor():
        try:
            response = competing_client.post(
                reverse("resume:list"), {"name": "Winner", "slug": "shared"}
            )
            assert response.status_code == 200
            return Resume.objects.get(slug="shared").owner_id
        finally:
            connections.close_all()

    def valid_then_compete(form):
        if form.data.get("name") == "Submitted name":
            submitted_forms.append(form)
        valid = original_valid(form)
        if valid and not competed:
            competed.append(True)
            with ThreadPoolExecutor(max_workers=1) as executor:
                assert executor.submit(post_competitor).result(timeout=15) == winner.pk
        return valid

    monkeypatch.setattr(ResumeForm, "is_valid", valid_then_compete)
    response = client.post(
        reverse("resume:list"), {"name": "Submitted name", "slug": "shared"}
    )
    assert competed == [True]
    assert response.status_code == 200
    form = submitted_forms[0]
    assert "slug" in form.errors
    assert form["name"].value() == "Submitted name"
    assert form["slug"].value() == "shared"
    content = response.content.decode()
    assert "This slug was just taken" in content
    assert 'value="Submitted name"' in content
    assert 'value="shared"' in content
    assert Resume.objects.count() == 1
    assert Resume.objects.get().owner_id == winner.pk


@pytest.mark.django_db
def test_manual_create_unrelated_integrity_failure_propagates(
    client, django_user_model, monkeypatch
):
    owner = django_user_model.objects.create_user(username="synthetic")
    client.force_login(owner)

    def broken_save(*args, **kwargs):
        raise IntegrityError("synthetic unrelated database failure")

    monkeypatch.setattr(Resume, "save", broken_save)
    with pytest.raises(IntegrityError, match="unrelated"):
        client.post(reverse("resume:list"), {"name": "Synthetic", "slug": "synthetic"})
    assert not Resume.objects.exists()
