from typing import Type

from django import forms
from django.http import HttpRequest

from .base import ListPlugin, ListItemFormMixin, ListInline, ContextDict

from ..markdown import (
    markdown_to_html,
    textarea_input_to_markdown,
    markdown_to_textarea_input,
)


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
            "text": markdown_to_html(item["text"]),
            "edit_url": context["edit_url"],
            "delete_url": context["delete_url"],
        }
        return context


class CoverFlatForm(forms.Form):
    title = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=50, initial="Cover Title"
    )

    @staticmethod
    def set_context(item: dict, context: ContextDict) -> ContextDict:
        context["cover"] = {"title": item.get("title", "")}
        context["cover"]["edit_flat_url"] = context["edit_flat_url"]
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
            item["text"] = markdown_to_html(item["text"])
        return context
