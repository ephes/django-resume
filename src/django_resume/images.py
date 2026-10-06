import io
import struct
import uuid

from collections.abc import Iterable
from typing import IO, Any, cast

from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile


class UnknownImageFormat(Exception):
    pass


MAX_IMAGE_UPLOAD_SIZE = 2 * 1024 * 1024

# Raster formats accepted for uploads, mapped to the file extension used when
# storing them. SVG, HTML and anything else that is not one of these is rejected.
ALLOWED_IMAGE_FORMATS: dict[str, str] = {
    "jpeg": "jpg",
    "png": "png",
    "gif": "gif",
    "webp": "webp",
}

IMAGE_UPLOAD_ACCEPT = "image/jpeg,image/png,image/gif,image/webp"


def detect_image_format(data: bytes) -> str | None:
    """Return the allowed image format of ``data`` by its magic bytes, or None."""
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data.startswith(b"\211PNG\r\n\032\n") and data[12:16] == b"IHDR":
        return "png"
    if data.startswith(b"\377\330\377"):
        return "jpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def validate_image_upload(upload: UploadedFile) -> tuple[bytes, str, int, int]:
    """
    Check that an uploaded file really is an allowed raster image.

    The client's filename and content type are ignored: the format is detected
    from the file content. Returns the file content, the extension to store it
    under, and the image width and height. Raises ``forms.ValidationError``
    for files that are too large, not an allowed image format, or unreadable.
    """
    if upload.size is None or upload.size > MAX_IMAGE_UPLOAD_SIZE:
        raise forms.ValidationError("Image file too large ( > 2mb )")
    upload.seek(0)
    data = b"".join(upload.chunks())
    if len(data) > MAX_IMAGE_UPLOAD_SIZE:
        raise forms.ValidationError("Image file too large ( > 2mb )")
    image_format = detect_image_format(data)
    if image_format is None:
        raise forms.ValidationError(
            "Upload a valid image. Supported formats are JPEG, PNG, GIF and WebP."
        )
    try:
        width, height = get_image_metadata_from_bytesio(io.BytesIO(data), len(data))
    except (UnknownImageFormat, struct.error, ValueError, IndexError):
        raise forms.ValidationError(
            "Upload a valid image. The file could not be read as an image."
        )
    if width <= 0 or height <= 0:
        raise forms.ValidationError(
            "Upload a valid image. The file could not be read as an image."
        )
    return data, ALLOWED_IMAGE_FORMATS[image_format], width, height


def get_image_metadata_from_bytesio(input: IO[bytes], size: int) -> tuple[int, int]:
    data = input.read(32)  # Increased read size for WebP format detection
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
            # WebP extended format with VP8X chunk: 24-bit canvas width and
            # height minus one, little endian, at offsets 24 and 27
            if len(data) < 30:
                raise UnknownImageFormat("Truncated WebP VP8X header")
            width = int.from_bytes(data[24:27], "little") + 1
            height = int.from_bytes(data[27:30], "little") + 1
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
            self.fields[field_name].widget.attrs.setdefault(
                "accept", IMAGE_UPLOAD_ACCEPT
            )
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
        is_upload = isinstance(image, UploadedFile)
        just_clear_the_image = clear_image and not is_upload
        if just_clear_the_image:
            cleaned_data[image_field] = None
            image_handled = True

        set_new_image = is_upload and not image_handled
        if set_new_image:
            assert isinstance(image, UploadedFile)
            try:
                data, extension, width, height = validate_image_upload(image)
            except forms.ValidationError as error:
                # attach the error to the upload field
                raise forms.ValidationError({image_field: error.messages})
            # never trust the client's filename: store under a generated name
            # with the extension of the detected format
            cleaned_data[image_field] = default_storage.save(
                f"uploads/{uuid.uuid4().hex}.{extension}", ContentFile(data)
            )
            image_handled = True
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
        # Validate every upload before storing any of them, so a rejected file
        # never leaves another upload of the same form behind in storage.
        has_invalid_upload = False
        for image_field, _clear_field in self.image_fields:
            image = cleaned_data.get(image_field)
            if isinstance(image, UploadedFile):
                try:
                    validate_image_upload(image)
                except forms.ValidationError as error:
                    self.add_error(image_field, error)  # type: ignore[attr-defined]
                    has_invalid_upload = True
        if has_invalid_upload or self.errors:  # type: ignore[attr-defined]
            # do not store uploads for a form that will be rejected anyway
            return cleaned_data
        for image_field, clear_field in self.image_fields:
            cleaned_data = self.do_clean_image_field(
                cleaned_data, image_field, clear_field
            )
        return cleaned_data
