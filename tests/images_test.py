import re
import struct

import pytest
from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile, TemporaryUploadedFile

from django_resume.images import (
    IMAGE_UPLOAD_ACCEPT,
    MAX_IMAGE_UPLOAD_SIZE,
    ImageFormMixin,
    detect_image_format,
)

from .conftest import png_bytes


class TwoImageForm(ImageFormMixin, forms.Form):
    avatar_img = forms.FileField(required=False)
    clear_avatar = forms.BooleanField(required=False)
    signature_img = forms.FileField(required=False)
    clear_signature = forms.BooleanField(required=False)
    image_fields = [
        ("avatar_img", "clear_avatar"),
        ("signature_img", "clear_signature"),
    ]


def test_second_image_field_records_its_own_dimensions(in_memory_storage):
    # Given a form with two image fields and an upload only for the second one
    upload = SimpleUploadedFile(
        "signature.png", png_bytes(7, 3), content_type="image/png"
    )
    form = TwoImageForm(data={}, files={"signature_img": upload})

    # When the form is cleaned
    assert form.is_valid(), form.errors

    # Then the dimensions come from the uploaded signature, not the avatar field
    assert re.fullmatch(
        r"uploads/[0-9a-f]{32}\.png", form.cleaned_data["signature_img"]
    )
    assert form.cleaned_data["signature_img_width"] == 7
    assert form.cleaned_data["signature_img_height"] == 3
    assert "avatar_img_width" not in form.cleaned_data


def stored_uploads() -> list[str]:
    from django.core.files.storage import default_storage

    try:
        return default_storage.listdir("uploads")[1]
    except FileNotFoundError:
        return []


class OneImageForm(ImageFormMixin, forms.Form):
    avatar_img = forms.FileField(required=False)
    clear_avatar = forms.BooleanField(required=False)
    image_fields = [("avatar_img", "clear_avatar")]


def gif_bytes(width: int, height: int) -> bytes:
    return b"GIF89a" + struct.pack("<HH", width, height) + b"\x00" * 20 + b";"


def jpeg_bytes(width: int, height: int) -> bytes:
    sof = b"\xff\xc0" + struct.pack(">HBHH", 11, 8, height, width) + b"\x01\x11\x00"
    return b"\xff\xd8" + sof + b"\xff\xda\x00\x02" + b"\x00" * 8 + b"\xff\xd9"


def webp_vp8x_bytes(width: int, height: int) -> bytes:
    payload = (
        b"\x00\x00\x00\x00"
        + (width - 1).to_bytes(3, "little")
        + (height - 1).to_bytes(3, "little")
    )
    chunk = b"VP8X" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", 4 + len(chunk)) + b"WEBP" + chunk


@pytest.mark.parametrize(
    "name, content",
    [
        ("evil.png", b"<html><script>alert(1)</script></html>"),
        ("evil.html", b"<!doctype html><script>alert(1)</script>"),
        (
            "evil.svg",
            b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
        ),
        ("bitmap.bmp", b"BM" + b"\x00" * 40),
        ("truncated.png", b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR"),
        ("noframe.jpg", b"\xff\xd8\xff\xda\x00\x02"),
    ],
)
def test_non_image_uploads_are_rejected(in_memory_storage, name, content):
    # Given an upload that is not an allowed raster image, whatever its name
    upload = SimpleUploadedFile(name, content, content_type="image/png")
    form = OneImageForm(data={}, files={"avatar_img": upload})

    # Then the form is invalid with an error on the field and nothing is stored
    assert not form.is_valid()
    assert "Upload a valid image" in form.errors["avatar_img"][0]
    assert stored_uploads() == []


def test_oversize_upload_is_rejected(in_memory_storage):
    content = png_bytes(1, 1) + b"\x00" * (MAX_IMAGE_UPLOAD_SIZE + 1)
    upload = SimpleUploadedFile("big.png", content, content_type="image/png")
    form = OneImageForm(data={}, files={"avatar_img": upload})

    assert not form.is_valid()
    assert "too large" in form.errors["avatar_img"][0]
    assert stored_uploads() == []


def test_valid_png_is_saved_under_generated_name(in_memory_storage):
    # Given a valid PNG whose client filename tries to escape the upload dir
    upload = SimpleUploadedFile(
        "../../evil.html", png_bytes(5, 6), content_type="text/html"
    )
    form = OneImageForm(data={}, files={"avatar_img": upload})

    assert form.is_valid(), form.errors
    path = form.cleaned_data["avatar_img"]
    assert re.fullmatch(r"uploads/[0-9a-f]{32}\.png", path)
    assert (
        form.cleaned_data["avatar_img_width"],
        form.cleaned_data["avatar_img_height"],
    ) == (5, 6)
    assert stored_uploads() == [path.removeprefix("uploads/")]


@pytest.mark.parametrize(
    "content, extension, size",
    [
        (gif_bytes(3, 4), "gif", (3, 4)),
        (jpeg_bytes(640, 480), "jpg", (640, 480)),
        (webp_vp8x_bytes(1000, 70000), "webp", (1000, 70000)),
    ],
)
def test_allowed_formats_use_detected_extension(
    in_memory_storage, content, extension, size
):
    upload = SimpleUploadedFile("photo.png", content, content_type="image/png")
    form = OneImageForm(data={}, files={"avatar_img": upload})

    assert form.is_valid(), form.errors
    assert form.cleaned_data["avatar_img"].endswith(f".{extension}")
    assert (
        form.cleaned_data["avatar_img_width"],
        form.cleaned_data["avatar_img_height"],
    ) == size


def test_temporary_file_upload_is_validated_and_saved(in_memory_storage):
    # Uploads above the in-memory threshold arrive as TemporaryUploadedFile
    upload = TemporaryUploadedFile("photo.png", "image/png", 0, None)
    upload.write(png_bytes(2, 9))
    upload.size = upload.tell()
    upload.seek(0)
    form = OneImageForm(data={}, files={"avatar_img": upload})

    assert form.is_valid(), form.errors
    assert re.fullmatch(r"uploads/[0-9a-f]{32}\.png", form.cleaned_data["avatar_img"])
    assert form.cleaned_data["avatar_img_height"] == 9
    upload.close()


def test_one_invalid_upload_stores_nothing(in_memory_storage):
    # Given a valid avatar and an invalid signature in the same form
    form = TwoImageForm(
        data={},
        files={
            "avatar_img": SimpleUploadedFile("a.png", png_bytes(1, 1)),
            "signature_img": SimpleUploadedFile("s.svg", b"<svg></svg>"),
        },
    )

    # Then the form is invalid and the valid avatar was not stored either
    assert not form.is_valid()
    assert "signature_img" in form.errors
    assert stored_uploads() == []


def test_upload_widget_advertises_allowed_types():
    form = OneImageForm()
    assert form.fields["avatar_img"].widget.attrs["accept"] == IMAGE_UPLOAD_ACCEPT


@pytest.mark.parametrize(
    "content, expected",
    [
        (png_bytes(1, 1), "png"),
        (b"GIF87a\x01\x00\x01\x00", "gif"),
        (b"\xff\xd8\xff\xe0", "jpeg"),
        (b"RIFF\x00\x00\x00\x00WEBPVP8 ", "webp"),
        (b"<svg/>", None),
        (b"BM\x00\x00", None),
        (b"", None),
    ],
)
def test_detect_image_format(content, expected):
    assert detect_image_format(content) == expected


def test_second_storage_failure_removes_first_upload(in_memory_storage, monkeypatch):
    from django.core.files.storage import default_storage

    original_save = default_storage.save
    calls = []

    def fail_second(name, content):
        calls.append(name)
        if len(calls) == 2:
            raise OSError("storage unavailable")
        return original_save(name, content)

    monkeypatch.setattr(default_storage, "save", fail_second)
    form = TwoImageForm(
        data={},
        files={
            "avatar_img": SimpleUploadedFile("a.png", png_bytes(1, 1)),
            "signature_img": SimpleUploadedFile("s.png", png_bytes(2, 2)),
        },
    )
    with pytest.raises(OSError, match="storage unavailable"):
        form.is_valid()
    assert len(calls) == 2
    assert stored_uploads() == []


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["admin", "inline", "cover_admin", "cover_inline"])
def test_failed_resume_save_preserves_old_images(
    client, resume, in_memory_storage, monkeypatch, surface
):
    from django.core.files.base import ContentFile
    from django.core.files.storage import default_storage
    from django_resume.models import Resume
    from django_resume.plugins import plugin_registry

    resume.owner.is_staff = True
    resume.owner.is_superuser = True
    resume.owner.save()
    old_bytes = png_bytes(3, 3)
    old_path = default_storage.save("uploads/old.png", ContentFile(old_bytes))
    is_cover = surface.startswith("cover")
    field = "signature_img" if is_cover else "avatar_img"
    old_data = (
        {"cover": {"flat": {field: old_path}, "items": []}}
        if is_cover
        else {"identity": {"name": "Old", field: old_path}}
    )
    resume.plugin_data = old_data
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_registry.get_plugin("cover" if is_cover else "identity")
    urls = {
        "admin": lambda: plugin.admin.get_change_post_url(resume.pk),
        "inline": lambda: plugin.inline.get_post_url(resume.pk),
        "cover_admin": lambda: plugin.admin.get_change_flat_post_url(resume.pk),
        "cover_inline": lambda: plugin.inline.get_edit_flat_post_url(resume.pk),
    }
    calls = []

    def fail_save(self, *args, **kwargs):
        calls.append(self.pk)
        raise OSError("database unavailable")

    monkeypatch.setattr(Resume, "save", fail_save)
    with pytest.raises(OSError, match="database unavailable"):
        client.post(
            urls[surface](),
            {"name": "New", field: SimpleUploadedFile("new.png", png_bytes(2, 2))},
        )
    assert calls == [resume.pk]
    resume.refresh_from_db()
    assert resume.plugin_data == old_data
    assert stored_uploads() == ["old.png"]
    assert default_storage.open(old_path).read() == old_bytes


@pytest.mark.django_db
def test_admin_render_failure_keeps_committed_upload(
    client, resume, in_memory_storage, monkeypatch
):
    from django_resume.plugins import plugin_registry
    from django_resume.plugins import base

    resume.owner.is_staff = True
    resume.owner.is_superuser = True
    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_registry.get_plugin("identity")

    def fail_render(*args, **kwargs):
        raise RuntimeError("render failed")

    monkeypatch.setattr(base, "render", fail_render)
    with pytest.raises(RuntimeError, match="render failed"):
        client.post(
            plugin.admin.get_change_post_url(resume.pk),
            {
                "name": "New",
                "avatar_img": SimpleUploadedFile("new.png", png_bytes(2, 2)),
            },
        )
    resume.refresh_from_db()
    path = resume.plugin_data["identity"]["avatar_img"]
    assert stored_uploads() == [path.removeprefix("uploads/")]


def test_cleanup_attempts_every_new_object(in_memory_storage, monkeypatch):
    from django.core.files.storage import default_storage

    form = TwoImageForm(
        data={},
        files={
            "avatar_img": SimpleUploadedFile("a.png", png_bytes(1, 1)),
            "signature_img": SimpleUploadedFile("s.png", png_bytes(2, 2)),
        },
    )
    assert form.is_valid()
    first, second = form.new_image_uploads
    original_delete = default_storage.delete
    calls = []

    def fail_first(name):
        calls.append(name)
        if name == first:
            raise OSError("delete failed")
        original_delete(name)

    monkeypatch.setattr(default_storage, "delete", fail_first)
    with pytest.raises(OSError, match="delete failed"):
        form.cleanup_new_image_uploads()
    assert calls == [first, second]
    assert form.new_image_uploads == [first]
    assert stored_uploads() == [first.removeprefix("uploads/")]
