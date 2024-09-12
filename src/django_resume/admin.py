from django.contrib import admin, messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path, reverse

from .models import Person
from .plugins import plugin_registry


class PersonAdmin(admin.ModelAdmin):
    # fields = ("name", "slug", "plugin_data")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:person_id>/plugin/<str:plugin_name>/",
                self.admin_site.admin_view(self.plugin_view),
                name="person-plugin",
            ),
            path(
                "<int:person_id>/plugin/<str:plugin_name>/post/",
                self.admin_site.admin_view(self.plugin_view_post),
                name="person-plugin-post",
            ),
        ]
        return custom_urls + urls

    def add_plugin_method(self, plugin):
        """
        Add a method to the admin class that will return a link to the plugin admin view.
        This is used to have the plugins show up as readonly fields in the person change view.
        """

        def plugin_method(_self, obj):
            admin_link = plugin.get_admin_link(obj.id)
            print("plugin_method called, returning: ", admin_link)
            return admin_link

        plugin_method.__name__ = plugin.name
        setattr(self.__class__, plugin.name, plugin_method)

    def get_readonly_fields(self, request, obj=None):
        """Add a readonly field for each plugin."""
        print("get_readonly_fields called!")
        readonly_fields = list(super().get_readonly_fields(request, obj))
        # Filter out all plugins already in readonly_fields - somehow this method is getting called multiple times
        readonly_fields_lookup = set(readonly_fields)
        new_plugins = [
            p
            for p in plugin_registry.get_all_plugins()
            if p.name not in readonly_fields_lookup
        ]
        for plugin in new_plugins:
            readonly_fields.append(plugin.name)
            self.add_plugin_method(plugin)
        # print("readonly_fields: ", readonly_fields)
        # print("added method? ", self.employed_timeline, self.employed_timeline(obj))
        return readonly_fields

    def plugin_view_post(self, request, person_id, plugin_name):
        person = get_object_or_404(Person, id=person_id)
        plugin = plugin_registry.get_plugin(plugin_name)

        form_class = plugin.get_admin_form()
        if request.method == "POST":
            form = form_class(request.POST)
            if form.is_valid():
                existing_data = plugin.get_data(person)
                existing_data.append(form.cleaned_data)
                plugin.set_data(person, existing_data)
                messages.success(
                    request, f"{plugin.verbose_name} data updated successfully."
                )
                return redirect("admin:resume_person_change", person_id)
        return redirect("admin:resume_person_change", person_id)

    def plugin_view(self, request, person_id, plugin_name):
        person = get_object_or_404(Person, id=person_id)
        plugin = plugin_registry.get_plugin(plugin_name)

        if not plugin:
            return redirect("admin:resume_person_change", person_id)

        form_class = plugin.get_admin_form()
        forms = []
        if request.method == "POST":
            form = form_class(request.POST)
            if form.is_valid():
                plugin.set_data(person, form.cleaned_data)
                messages.success(
                    request, f"{plugin.verbose_name} data updated successfully."
                )
                return redirect("admin:resume_person_change", person_id)
        else:
            # initial_data = {'timeline_items': plugin.get_data(person)}
            initial_data = plugin.get_data(person)
            print("initial_data: ", initial_data)
            print("form_class: ", form_class)
            post_url = reverse(
                "admin:person-plugin-post",
                kwargs={"person_id": person_id, "plugin_name": plugin_name},
            )
            for form_data in initial_data:
                form = form_class(initial=form_data)
                form.post_url = post_url
                forms.append(form)
            if len(forms) == 0:
                form = form_class(initial={})
                form.post_url = post_url
                forms.append(form)
            # form = form_class(initial=initial_data)

        print("post url: ", forms[0].post_url)
        context = {
            "title": f"{plugin.verbose_name} for {person.name}",
            "forms": forms,
            "person": person,
            "plugin": plugin,
            "opts": self.model._meta,
            # context for admin/change_form.html template
            "add": False,
            "change": True,
            "is_popup": False,
            "save_as": False,
            "has_add_permission": False,
            "has_view_permission": True,
            "has_change_permission": True,
            "has_delete_permission": False,
            "has_editable_inline_admin_formsets": False,
        }
        return render(request, plugin.change_form_template, context)


admin.site.register(Person, PersonAdmin)
