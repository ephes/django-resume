"""Synthetic transport and browser tests for import parser failures."""

import io
from unittest.mock import Mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.urls import reverse

from django_resume.formats.json_resume import importer
from django_resume.formats.json_resume.import_preview import (
    ImportPreviewClaims,
    input_digest,
    sign_import_preview,
)
from django_resume.models import Resume

INTEGER_DOCUMENT = (
    b'{"basics":{"name":"Synthetic","image":"https://example.com/image.png"},"extension":'
    + b"9" * 5000
    + b"}"
)
INTEGER_ERROR = "JSON integer exceeds supported limits"


def synthetic_url(monkeypatch, data):
    monkeypatch.setattr(
        importer.socket,
        "getaddrinfo",
        Mock(return_value=[(2, 1, 6, "", ("8.8.8.8", 443))]),
    )
    response = Mock(status=200, headers={})
    stream = io.BytesIO(data)
    response.read1.side_effect = stream.read
    connection = Mock(sock=None)
    connection.getresponse.return_value = response
    monkeypatch.setattr(importer, "_connection_for_url", Mock(return_value=connection))


def test_large_integer_file_bytes_and_url_have_bounded_errors(tmp_path, monkeypatch):
    path = tmp_path / "synthetic.json"
    path.write_bytes(INTEGER_DOCUMENT)
    synthetic_url(monkeypatch, INTEGER_DOCUMENT)
    for load in (
        lambda: importer.load_document_bytes(INTEGER_DOCUMENT),
        lambda: importer.load_document(path),
        lambda: importer.load_document_url("https://example.com/resume.json"),
    ):
        with pytest.raises(importer.JsonResumeImportError) as error:
            load()
        assert str(error.value) == INTEGER_ERROR


@pytest.mark.django_db
@pytest.mark.parametrize(
    "source, action", [("file", "preview"), ("file", "create"), ("url", "")]
)
def test_large_integer_browser_writes_nothing(
    client, django_user_model, monkeypatch, action, source
):
    owner = django_user_model.objects.create_user(username="synthetic")
    client.force_login(owner)
    synthetic_url(monkeypatch, INTEGER_DOCUMENT)
    storage = Mock()
    monkeypatch.setattr("django_resume.images.default_storage", storage)
    data = {"slug": "synthetic", "action": action}
    if source == "file" and action == "create":
        # Synthetic server-issued claims exercise the re-decoding confirmation path.
        data["confirmation"] = sign_import_preview(
            ImportPreviewClaims(
                owner=str(owner.pk),
                input_digest=input_digest(INTEGER_DOCUMENT),
                slug="synthetic",
                name="",
                mode="restore",
                plan_digest="unused",
            )
        )
    if source == "file":
        data["file"] = SimpleUploadedFile(
            "synthetic.json", INTEGER_DOCUMENT, "application/json"
        )
    else:
        data["source_url"] = "https://example.com/resume.json"
    response = client.post(reverse("resume:json-resume-import"), data)
    assert response.status_code == 200
    assert INTEGER_ERROR in str(response.context["import_form"].errors)
    assert not Resume.objects.exists()
    storage.save.assert_not_called()


@pytest.mark.django_db
def test_large_integer_cli_writes_nothing(tmp_path, django_user_model):
    owner = django_user_model.objects.create_user(username="synthetic")
    path = tmp_path / "synthetic.json"
    path.write_bytes(INTEGER_DOCUMENT)
    with pytest.raises(CommandError, match=INTEGER_ERROR):
        call_command(
            "import_json_resume", str(path), owner=owner.username, slug="synthetic"
        )
    assert not Resume.objects.exists()


@pytest.mark.parametrize(
    "url",
    [
        "https://[broken/resume.json",
        "https://example.com\uff0fprivate/resume.json",
        "https://example.com:invalid/resume.json",
        "https://example.com:99999/resume.json",
    ],
)
def test_invalid_authority_is_rejected_before_network(url, monkeypatch):
    resolve = Mock(side_effect=AssertionError("DNS must not run"))
    connect = Mock(side_effect=AssertionError("HTTP must not run"))
    monkeypatch.setattr(importer.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(importer, "_connection_for_url", connect)
    with pytest.raises(importer.JsonResumeImportError) as error:
        importer.load_document_url(url)
    assert str(error.value) == "Invalid JSON Resume URL authority"
    assert error.value.field == "source_url"
    resolve.assert_not_called()
    connect.assert_not_called()


def test_valid_public_ipv6_is_still_pinned(monkeypatch):
    resolve = Mock(return_value=[(10, 1, 6, "", ("2606:4700:4700::1111", 8443, 0, 0))])
    monkeypatch.setattr(importer.socket, "getaddrinfo", resolve)
    result = importer._validate_import_url(
        "https://[2606:4700:4700::1111]:8443/resume.json"
    )
    assert result.address == result.hostname == "2606:4700:4700::1111"
    assert result.host_header == "[2606:4700:4700::1111]:8443"
    assert result.port == 8443


def test_stricter_integer_conversion_limit_is_normalized(monkeypatch):
    def limited_int(token):
        raise ValueError("synthetic runtime integer limit")

    monkeypatch.setattr(importer, "int", limited_int, raising=False)
    with pytest.raises(importer.JsonResumeImportError, match=INTEGER_ERROR):
        importer.load_document_bytes(b'{"extension":123}')
