from collections.abc import Iterable
from typing import Any, cast

from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile


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
            cleaned_data["avatar_img"] = default_storage.save(
                f"uploads/{image.name}", ContentFile(image.read())
            )
            image_handled = True

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
