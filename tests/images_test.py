from django import forms
from django.core.files.uploadedfile import SimpleUploadedFile

from django_resume.images import ImageFormMixin

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
    assert form.cleaned_data["signature_img"].startswith("uploads/signature")
    assert form.cleaned_data["signature_img_width"] == 7
    assert form.cleaned_data["signature_img_height"] == 3
    assert "avatar_img_width" not in form.cleaned_data
