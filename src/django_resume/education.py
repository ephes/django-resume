from typing import Any

from django import forms

from .plugins import SimplePlugin, SimpleTemplates


class EducationForm(forms.Form):
    school_name = forms.CharField(label="School name", max_length=100)
    school_url = forms.CharField(label="School url", max_length=100)
    start = forms.CharField(widget=forms.TextInput(), required=False)
    end = forms.CharField(widget=forms.TextInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_initial()

    def set_initial(self):
        self.fields["school_name"].initial = "School name"
        self.fields["school_url"].initial = "https://example.com"
        self.fields["start"].initial = "start"
        self.fields["end"].initial = "end"

    @staticmethod
    def set_context(data: dict, context: dict[str, Any]) -> dict[str, Any]:
        context["education"] = {
            "school_url": data["school_url"],
            "school_name": data["school_name"],
            "start": data["start"],
            "end": data["end"],
            "edit_url": context["edit_url"],
        }
        return context


class EducationPlugin(SimplePlugin):
    name: str = "education"
    verbose_name: str = "Education"
    templates = SimpleTemplates(
        main="django_resume/plain/education.html",
        form="django_resume/plain/education_form.html",
    )
    admin_form_class = inline_form_class = EducationForm
