import io
import struct

from collections.abc import Iterable
from typing import Any, cast

from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile


class UnknownImageFormat(Exception):
    pass


def get_image_metadata_from_bytesio(
    input: InMemoryUploadedFile, size: int
) -> tuple[int, int]:
    data = input.read(30)  # Increased read size for WebP format detection
    msg = " raised while trying to decode as JPEG."

    # Check for GIF format
    if (size >= 10) and data[:6] in (b"GIF87a", b"GIF89a"):
        w, h = struct.unpack("<HH", data[6:10])
        width = int(w)
        height = int(h)

    # Check for PNG format
    elif (
        (size >= 24)
        and data.startswith(b"\211PNG\r\n\032\n")
        and (data[12:16] == b"IHDR")
    ):
        w, h = struct.unpack(">LL", data[16:24])
        width = int(w)
        height = int(h)

    # Check for JPEG format
    elif (size >= 2) and data.startswith(b"\377\330"):
        input.seek(0)
        input.read(2)
        b = input.read(1)
        try:
            while b and ord(b) != 0xDA:
                while ord(b) != 0xFF:
                    b = input.read(1)
                while ord(b) == 0xFF:
                    b = input.read(1)
                if 0xC0 <= ord(b) <= 0xC3:
                    input.read(3)
                    h, w = struct.unpack(">HH", input.read(4))
                    break
                else:
                    input.read(int(struct.unpack(">H", input.read(2))[0]) - 2)
                b = input.read(1)
            width = int(w)
            height = int(h)
        except struct.error:
            raise UnknownImageFormat("StructError" + msg)
        except ValueError:
            raise UnknownImageFormat("ValueError" + msg)
        except Exception as e:
            raise UnknownImageFormat(e.__class__.__name__ + msg)

    # Check for BMP format
    elif (size >= 26) and data.startswith(b"BM"):
        headersize = struct.unpack("<I", data[14:18])[0]
        if headersize == 12:
            w, h = struct.unpack("<HH", data[18:22])
            width = int(w)
            height = int(h)
        elif headersize >= 40:
            w, h = struct.unpack("<ii", data[18:26])
            width = int(w)
            height = abs(int(h))
        else:
            raise UnknownImageFormat("Unknown DIB header size:" + str(headersize))

    # Check for WebP format
    elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8 ":
            # Simple WebP file format with VP8 chunk
            w, h = struct.unpack("<HH", data[26:30])
            width = int(w) & 0x3FFF  # 14-bit width
            height = int(h) & 0x3FFF  # 14-bit height
        elif data[12:16] == b"VP8L":
            # WebP lossless format with VP8L chunk
            w, h = struct.unpack("<HH", data[21:25])
            width = (w & 0x3FFF) + 1
            height = (h & 0x3FFF) + 1
        elif data[12:16] == b"VP8X":
            # WebP extended format with VP8X chunk
            w, h = struct.unpack("<LL", data[24:32])
            width = (w & 0xFFFFFF) + 1
            height = (h & 0xFFFFFF) + 1
        else:
            raise UnknownImageFormat("Unknown WebP format")

    else:
        raise UnknownImageFormat("unknown")

    return width, height


def get_image_dimensions_from_storage(path):
    with default_storage.open(path, "rb") as file:
        file_data = io.BytesIO(file.read())
        size = default_storage.size(path)
        return get_image_metadata_from_bytesio(file_data, size)


class CustomFileObject:
    """
    A simple class to represent a file object with a name and a url.
    This is needed because I cannot use an ImageField from a model,
    because there is no model here, just json data.
    """

    def __init__(self, filename):
        self.name = filename
        self.url = default_storage.url(filename)

    def __str__(self) -> str:
        return self.name


class ImageFormMixin:
    """
    Mixin for forms that have image fields. An image field always has an
    associated clear field. If the clear field is checked, the image field
    will be cleared. If the image field is set to a new image, the old image
    will be cleared. If the image field is set to the same image, nothing
    will happen.

    So you have to define three fields in the form:
        - image_field: The image file field
        - clear_field: The clear checkbox field

    And set the image_fields attribute to a list of tuples accordingly.
    """

    fields: dict
    image_fields: Iterable[tuple[str, str]] = []  # [("image_field", "clear_field")]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        initial = cast(dict[str, Any], self.initial)  # type: ignore
        for field_name, _clear in self.image_fields:
            if initial is None:
                continue
            initial_filename = initial.get(field_name)
            if initial_filename is not None:
                self.fields[field_name].initial = CustomFileObject(initial_filename)

    @staticmethod
    def get_image_url_for_field(image_path: str) -> str:
        return default_storage.url(image_path)

    @staticmethod
    def do_clean_image_field(
        cleaned_data: dict[str, Any], image_field: str, clear_field: str
    ) -> dict[str, Any]:
        image = cleaned_data.get(image_field)
        clear_image = cleaned_data.get(clear_field)

        image_handled = False
        just_clear_the_image = clear_image and not hasattr(image, "temporary_file_path")
        if just_clear_the_image:
            cleaned_data[image_field] = None
            image_handled = True

        set_new_image = isinstance(image, InMemoryUploadedFile) and not image_handled
        if set_new_image:
            assert image is not None
            if image.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Image file too large ( > 2mb )")
            cleaned_data[image_field] = default_storage.save(
                f"uploads/{image.name}", ContentFile(image.read())
            )
            image_handled = True

            # Add image dimensions to cleaned data
            try:
                width, height = get_image_dimensions_from_storage(
                    cleaned_data["avatar_img"]
                )
            except UnknownImageFormat:
                width, height = None, None
            cleaned_data[f"{image_field}_width"] = width
            cleaned_data[f"{image_field}_height"] = height

        keep_current_image = (
            not clear_image and isinstance(clear_image, str) and not image_handled
        )
        if keep_current_image:
            cleaned_data[image_field] = image

        del cleaned_data[clear_field]  # reset the clear image field
        return cleaned_data

    def clean(self) -> dict[str, Any]:
        cleaned_data = super().clean()  # type: ignore
        for image_field, clear_field in self.image_fields:
            cleaned_data = self.do_clean_image_field(
                cleaned_data, image_field, clear_field
            )
        return cleaned_data
