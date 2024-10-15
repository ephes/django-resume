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
