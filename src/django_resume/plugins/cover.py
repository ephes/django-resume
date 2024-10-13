from django import forms
from django.http import HttpRequest

from .base import SimplePlugin, SimpleTemplates, ContextDict
from ..markdown import (
    markdown_to_html,
    textarea_input_to_markdown,
    markdown_to_textarea_input,
)


class CoverForm(forms.Form):
    title = forms.CharField(
        label="Cover Letter Title",
        max_length=256,
        initial="Cover Title",
    )
    text = forms.CharField(
        label="Cover Letter Text",
        max_length=1024,
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


class CoverPlugin(SimplePlugin):
    name: str = "cover"
    verbose_name: str = "Cover Letter"
    templates = SimpleTemplates(
        main="django_resume/cover/plain/content.html",
        form="django_resume/cover/plain/form.html",
    )
    admin_form_class = inline_form_class = CoverForm

    def get_context(
        self,
        _request: HttpRequest,
        plugin_data: dict,
        resume_pk: int,
        *,
        context: ContextDict,
        edit: bool = False,
    ) -> ContextDict:
        context = super().get_context(
            _request, plugin_data, resume_pk, context=context, edit=edit
        )
        cover_text = plugin_data.get("text")
        print("cover_text", cover_text)
        if cover_text is not None:
            context["text"] = markdown_to_html(cover_text)
        return context
