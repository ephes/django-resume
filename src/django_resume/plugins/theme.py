from django import forms
from django.http import HttpRequest

from .base import SimplePlugin, ContextDict


class ThemeForm(forms.Form):
    name = forms.CharField(
        label="Theme Name",
        max_length=100,
        initial="plain",
    )


class ThemePlugin(SimplePlugin):
    name: str = "theme"
    verbose_name: str = "Theme Selector"
    admin_form_class = inline_form_class = ThemeForm
    prompt = """
        Create a django-resume plugin that allows users to select a visual theme for their content from
        a dropdown menu. The plugin provides a simple way to switch between different themes,
        ensuring a personalized appearance. Users can choose from predefined themes, with the
        default set to “plain.”
        
        The plugin displays the current theme name on the page. When the edit mode is enabled,
        users can select a different theme from a dropdown menu. Once the form is submitted, the
        page refreshes to apply the selected theme.
        
        The editing interface provides an intuitive way to change the theme, with error handling
        to ensure valid selections. The plugin maintains a user-friendly experience by making it
        easy to preview and switch themes without unnecessary complexity.    
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
        if context.get("name") is None:
            context["name"] = "plain"
        return context
