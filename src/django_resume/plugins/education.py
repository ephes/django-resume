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
        include fields for the school name, school URL, start date, and end date. The school name
        and URL are required, while the start and end dates are optional. The plugin should be
        named "education", with the verbose name set to "Education". The form’s data should be
        JSON serializable.
        
        When displayed, the plugin should show the title "Education", with the school name as
        a clickable link leading to the provided school URL, aligned to the left. The start and
        end dates should appear on the right, formatted as either `"YYYY"` or `"YYYY-MM"`.
        An edit button should be shown next to the section title when editing is enabled.      
    """
