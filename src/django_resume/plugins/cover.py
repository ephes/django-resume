from typing import Type

from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.http import HttpRequest
from django.core.files.uploadedfile import InMemoryUploadedFile


from .base import ListPlugin, ListItemFormMixin, ListInline, ContextDict

from ..markdown import (
    markdown_to_html,
    textarea_input_to_markdown,
    markdown_to_textarea_input,
)


def link_handler(text, url):
    return f'<a href="{url}" class="underlined">{text}</a>'


class CustomFileObject:
    def __init__(self, filename):
        self.name = filename
        self.url = default_storage.url(filename)

    def __str__(self):
        return self.name


class CoverItemForm(ListItemFormMixin, forms.Form):
    title = forms.CharField(
        label="Cover Letter Title",
        max_length=256,
        initial="Cover Title",
    )
    text = forms.CharField(
        label="Cover Letter Text",
        max_length=4096,
        initial="Some cover letter text...",
        widget=forms.Textarea(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Transform initial text from markdown to textarea input.
        self.initial["text"] = markdown_to_textarea_input(self.initial.get("text", ""))

    def clean_text(self):
        text = self.cleaned_data["text"]
        text = textarea_input_to_markdown(text)
        return text

    @staticmethod
    def get_initial() -> ContextDict:
        """Just some default values."""
        return {
            "title": "Cover item title",
            "text": "Some cover paragraph...",
        }

    def set_context(self, item: dict, context: ContextDict) -> ContextDict:
        context["item"] = {
            "id": item["id"],
            "title": item["title"],
            "text": markdown_to_html(item["text"], handlers={"link": link_handler}),
            "edit_url": context["edit_url"],
            "delete_url": context["delete_url"],
        }
        return context


class CoverFlatForm(forms.Form):
    title = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=50, initial="Cover Title"
    )
    avatar_img = forms.FileField(
        label="Profile Image",
        max_length=100,
        required=False,
    )
    avatar_alt = forms.CharField(
        label="Profile photo alt text",
        max_length=100,
        initial="Profile photo",
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial image
        initial_avatar_img_filename = self.initial.get("avatar_img")
        if initial_avatar_img_filename is not None:
            self.fields["avatar_img"].initial = CustomFileObject(
                initial_avatar_img_filename
            )

    @property
    def avatar_img_url(self):
        return default_storage.url(self.initial.get("avatar_img", ""))

    @staticmethod
    def set_context(item: dict, context: ContextDict) -> ContextDict:
        image_url = default_storage.url(item.get("avatar_img", ""))
        context["cover"] = {
            "title": item.get("title", ""),
            "avatar_alt": item.get("avatar_alt", ""),
            "avatar_img": image_url,
            "avatar_img_url": image_url,
            "edit_flat_url": context["edit_flat_url"],
        }
        return context

    def clean(self):
        # super ugly - FIXME
        cleaned_data = super().clean()
        avatar_img = cleaned_data.get("avatar_img")

        set_new_avatar_image = isinstance(avatar_img, InMemoryUploadedFile)
        if set_new_avatar_image:
            if avatar_img.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Image file too large ( > 2mb )")
            cleaned_data["avatar_img"] = default_storage.save(
                f"uploads/{avatar_img.name}", ContentFile(avatar_img.read())
            )

        keep_current_avatar = isinstance(avatar_img, str)

        if keep_current_avatar:
            cleaned_data["avatar_img"] = avatar_img

        return cleaned_data


class CoverPlugin(ListPlugin):
    name: str = "cover"
    verbose_name: str = "Cover Letter"
    inline: ListInline

    @staticmethod
    def get_form_classes() -> dict[str, Type[forms.Form]]:
        return {"item": CoverItemForm, "flat": CoverFlatForm}

    def get_context(
        self,
        _request: HttpRequest,
        plugin_data: dict,
        resume_pk: int,
        *,
        context: ContextDict,
        edit: bool = False,
        theme: str = "plain",
    ) -> ContextDict:
        context = super().get_context(
            _request, plugin_data, resume_pk, context=context, edit=edit, theme=theme
        )
        # convert markdown to html for rendering
        items = plugin_data.get("items", [])
        for item in items:
            item["text"] = markdown_to_html(
                item["text"], handlers={"link": link_handler}
            )
        # add avatar image url
        context["avatar_img_url"] = default_storage.url(
            plugin_data.get("flat", {}).get("avatar_img", "")
        )
        return context
