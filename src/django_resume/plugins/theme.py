from django import forms
from django.http import HttpRequest

from .base import SimplePlugin, SimpleTemplates, ContextDict


class ThemeForm(forms.Form):
    name = forms.CharField(
        label="Theme Name",
        max_length=100,
        initial="plain",
    )


class ThemePlugin(SimplePlugin):
    name: str = "theme"
    verbose_name: str = "Theme Selector"
    templates = SimpleTemplates(
        main="django_resume/theme/plain/content.html",
        form="django_resume/theme/plain/form.html",
    )
    admin_form_class = inline_form_class = ThemeForm

    def get_context(
        self,
        _request: HttpRequest,
        plugin_data: dict,
        resume_pk: int,
        *,
        context: ContextDict,
        edit: bool = False,
    ) -> ContextDict:
        context = super().get_context(
            _request, plugin_data, resume_pk, context=context, edit=edit
        )
        if context.get("name") is None:
            context["name"] = "plain"
        return context
