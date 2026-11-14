from typing import Any

from django import forms
from django.contrib import admin
from django.db import OperationalError, router
from django.core.exceptions import ValidationError
from django.http import HttpRequest

from .models import Resume
from .plugins import plugin_registry
from .plugins.base import Plugin, URLPatterns, set_edit_revision


CONFLICT_MESSAGE = "This resume changed since you opened it. Reload the editor and reapply your changes."


def document_state(resume: Resume) -> dict[str, Any]:
    return {
        field.attname: getattr(resume, field.attname)
        for field in Resume._meta.concrete_fields
        if not field.primary_key
    }


class DocumentConflict(Exception):
    pass


class ResumeAdminForm(forms.ModelForm):
    edit_revision = forms.CharField(widget=forms.HiddenInput, required=False)

    class Meta:
        model = Resume
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_document = document_state(self.instance)
        if not self.instance._state.adding:
            set_edit_revision(
                self, self.instance, "root-admin", "document", self.original_document
            )


class ResumeAdmin(admin.ModelAdmin):
    form = ResumeAdminForm

    def get_object(self, request, object_id, from_field=None):
        # ModelAdmin already wraps POST in the routed writer transaction.
        if request.method == "POST":
            queryset = (
                self.get_queryset(request)
                .using(router.db_for_write(Resume))
                .select_for_update()
            )
            field = (
                Resume._meta.pk
                if from_field is None
                else Resume._meta.get_field(from_field)
            )
            try:
                return queryset.get(**{field.name: field.to_python(object_id)})
            except (Resume.DoesNotExist, ValidationError, ValueError):
                return None
        return super().get_object(request, object_id, from_field)

    def save_model(self, request, obj, form, change):
        if not change:
            return super().save_model(request, obj, form, change)
        # Match Resume.save()'s normalization for cleared optional JSON fields.
        if obj.plugin_data is None:
            obj.plugin_data = {}
        if obj.integration_data is None:
            obj.integration_data = {}
        # Compare the entire loaded document as well as checking the signed GET
        # revision. This also fences writes on backends without row locks.
        changed = (
            Resume.objects.using(obj._state.db)
            .filter(pk=obj.pk, **form.original_document)
            .update(**document_state(obj))
        )
        if changed != 1:
            raise DocumentConflict

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        try:
            return super().changeform_view(request, object_id, form_url, extra_context)
        except (DocumentConflict, OperationalError) as exc:
            # SQLite can report contention instead of a zero-row CAS. Other DB
            # errors must still surface rather than masquerading as conflicts.
            code = getattr(exc.__cause__, "sqlite_errorcode", 0)
            if isinstance(exc, OperationalError) and code & 255 not in (5, 6):
                raise
        # The failed writer transaction has rolled back, including admin logs.
        # Rebind the POST against the current row and force an ordinary form error.
        request._resume_document_conflict = True
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_form(self, request, obj=None, **kwargs):
        form_class = super().get_form(request, obj, **kwargs)
        if not getattr(request, "_resume_document_conflict", False):
            return form_class

        class ConflictForm(form_class):
            def clean(self):
                super().clean()
                raise forms.ValidationError(CONFLICT_MESSAGE)

        return ConflictForm

    plugin_field_prefix = "plugin_link__"
    # fields = ("name", "slug", "plugin_data")

    def get_urls(self) -> URLPatterns:
        urls = super().get_urls()
        custom_urls = []
        for plugin in plugin_registry.get_all_plugins():
            custom_urls.extend(plugin.get_admin_urls(self.admin_site.admin_view))
        return custom_urls + urls

    def get_plugin_readonly_field_name(self, plugin_name: str) -> str:
        return f"{self.plugin_field_prefix}{plugin_name}"

    def add_plugin_method(self, plugin: Plugin) -> None:
        """
        Add a method to the admin class that will return a link to the plugin admin view.
        This is used to have the plugins show up as readonly fields in the resume change view.
        """

        def plugin_method(_self, obj: Resume) -> str:
            admin_link = plugin.get_admin_link(obj.id)
            return admin_link

        field_name = self.get_plugin_readonly_field_name(plugin.name)
        plugin_method.__name__ = field_name
        setattr(plugin_method, "short_description", plugin.verbose_name)
        setattr(self.__class__, field_name, plugin_method)

    def get_readonly_fields(self, request: HttpRequest, obj=None) -> list[str]:
        """Add a readonly field for each plugin."""
        readonly_fields = list(super().get_readonly_fields(request, obj))
        # Filter out all plugins already in readonly_fields - somehow this method is getting called multiple times
        readonly_fields_lookup = set(readonly_fields)
        new_plugins = [
            p
            for p in plugin_registry.get_all_plugins()
            if self.get_plugin_readonly_field_name(p.name) not in readonly_fields_lookup
        ]
        for plugin in new_plugins:
            readonly_fields.append(self.get_plugin_readonly_field_name(plugin.name))
            self.add_plugin_method(plugin)
        return readonly_fields


admin.site.register(Resume, ResumeAdmin)
