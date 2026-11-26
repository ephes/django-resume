"""Shared Markdown descriptions for projects and both timelines."""

from typing import Any, cast

from django import forms

from ..markdown import (
    MAX_MARKDOWN_CHARS,
    markdown_to_html,
    textarea_input_to_markdown,
    underlined_link_handler,
)
from .base import EditorTextField, prepare_editor_text


class DescriptionField(EditorTextField):
    _legacy_text: str | None = None

    def __init__(self) -> None:
        super().__init__(max_length=MAX_MARKDOWN_CHARS)

    def clean(self, value: Any) -> str:
        if self._legacy_text is not None and self._is_blank(value):
            return self._legacy_text
        return super().clean(value)

    def _is_blank(self, value: Any) -> bool:
        # A cleared contenteditable can still submit markup such as ``<br>``.
        try:
            text = textarea_input_to_markdown(self.to_python(value) or "")
        except ValueError:
            return False
        return not text.strip()


def prepare_description(form: forms.Form) -> str:
    stored = form.initial.get("description", "")
    if len(stored) > MAX_MARKDOWN_CHARS:
        field = cast(DescriptionField, form.fields["description"])
        field._legacy_text = stored
        if not form.data.get(form.add_prefix("description")):
            field.help_text = (
                "Leave the replacement blank to keep the oversized description. "
                "Copy the original from your private JSON Resume export to shorten it."
            )
        # The original stays server-side. The signed revision still covers it.
        form.initial = {**form.initial, "description": ""}
    return prepare_editor_text(form, "description")


def render_description(text: str) -> str:
    if len(text) > MAX_MARKDOWN_CHARS:
        return "Description exceeds the Markdown display limit."
    return markdown_to_html(text, handlers={"link": underlined_link_handler})
