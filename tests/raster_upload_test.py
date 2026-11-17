"""Complete synthetic raster admission, through real form/storage boundaries."""

import struct

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from django_resume.images import validate_image_upload
from tests.conftest import raster_bytes
from tests.editor_helpers import post_current_editor
from tests.images_test import OneImageForm, TwoImageForm, stored_uploads


@pytest.mark.parametrize("format", ["JPEG", "PNG", "GIF", "WEBP"])
@pytest.mark.parametrize("damage", ["header", "truncated", "corrupt"])
def test_incomplete_raster_refuses_every_upload(in_memory_storage, format, damage):
    content = raster_bytes(format)
    if damage == "header":
        if format == "JPEG":
            content = content[: content.index(b"\xff\xda")]
        else:
            content = content[: {"PNG": 24, "GIF": 10, "WEBP": 30}[format]]
    elif damage == "truncated":
        content = content[:-8]
    else:
        if format == "PNG":
            offset = content.index(b"IDAT") + 4
            content = content[:offset] + b"broken" + content[offset + 6 :]
        elif format == "GIF":
            offset = content.index(b"\x2c") + 10  # LZW minimum code size
            content = content[:offset] + b"\xff" + content[offset + 1 :]
        elif format == "JPEG":
            offset = content.index(b"\xff\xda")
            content = content[:offset] + b"\xff\xda\xff\xff" + content[offset + 4 :]
        else:
            content = content[:20] + b"\xff\xff\xff" + content[23:]
    form = TwoImageForm(
        data={},
        files={
            "avatar_img": SimpleUploadedFile("good.png", raster_bytes("PNG")),
            "signature_img": SimpleUploadedFile("broken", content),
        },
    )
    assert not form.is_valid()
    assert "Upload a valid image" in str(form.errors["signature_img"])
    assert stored_uploads() == []


@pytest.mark.parametrize(
    "format,animated",
    [
        ("JPEG", False),
        ("PNG", False),
        ("GIF", False),
        ("WEBP", False),
        ("PNG", True),
        ("GIF", True),
        ("WEBP", True),
    ],
)
def test_complete_raster_stores_original_bytes(in_memory_storage, format, animated):
    from django.core.files.storage import default_storage

    content = raster_bytes(format, animated=animated)
    form = OneImageForm(
        data={}, files={"avatar_img": SimpleUploadedFile("untrusted.svg", content)}
    )
    assert form.is_valid(), form.errors
    assert (
        form.cleaned_data["avatar_img_width"],
        form.cleaned_data["avatar_img_height"],
    ) == (3, 2)
    with default_storage.open(form.cleaned_data["avatar_img"], "rb") as stored:
        assert stored.read() == content


def test_form_reads_upload_once(in_memory_storage):
    class ChangingUpload(SimpleUploadedFile):
        reads = 0

        def chunks(self, chunk_size=None):
            self.reads += 1
            yield raster_bytes("PNG") if self.reads == 1 else b"GIF89a\x01\x00\x01\x00"

    upload = ChangingUpload("synthetic", b"x")
    form = OneImageForm(data={}, files={"avatar_img": upload})
    assert form.is_valid(), form.errors
    assert upload.reads == 1
    from django.core.files.storage import default_storage

    with default_storage.open(form.cleaned_data["avatar_img"], "rb") as stored:
        assert stored.read() == raster_bytes("PNG")


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["admin", "inline"])
def test_decoder_refusal_preserves_previous_image(
    client, resume, in_memory_storage, surface
):
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django_resume.plugins import plugin_registry

    previous = default_storage.save(
        "uploads/previous.png", ContentFile(raster_bytes("PNG"))
    )
    original = {"identity": {"name": "Synthetic", "avatar_img": previous}}
    resume.plugin_data = original
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_registry.get_plugin("identity")
    url = (
        plugin.admin.get_change_post_url(resume.pk)
        if surface == "admin"
        else plugin.inline.get_post_url(resume.pk)
    )
    response = post_current_editor(
        client,
        url,
        {
            "name": "Changed",
            "clear_avatar": "on",
            "avatar_img": SimpleUploadedFile("truncated.png", raster_bytes("PNG")[:24]),
        },
    )
    assert response.status_code == 200
    assert "Upload a valid image" in response.content.decode()
    resume.refresh_from_db()
    assert resume.plugin_data == original
    assert stored_uploads() == ["previous.png"]


def test_animation_pixel_work_is_bounded(monkeypatch):
    from django_resume import images
    from django import forms

    monkeypatch.setattr(images, "MAX_IMAGE_PIXELS", 6)
    with pytest.raises(forms.ValidationError, match="pixels"):
        validate_image_upload(
            SimpleUploadedFile("animated.gif", raster_bytes("GIF", animated=True))
        )


def test_pixel_admission_precedes_decoder(monkeypatch):
    from django import forms
    from django_resume import images

    def unexpected(*args, **kwargs):
        pytest.fail("decoder ran before dimension admission")

    monkeypatch.setattr(Image, "open", unexpected)
    content = (
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 4 + b"IHDR" + struct.pack(">II", 20000, 1)
    )
    with pytest.raises(forms.ValidationError, match="dimensions"):
        images.validate_image_upload(SimpleUploadedFile("large.png", content))


@pytest.mark.parametrize("format", ["JPEG", "PNG", "GIF", "WEBP"])
def test_missing_raster_terminator_is_rejected(in_memory_storage, format):
    content = raster_bytes(format)[:-1]
    form = OneImageForm(
        data={}, files={"avatar_img": SimpleUploadedFile("incomplete", content)}
    )
    assert not form.is_valid()
    assert stored_uploads() == []


@pytest.mark.parametrize("format", ["PNG", "GIF", "WEBP"])
def test_damaged_later_frame_is_rejected(in_memory_storage, format):
    content = raster_bytes(format, animated=True)
    if format == "PNG":
        offset = content.index(b"fdAT") + 8
        content = content[:offset] + b"broken" + content[offset + 6 :]
    elif format == "GIF":
        content = content[:-8] + b";"
    else:
        content = content[:-8]
    form = OneImageForm(
        data={}, files={"avatar_img": SimpleUploadedFile("incomplete", content)}
    )
    assert not form.is_valid()
    assert stored_uploads() == []


def test_lenient_host_decoder_cannot_admit_uploads(monkeypatch, in_memory_storage):
    from PIL import ImageFile

    monkeypatch.setattr(ImageFile, "LOAD_TRUNCATED_IMAGES", True)
    form = OneImageForm(
        data={},
        files={
            "avatar_img": SimpleUploadedFile(
                "incomplete.jpg", raster_bytes("JPEG")[:-2]
            )
        },
    )
    assert not form.is_valid()
    assert "Upload a valid image" in str(form.errors)
    assert stored_uploads() == []
