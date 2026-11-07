"""Real middleware checks, with valid application proof and synthetic data only."""

from copy import deepcopy
import json

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from django_resume import views
from django_resume.models import Resume
from django_resume.plugins import TokenPlugin
from django_resume.plugins.education import EducationPlugin
from django_resume.plugins.identity import IdentityPlugin
from tests.conftest import png_bytes
from tests.editor_helpers import revision_data


@pytest.fixture
def browser_owner(django_user_model, settings):
    owner = django_user_model.objects.create_user(username="synthetic-owner")
    resume = Resume.objects.create(
        name="Synthetic",
        slug="synthetic",
        owner=owner,
        plugin_data={
            "identity": {"name": "Original"},
            "education": {
                "flat": {"title": "Education"},
                "items": [
                    {"id": "school", "school_name": "Original school", "position": 0}
                ],
            },
            "token": {"flat": {"token_required": False}},
        },
    )
    client = Client(enforce_csrf_checks=True)
    client.force_login(owner)
    assert client.get(reverse("resume:list"), secure=True).status_code == 200
    return client, resume, client.cookies[settings.CSRF_COOKIE_NAME].value


def proof_headers(csrf, proof):
    headers = {"Origin": "https://testserver"}
    if proof != "missing":
        headers["X-CSRFToken"] = (
            ("a" * 32 if csrf != "a" * 32 else "b" * 32)
            if proof == "mismatched"
            else csrf
        )
    if proof == "foreign-origin":
        headers["Origin"] = "https://foreign.example.invalid"
    return headers


def upload():
    return SimpleUploadedFile(
        "synthetic.json",
        json.dumps({"basics": {"name": "Imported"}}).encode(),
        "application/json",
    )


@pytest.mark.django_db
@pytest.mark.parametrize("action", ["preview", "create", "url", "delete"])
@pytest.mark.parametrize("proof", ["missing", "mismatched", "foreign-origin", "valid"])
def test_import_and_delete_require_browser_csrf(browser_owner, action, proof, mocker):
    client, resume, csrf = browser_owner
    url = reverse("resume:json-resume-import")
    data = {"slug": "imported"}
    if action in {"preview", "create"}:
        if action == "create":
            response = client.post(
                url,
                {**data, "action": "preview", "file": upload()},
                secure=True,
                headers=proof_headers(csrf, "valid"),
            )
            assert response.status_code == 200
            data["confirmation"] = response.context["import_preview"]["confirmation"]
        data.update(action=action, file=upload())
    elif action == "url":
        data["source_url"] = "https://example.invalid/resume.json"
    fetch = mocker.patch.object(
        views, "load_document_url", return_value={"basics": {"name": "Imported"}}
    )
    prepare = mocker.spy(views, "_prepare_uploaded_import")
    create = mocker.spy(views, "create_prepared_import")
    before = list(Resume.objects.values())
    if action == "delete":
        response = client.delete(
            reverse("resume:delete", kwargs={"slug": resume.slug}),
            secure=True,
            headers=proof_headers(csrf, proof),
        )
    else:
        response = client.post(
            url, data, secure=True, headers=proof_headers(csrf, proof)
        )
    if proof != "valid":
        assert response.status_code == 403
        assert list(Resume.objects.values()) == before
        fetch.assert_not_called()
        prepare.assert_not_called()
        create.assert_not_called()
    else:
        assert response.status_code == 200
        if action == "delete":
            assert not Resume.objects.filter(pk=resume.pk).exists()
        elif action == "preview":
            assert "import_preview" in response.context
            assert list(Resume.objects.values()) == before
            prepare.assert_called_once()
            create.assert_not_called()
        else:
            imported = Resume.objects.get(slug="imported")
            assert imported.owner == resume.owner
            assert imported.plugin_data["identity"]["name"] == "Imported"
        if action == "url":
            fetch.assert_called_once_with("https://example.invalid/resume.json")
        else:
            fetch.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "kind", ["identity", "token-flat", "education-flat", "item-create", "item-update"]
)
@pytest.mark.parametrize("proof", ["missing", "mismatched", "foreign-origin", "valid"])
def test_inline_revision_does_not_replace_browser_csrf(
    browser_owner, kind, proof, in_memory_storage, mocker
):
    client, resume, csrf = browser_owner
    if kind == "identity":
        view = IdentityPlugin().inline
        url = view.get_post_url(resume.pk)
        data = revision_data(
            view,
            resume,
            {
                "name": "Changed",
                "avatar_img": SimpleUploadedFile(
                    "synthetic.png", png_bytes(2, 2), "image/png"
                ),
            },
        )
    elif kind.endswith("flat"):
        view = (
            TokenPlugin().inline if kind == "token-flat" else EducationPlugin().inline
        )
        url = view.get_edit_flat_post_url(resume.pk)
        data = revision_data(
            view,
            resume,
            {"token_required": "on"} if kind == "token-flat" else {"title": "Changed"},
            "flat",
        )
    else:
        view = EducationPlugin().inline
        url = view.get_post_item_url(resume.pk)
        item_id = "school" if kind == "item-update" else ""
        data = revision_data(
            view,
            resume,
            {"id": item_id, "school_name": "Changed", "position": 1},
            "item:" + item_id,
        )
    before = deepcopy(resume.plugin_data)
    save = mocker.spy(default_storage, "save")
    response = client.post(url, data, secure=True, headers=proof_headers(csrf, proof))
    resume.refresh_from_db()
    if proof != "valid":
        assert response.status_code == 403
        assert resume.plugin_data == before
        save.assert_not_called()
    else:
        assert response.status_code == 200
        if kind == "identity":
            assert resume.plugin_data["identity"]["name"] == "Changed"
            save.assert_called_once()
            assert default_storage.exists(resume.plugin_data["identity"]["avatar_img"])
        elif kind == "token-flat":
            assert resume.plugin_data["token"]["flat"]["token_required"] is True
        elif kind == "education-flat":
            assert resume.plugin_data["education"]["flat"]["title"] == "Changed"
        else:
            items = resume.plugin_data["education"]["items"]
            assert len(items) == (2 if kind == "item-create" else 1)
            assert items[-1]["school_name"] == "Changed"
