"""Owner downloads use the canonical resume row."""

import pytest
from django.urls import reverse

from django_resume.models import Resume
from django_resume.plugins.identity import IdentityPlugin


class ExportRouter:
    def db_for_read(self, model, **hints):
        return "default"

    def db_for_write(self, model, **hints):
        return "other" if model is Resume else "default"


@pytest.mark.django_db(databases=["default", "other"])
@pytest.mark.parametrize(
    ("requester", "writer_owner", "status"),
    [
        ("current-owner", "current-owner", 200),
        ("former-owner", "current-owner", 404),
        ("former-owner", None, 404),
    ],
)
def test_export_uses_writer_row(
    client, settings, django_user_model, requester, writer_owner, status
):
    for username in ("former-owner", "current-owner"):
        user = django_user_model.objects.create(username=username)
        django_user_model.objects.using("other").create(pk=user.pk, username=username)

    slug = "synthetic-export"

    def create_row(alias, owner, name):
        owner_id = django_user_model.objects.get(username=owner).pk
        resume = Resume(slug=slug, name=name, owner_id=owner_id)
        IdentityPlugin().data.set_data(resume, {"name": name})
        resume.save(using=alias)

    create_row("default", "former-owner", "Replica Resume")
    if writer_owner is not None:
        create_row("other", writer_owner, "Writer Resume")

    client.force_login(django_user_model.objects.get(username=requester))
    settings.DATABASE_ROUTERS = [ExportRouter()]
    response = client.get(reverse("django_resume:json-resume", kwargs={"slug": slug}))

    assert response.status_code == status
    assert {"private", "no-store"} <= set(response["Cache-Control"].split(", "))
    if status == 200:
        assert response.json()["basics"]["name"] == "Writer Resume"
        assert response["Content-Disposition"] == f'attachment; filename="{slug}.json"'
    else:
        assert response.content == b""
