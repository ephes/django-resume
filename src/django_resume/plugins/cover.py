from typing import Type, cast, Any

from django import forms
from django.core.files.storage import default_storage
from django.http import HttpRequest

from .base import ListPlugin, ListItemFormMixin, ListInline, ContextDict

from ..markdown import (
    markdown_to_html,
    textarea_input_to_markdown,
    markdown_to_textarea_input,
)
from ..images import ImageFormMixin


def link_handler(text: str, url: str) -> str:
    return f'<a href="{url}" class="underlined">{text}</a>'


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

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        # Transform initial text from markdown to textarea input.
        initial = cast(dict[str, Any], self.initial)
        initial["text"] = markdown_to_textarea_input(self.initial.get("text", ""))
        self.initial = initial

    def clean_text(self) -> str:
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


class CoverFlatForm(ImageFormMixin, forms.Form):
    title = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=50, initial="Cover Title"
    )
    avatar_img = forms.FileField(
        label="Profile Image",
        max_length=100,
        required=False,
    )
    clear_avatar = forms.BooleanField(
        widget=forms.CheckboxInput, initial=False, required=False
    )
    avatar_alt = forms.CharField(
        label="Profile photo alt text",
        max_length=100,
        initial="Profile photo",
        required=False,
    )
    image_fields = [("avatar_img", "clear_avatar")]

    @property
    def avatar_img_url(self) -> str:
        return self.get_image_url_for_field(self.initial.get("avatar_img", ""))

    @staticmethod
    def set_context(item: dict, context: ContextDict) -> ContextDict:
        image_url = ImageFormMixin.get_image_url_for_field(item.get("avatar_img", ""))
        context["cover"] = {
            "title": item.get("title", ""),
            "avatar_alt": item.get("avatar_alt", ""),
            "avatar_img": image_url,
            "avatar_img_url": image_url,
            "edit_flat_url": context["edit_flat_url"],
        }
        return context


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
        # first item is special because it should float around the avatar image
        context["first_item"] = items[0] if items else None
        # add avatar image url
        context["avatar_img_url"] = default_storage.url(
            plugin_data.get("flat", {}).get("avatar_img", "")
        )
        return context
