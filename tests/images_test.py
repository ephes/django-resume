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
