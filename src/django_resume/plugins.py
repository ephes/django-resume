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


class ListItemFormMixin(forms.Form):
    id = forms.CharField(widget=forms.HiddenInput(), required=False)

    def __init__(self, *args, **kwargs):
        self.person = kwargs.pop("person")
        self.existing_items = kwargs.pop("existing_items", [])
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


class ListPlugin(BasePlugin):
    """
    A plugin that displays a list of items. Simple crud operations are supported.
    Each item in the list is a json serializable dict and should have an "id" field.

    Additional flat data can be stored in the plugin_data['flat'] field.
    """

    name = "list_plugin"
    admin_change_form_template = (
        "django_resume/admin/list_plugin_admin_change_form_htmx.html"
    )
    admin_item_change_form_template = (
        "django_resume/admin/list_plugin_admin_item_form.html"
    )
    admin_flat_form_template = "django_resume/admin/list_plugin_admin_flat_form.html"

    # admin stuff

    def get_admin_item_form(self):
        """Should return a form class that is used to create and update items."""

        class ListItemForm(ListItemFormMixin, forms.Form):
            """Just a dummy form."""

            pass

        return ListItemForm

    def get_admin_flat_form(self):
        """Should return a form class that is used to create and update flat data."""

        class ListFlatForm(forms.Form):
            """Just a dummy form."""

            pass

        return ListFlatForm

    # admin urls

    def get_admin_change_url(self, person_id):
        """
        Main admin view for this plugin. This view should display a list of item
        forms with update buttons for existing items and a button to get a form to
        add a new item. And a form to change the data for the plugin that is stored
        in a flat format.
        """
        return reverse(
            f"admin:{self.name}-admin-change", kwargs={"person_id": person_id}
        )

    def get_admin_item_add_form_url(self, person_id):
        """
        Returns the url of a view that returns a form to add a new item. The person_id
        is needed to be able to add the right post url to the form.
        """
        return reverse(
            f"admin:{self.name}-admin-item-add", kwargs={"person_id": person_id}
        )

    def get_admin_change_item_post_url(self, person_id):
        """Used for create and update item."""
        return reverse(
            f"admin:{self.name}-admin-item-post", kwargs={"person_id": person_id}
        )

    def get_admin_delete_item_url(self, person_id, item_id):
        """Used for delete item."""
        return reverse(
            f"admin:{self.name}-admin-item-delete",
            kwargs={"person_id": person_id, "item_id": item_id},
        )

    def get_admin_change_flat_post_url(self, person_id):
        """Used for create and update flat data."""
        return reverse(
            f"admin:{self.name}-admin-flat-post", kwargs={"person_id": person_id}
        )

    def get_admin_link(self, person_id):
        """
        Return a link to the main admin view for this plugin. This is used to have the
        plugins show up as readonly fields in the person change view and to have a link
        to be able to edit the plugin data.
        """
        url = self.get_admin_change_url(person_id)
        return format_html('<a href="{}">{}</a>', url, f"Edit {self.verbose_name}")

    def get_admin_urls(self, admin_view):
        """
        This method should return a list of urls that are used to manage the
        plugin data in the admin interface.
        """
        urls = [
            path(
                f"<int:person_id>/plugin/{self.name}/change/",
                admin_view(self.get_admin_change_view),
                name=f"{self.name}-admin-change",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/item/post/",
                admin_view(self.post_admin_item_view),
                name=f"{self.name}-admin-item-post",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/add/",
                admin_view(self.get_admin_add_item_form_view),
                name=f"{self.name}-admin-item-add",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/delete/<str:item_id>/",
                admin_view(self.delete_admin_item_view),
                name=f"{self.name}-admin-item-delete",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/flat/post/",
                admin_view(self.post_admin_flat_view),
                name=f"{self.name}-admin-flat-post",
            ),
        ]
        return urls

    # admin views

    def get_admin_add_item_form_view(self, request, person_id):
        """Return a single empty form to add a new item."""
        person = get_object_or_404(Person, pk=person_id)
        form_class = self.get_admin_item_form()
        existing_items = self.get_data(person).get("items", [])
        form = form_class(initial={}, person=person, existing_items=existing_items)
        form.post_url = self.get_admin_change_item_post_url(person.pk)
        context = {"form": form}
        return render(request, self.admin_item_change_form_template, context)

    def delete_admin_item_view(self, _request, person_id, item_id):
        """Delete an item from the items list of this plugin."""
        person = get_object_or_404(Person, pk=person_id)
        person = self.delete(person, {"id": item_id})
        person.save()
        return HttpResponse(status=200)

    def get_admin_change_view(self, request, person_id):
        """Return the main admin view for this plugin."""
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
        plugin_data = self.get_data(person)
        # flat form
        flat_form_class = self.get_admin_flat_form()
        flat_form = flat_form_class(initial=plugin_data.get("flat", {}))
        flat_form.post_url = self.get_admin_change_flat_post_url(person.pk)
        context["flat_form"] = flat_form
        # item forms
        item_form_class = self.get_admin_item_form()
        initial_items_data = plugin_data.get("items", [])
        post_url = self.get_admin_change_item_post_url(person.id)
        timeline_forms = []
        for initial_item_data in initial_items_data:
            form = item_form_class(
                initial=initial_item_data,
                person=person,
                existing_items=initial_items_data,
            )
            form.post_url = post_url
            form.delete_url = self.get_admin_delete_item_url(
                person.id, initial_item_data["id"]
            )
            timeline_forms.append(form)
        context["add_item_form_url"] = self.get_admin_item_add_form_url(person.id)
        context["item_forms"] = timeline_forms
        return render(request, self.admin_change_form_template, context)

    def post_admin_item_view(self, request, person_id):
        """Handle post requests to create or update a single item."""
        person = get_object_or_404(Person, id=person_id)
        form_class = self.get_admin_item_form()
        existing_items = self.get_data(person).get("items", [])
        form = form_class(request.POST, person=person, existing_items=existing_items)
        form.post_url = self.get_admin_change_item_post_url(person.pk)
        context = {"form": form}
        if form.is_valid():
            if form.cleaned_data.get("id", False):
                item_id = form.cleaned_data["id"]
                person = self.update(person, form.cleaned_data)
            else:
                data = form.cleaned_data
                item_id = str(uuid4())
                data["id"] = item_id
                person = self.create(person, data)
                # weird hack to make the form look like it is for an existing item
                # if there's a better way to do this, please let me know FIXME
                form.data = form.data.copy()
                form.data["id"] = item_id
            person.save()
            form.delete_url = self.get_admin_delete_item_url(person.id, item_id)
        return render(request, self.admin_item_change_form_template, context)

    def post_admin_flat_view(self, request, person_id):
        """Handle post requests to update flat data."""
        print("update flat data! ", request.POST)
        person = get_object_or_404(Person, id=person_id)
        form_class = self.get_admin_flat_form()
        form = form_class(request.POST)
        form.post_url = self.get_admin_change_flat_post_url(person.pk)
        context = {"form": form}
        if form.is_valid():
            person = self.update_flat(person, form.cleaned_data)
            person.save()
        return render(request, self.admin_flat_form_template, context)

    # data handling for flat form

    def update_flat(self, person, data):
        """Update the flat data of this plugin."""
        plugin_data = self.get_data(person)
        plugin_data["flat"] = data
        return self.set_data(person, plugin_data)

    # crud data handling for items

    def create(self, person, data):
        """Create an item in the items list of this plugin."""
        plugin_data = self.get_data(person)
        plugin_data.setdefault("items", []).append(data)
        person = self.set_data(person, plugin_data)
        return person

    def update(self, person, data):
        """Update an item in the items list of this plugin."""
        plugin_data = self.get_data(person)
        items = plugin_data.get("items", [])
        for item in items:
            if item["id"] == data["id"]:
                item.update(data)
                break
        plugin_data["items"] = items
        return self.set_data(person, plugin_data)

    def delete(self, person, data):
        """Delete an item from the items list of this plugin."""
        plugin_data = self.get_data(person)
        items = plugin_data.get("items", [])
        for i, item in enumerate(items):
            if item["id"] == data["id"]:
                items.pop(i)
                break
        plugin_data["items"] = items
        return self.set_data(person, plugin_data)


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
