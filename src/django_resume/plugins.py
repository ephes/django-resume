from uuid import uuid4

from django import forms
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, path
from django.utils.html import format_html

from .models import Person


class BasePlugin:
    name = "base_plugin"
    verbose_name = "Base Plugin"

    def get_data(self, person):
        return person.plugin_data.get(self.name, {})

    def set_data(self, person, data):
        if not person.plugin_data:
            person.plugin_data = {}
        person.plugin_data[self.name] = data
        print("setting data: ", data, "on person: ", person)
        return person

    def get_admin_form(self):
        return None

    def get_list_display_field(self):
        def admin_link(obj):
            return self.get_admin_link(obj.id)

        admin_link.short_description = self.verbose_name
        return admin_link

    def create(self, person, data):
        return self.set_data(person, data)

    def update(self, person, data):
        return self.set_data(person, data)

    def delete(self, person, data):
        return self.set_data(person, data)


class ListFormMixin(forms.Form):
    id = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        self.person = kwargs.pop("person")
        super().__init__(*args, **kwargs)

    @property
    def is_new(self):
        """Used to determine if the form is for a new item or an existing one."""
        if self.is_bound:
            return False
        return not self.initial.get("id", False)

    @property
    def item_id(self):
        """
        Use a uuid for the item id if there is no id in the initial data. This is to
        allow the htmx delete button to work even when there are multiple new item
        forms on the page.
        """
        if self.is_bound:
            return self.cleaned_data.get("id", uuid4())
        return self.initial.get("id", uuid4())


class ListForm(ListFormMixin, forms.Form):
    data = forms.JSONField()


class ListPlugin(BasePlugin):
    """
    A plugin that displays a list of items. Simple crud operations are supported.
    Each item in the list is a json serializable dict and should have an "id" field.
    """

    name = "list_plugin"
    admin_change_form_template = (
        "django_resume/admin/list_plugin_admin_change_form_htmx.html"
    )
    admin_item_change_form_template = (
        "django_resume/admin/list_plugin_admin_item_form.html"
    )

    # admin stuff

    def get_admin_form(self):
        return ListForm

    # admin urls

    def get_admin_change_post_url(self, person_id):
        return reverse(f"admin:{self.name}-admin-post", kwargs={"person_id": person_id})

    def get_admin_delete_link(self, person_id, item_id):
        return reverse(
            f"admin:{self.name}-admin-delete",
            kwargs={"person_id": person_id, "item_id": item_id},
        )

    def get_admin_change_url(self, person_id):
        return reverse(
            f"admin:{self.name}-admin-change", kwargs={"person_id": person_id}
        )

    def get_admin_add_form_link(self, person_id):
        return reverse(f"admin:{self.name}-admin-add", kwargs={"person_id": person_id})

    def get_admin_link(self, person_id):
        print("get admin link called for person: ", person_id)
        url = self.get_admin_change_url(person_id)
        return format_html('<a href="{}">{}</a>', url, f"Edit {self.verbose_name}")

    def get_admin_urls(self, admin_view):
        urls = [
            path(
                f"<int:person_id>/plugin/{self.name}/change/",
                admin_view(self.admin_change_view),
                name=f"{self.name}-admin-change",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/post/",
                admin_view(self.admin_post_view),
                name=f"{self.name}-admin-post",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/add/",
                admin_view(self.add_admin_form_view),
                name=f"{self.name}-admin-add",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/delete/<str:item_id>/",
                admin_view(self.delete_admin_view),
                name=f"{self.name}-admin-delete",
            ),
        ]
        return urls

    # admin views

    def add_admin_form_view(self, request, person_id):
        print("add admin form view called!")
        person = get_object_or_404(Person, pk=person_id)
        form_class = self.get_admin_form()
        form = form_class(initial={}, person=person)
        form.post_url = self.get_admin_change_post_url(person.pk)
        context = {"form": form}
        return render(request, self.admin_item_change_form_template, context)

    def delete_admin_view(self, _request, person_id, item_id):
        print("delete admin view called for item: ", item_id)
        person = get_object_or_404(Person, pk=person_id)
        person = self.delete(person, {"id": item_id})
        person.save()
        return HttpResponse(status=200)

    def admin_change_view(self, request, person_id):
        person = get_object_or_404(Person, pk=person_id)
        context = {
            "title": f"{self.verbose_name} for {person.name}",
            "person": person,
            "plugin": self,
            "opts": Person._meta,
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
        form_class = self.get_admin_form()
        initial_data = self.get_data(person)
        print("initial_data: ", initial_data)
        post_url = self.get_admin_change_post_url(person.id)
        timeline_forms = []
        for form_data in initial_data:
            form = form_class(initial=form_data, person=person)
            form.post_url = post_url
            form.delete_url = self.get_admin_delete_link(person.id, form_data["id"])
            timeline_forms.append(form)
        context["add_form_link"] = self.get_admin_add_form_link(person.id)
        context["forms"] = timeline_forms
        return render(request, self.admin_change_form_template, context)

    def admin_post_view(self, request, person_id):
        person = get_object_or_404(Person, id=person_id)
        form_class = self.get_admin_form()
        form = form_class(request.POST, person=person)
        form.post_url = self.get_admin_change_post_url(person.pk)
        context = {"form": form}
        if form.is_valid():
            print("save cleaned data: ", form.cleaned_data)
            if form.cleaned_data.get("id", False):
                person = self.update(person, form.cleaned_data)
            else:
                person = self.create(person, form.cleaned_data)
            person.save()
            form.delete_url = self.get_admin_delete_link(
                person.id, form.cleaned_data["id"]
            )
        return render(request, self.admin_item_change_form_template, context)

    # crud data handling

    def get_data(self, person):
        """Returns an empty list if no data is found."""
        return person.plugin_data.get(self.name, [])

    def create(self, person, data):
        data["id"] = str(uuid4())
        items = self.get_data(person)
        items.append(data)
        print("create items: ", items)
        person = self.set_data(person, items)
        print("create for person: ", person)
        return person

    def update(self, person, data):
        items = self.get_data(person)
        for i, item in enumerate(items):
            if item["id"] == data["id"]:
                item.update(data)
                break
        return self.set_data(person, items)

    def delete(self, person, data):
        items = self.get_data(person)
        for i, item in enumerate(items):
            if item["id"] == data["id"]:
                items.pop(i)
                break
        return self.set_data(person, items)


class PluginRegistry:
    def __init__(self):
        self.plugins = {}

    def register(self, plugin_class):
        plugin = plugin_class()
        self.plugins[plugin.name] = plugin

    def get_plugin(self, name):
        return self.plugins.get(name)

    def get_all_plugins(self):
        return self.plugins.values()


plugin_registry = PluginRegistry()
