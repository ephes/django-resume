from typing import Any, cast

from django import forms
from django.http import HttpRequest

from .base import SimplePlugin, ContextDict
from ..markdown import (
    markdown_to_html,
    markdown_to_plain_text,
    markdown_to_textarea_input,
    textarea_input_to_html,
    textarea_input_to_markdown,
)
from ..interchange.protocols import AdapterExport


class AboutForm(forms.Form):
    title = forms.CharField(label="Title", max_length=256, initial="About")
    text = forms.CharField(
        label="About",
        max_length=1024,
        initial="Some about text...",
        widget=forms.Textarea,
    )

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        initial = cast(dict[str, Any], self.initial)
        initial["text"] = markdown_to_textarea_input(initial.get("text", ""))
        self.initial = initial
        self.text_display_html = textarea_input_to_html(self["text"].value() or "")

    def clean_text(self) -> str:
        return textarea_input_to_markdown(self.cleaned_data["text"])


class AboutJsonResumeAdapter:
    owned_paths = ("/basics/summary",)
    multivalued_paths: tuple[str, ...] = ()

    def export(self, facts: dict) -> AdapterExport:
        contributions: list[tuple[str, object]] = []
        notes: list[str] = []
        summary = facts.get("summary", "")
        if summary:
            contributions.append(("/basics/summary", summary))
        if facts.get("title"):
            notes.append("about.title has no JSON Resume mapping; not exported")
        return AdapterExport(contributions=contributions, notes=notes)


class AboutPlugin(SimplePlugin):
    name: str = "about"
    verbose_name: str = "About"
    capabilities: tuple[str, ...] = ("summary", "portfolio", "cv")
    admin_form_class = inline_form_class = AboutForm
    prompt = """
        Create a django-resume plugin to display a brief “About” section on a webpage. The plugin
        should include a title and a descriptive text, both of which can be customized. The
        title provides a heading for the section, while the text contains information about the
        subject.

        The plugin should be displayed with the title as an H2 heading followed by the
        descriptive text. An edit button should be available to allow users to modify the
        content inline. When in edit mode, the title and text should be editable, and changes
        should be submitted via a form.

        The plugin should offer a clean and user-friendly interface, ensuring that content
        updates are simple and efficient.
    """

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
        text_markdown = context.pop("text", "")
        context["text_markdown"] = text_markdown
        context["text_plain"] = markdown_to_plain_text(text_markdown)
        context["text_html"] = markdown_to_html(text_markdown)
        return context

    def get_structured_data(self, resume) -> dict:
        data = self.get_data(resume)
        return {"summary": data.get("text", ""), "title": data.get("title", "")}

    def get_export_adapters(self) -> dict:
        return {"json_resume": AboutJsonResumeAdapter()}
