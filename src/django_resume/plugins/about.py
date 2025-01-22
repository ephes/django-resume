from django import forms

from .base import SimplePlugin


class AboutForm(forms.Form):
    title = forms.CharField(label="Title", max_length=256, initial="About")
    text = forms.CharField(
        label="About",
        max_length=1024,
        initial="Some about text...",
        widget=forms.Textarea,
    )


class AboutPlugin(SimplePlugin):
    name: str = "about"
    verbose_name: str = "About"
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
