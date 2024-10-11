from django import forms

from .base import SimplePlugin, SimpleTemplates


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
        widget=forms.Textarea,
    )


class CoverPlugin(SimplePlugin):
    name: str = "cover"
    verbose_name: str = "Cover Letter"
    templates = SimpleTemplates(
        main="django_resume/cover/plain/content.html",
        form="django_resume/cover/plain/form.html",
    )
    admin_form_class = inline_form_class = CoverForm
