from django import forms

from .base import SimplePlugin


class EducationForm(forms.Form):
    school_name = forms.CharField(
        label="School name", max_length=100, initial="School name"
    )
    school_url = forms.URLField(
        label="School url",
        max_length=100,
        initial="https://example.com",
        assume_scheme="https",
    )
    start = forms.CharField(widget=forms.TextInput(), required=False, initial="start")
    end = forms.CharField(widget=forms.TextInput(), required=False, initial="end")


class EducationPlugin(SimplePlugin):
    name: str = "education"
    verbose_name: str = "Education"
    admin_form_class = inline_form_class = EducationForm
    prompt = """
        Create a django-resume plugin to display education-related information. The plugin should
        include fields for the school name, school URL, start date, and end date. The start and
        end dates are optional. The plugin should be named "education" with the verbose name
        set to "Education".
        
        When rendered, the plugin should display the title “Education,” with the school name
        shown as a clickable link to the provided school URL, aligned to the left. The start and
        end dates should be displayed on the right, formatted as either “YYYY” or “YYYY-MM”.
    """
