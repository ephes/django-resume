from typing import Any, Type

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


class EducationForContext:
    def __init__(
        self,
        school_name: str,
        school_url: str,
        start: str,
        end: str,
        templates: SimpleTemplates,
        edit_url: str,
    ):
        self.school_name = school_name
        self.school_url = school_url
        self.start = start
        self.end = end
        self.templates = templates
        self.edit_url = edit_url


class EducationPlugin(SimplePlugin):
    name: str = "education"
    verbose_name: str = "Education"
    templates = SimpleTemplates(
        main="django_resume/plain/education.html",
        form="django_resume/plain/education_form.html",
    )

    @staticmethod
    def get_form_classes() -> dict[str, Type[forms.Form]]:
        return {"admin": EducationForm, "inline": EducationForm}

    def get_context(
        self, plugin_data, person_pk, *, context: dict[str, Any]
    ) -> EducationForContext:
        education = EducationForContext(
            school_name=plugin_data.get("school_name", "School name"),
            school_url=plugin_data.get("school_url", "https://example.org"),
            start=plugin_data.get("start", "start"),
            end=plugin_data.get("end", "end"),
            templates=self.templates,
            edit_url=self.inline.get_edit_url(person_pk),
        )
        return education
