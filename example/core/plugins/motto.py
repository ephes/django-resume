from django import forms
from django_resume.plugins.base import SimplePlugin


class MottoForm(forms.Form):
    """Form for the motto plugin."""

    title = forms.CharField(
        label="Section Title",
        max_length=100,
        initial="My Motto",
        help_text="The heading for this section",
    )
    quote = forms.CharField(
        label="Motto/Quote",
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        initial="Stay curious, stay humble, keep learning.",
        help_text="Your personal motto or favorite inspirational quote",
    )
    attribution = forms.CharField(
        label="Attribution",
        max_length=200,
        required=False,
        help_text="Author of the quote (optional)",
    )


class MottoPlugin(SimplePlugin):
    name: str = "motto"
    verbose_name: str = "Personal Motto"
    admin_form_class = inline_form_class = MottoForm

    prompt = """
    Create a django-resume plugin to display a personal motto or inspirational quote.
    The plugin should include the quote text and an optional attribution.
    
    The plugin should display the motto prominently with clean typography
    and allow users to edit the content inline. Keep the design simple
    and elegant.
    """
