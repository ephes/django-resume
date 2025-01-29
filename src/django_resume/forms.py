from django import forms

from django_resume.models import Resume, Plugin


class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ["name", "slug"]


class PluginForm(forms.ModelForm):
    llm = forms.BooleanField(required=False)

    class Meta:
        model = Plugin
        fields = [
            "name",
            "model",
            "prompt",
            "module",
            "form_template",
            "content_template",
            "llm",
        ]
