from uuid import uuid4

from typing import Protocol, runtime_checkable, Callable, TypeAlias

from django import forms
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, path, URLPattern, URLResolver
from django.utils.html import format_html

from .models import Person


URLPatterns: TypeAlias = list[URLPattern | URLResolver]


@runtime_checkable
class Plugin(Protocol):
    name: str
    verbose_name: str

    def get_admin_urls(self, admin_view: Callable) -> URLPatterns:
        """Return a list of urls that are used to manage the plugin data in the Django admin interface."""
        ...

    def get_admin_link(self, person_id: int) -> str:
        """Return a formatted html link to the main admin view for this plugin."""
        ...

    def get_inline_urls(self) -> URLPatterns:
        """Return a list of urls that are used to manage the plugin data inline."""
        ...

    def get_form_classes(self) -> dict[str, type[forms.Form]]:
        """Return a dictionary of form classes that are used to manage the plugin data."""
        ...

    def get_data(self, person: Person) -> dict:
        """Return the plugin data for a person."""
        ...


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
        Use an uuid for the item id if there is no id in the initial data. This is to
        allow the htmx delete button to work even when there are multiple new item
        forms on the page.
        """
        if self.is_bound:
            return self.cleaned_data.get("id", uuid4())
        if self.initial.get("id") is None:
            self.initial["id"] = uuid4()
        return self.initial["id"]


class ListTemplates:
    def __init__(
        self, *, main: str, flat: str, flat_form: str, item: str, item_form: str
    ):
        self.main = main
        self.flat = flat
        self.flat_form = flat_form
        self.item = item
        self.item_form = item_form


class ListData:
    """
    This class contains the logic of the list plugin concerned with the data handling.

    Simple crud operations are supported.
    """

    def __init__(self, *, plugin_name: str):
        self.plugin_name = plugin_name

    # read
    def get_data(self, person: Person):
        return person.plugin_data.get(self.plugin_name, {})

    def get_item_by_id(self, person: Person, item_id: str) -> dict | None:
        items = self.get_data(person).get("items", [])
        for item in items:
            if item["id"] == item_id:
                return item
        return None

    # write
    def set_data(self, person: Person, data: dict):
        if not person.plugin_data:
            person.plugin_data = {}
        person.plugin_data[self.plugin_name] = data
        return person

    def create(self, person: Person, data: dict):
        """Create an item in the items list of this plugin."""
        plugin_data = self.get_data(person)
        plugin_data.setdefault("items", []).append(data)
        person = self.set_data(person, plugin_data)
        return person

    def update(self, person: Person, data: dict):
        """Update an item in the items list of this plugin."""
        plugin_data = self.get_data(person)
        items = plugin_data.get("items", [])
        for item in items:
            if item["id"] == data["id"]:
                item.update(data)
                break
        plugin_data["items"] = items
        return self.set_data(person, plugin_data)

    def update_flat(self, person: Person, data: dict):
        """Update the flat data of this plugin."""
        plugin_data = self.get_data(person)
        plugin_data["flat"] = data
        return self.set_data(person, plugin_data)

    def delete(self, person: Person, data: dict):
        """Delete an item from the items list of this plugin."""
        plugin_data = self.get_data(person)
        items = plugin_data.get("items", [])
        for i, item in enumerate(items):
            if item["id"] == data["id"]:
                items.pop(i)
                break
        plugin_data["items"] = items
        return self.set_data(person, plugin_data)


class ListAdmin:
    """
    This class contains the logic of the list plugin concerned with the Django admin interface.

    Simple crud operations are supported. Each item in the list is a json serializable
    dict and should have an "id" field.

    Why have an own class for this? Because the admin interface is different from the
    inline editing on the website itself. For example: the admin interface has a change
    view where all forms are displayed at once. Which makes sense, because the admin is
    for editing.
    """

    admin_change_form_template = (
        "django_resume/admin/list_plugin_admin_change_form_htmx.html"
    )
    admin_item_change_form_template = (
        "django_resume/admin/list_plugin_admin_item_form.html"
    )
    admin_flat_form_template = "django_resume/admin/list_plugin_admin_flat_form.html"

    def __init__(
        self,
        *,
        plugin_name: str,
        plugin_verbose_name,
        form_classes: dict,
        data: ListData,
    ):
        self.plugin_name = plugin_name
        self.plugin_verbose_name = plugin_verbose_name
        self.form_classes = form_classes
        self.data = data

    def get_change_url(self, person_id):
        """
        Main admin view for this plugin. This view should display a list of item
        forms with update buttons for existing items and a button to get a form to
        add a new item. And a form to change the data for the plugin that is stored
        in a flat format.
        """
        return reverse(
            f"admin:{self.plugin_name}-admin-change", kwargs={"person_id": person_id}
        )

    def get_admin_link(self, person_id: int) -> str:
        """
        Return a link to the main admin view for this plugin. This is used to have the
        plugins show up as readonly fields in the person change view and to have a link
        to be able to edit the plugin data.
        """
        url = self.get_change_url(person_id)
        return format_html(
            '<a href="{}">{}</a>', url, f"Edit {self.plugin_verbose_name}"
        )

    def get_change_flat_post_url(self, person_id):
        """Used for create and update flat data."""
        return reverse(
            f"admin:{self.plugin_name}-admin-flat-post", kwargs={"person_id": person_id}
        )

    def get_change_item_post_url(self, person_id):
        """Used for create and update item."""
        return reverse(
            f"admin:{self.plugin_name}-admin-item-post", kwargs={"person_id": person_id}
        )

    def get_delete_item_url(self, person_id, item_id):
        """Used for delete item."""
        return reverse(
            f"admin:{self.plugin_name}-admin-item-delete",
            kwargs={"person_id": person_id, "item_id": item_id},
        )

    def get_item_add_form_url(self, person_id):
        """
        Returns the url of a view that returns a form to add a new item. The person_id
        is needed to be able to add the right post url to the form.
        """
        return reverse(
            f"admin:{self.plugin_name}-admin-item-add", kwargs={"person_id": person_id}
        )

    # crud views

    def get_add_item_form_view(self, request, person_id):
        """Return a single empty form to add a new item."""
        person = get_object_or_404(Person, pk=person_id)
        form_class = self.form_classes["item"]
        existing_items = self.data.get_data(person).get("items", [])
        form = form_class(initial={}, person=person, existing_items=existing_items)
        form.post_url = self.get_change_item_post_url(person.pk)
        context = {"form": form}
        return render(request, self.admin_item_change_form_template, context)

    def get_change_view(self, request, person_id):
        """Return the main admin view for this plugin."""
        person = get_object_or_404(Person, pk=person_id)
        context = {
            "title": f"{self.plugin_verbose_name} for {person.name}",
            "person": person,
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
        plugin_data = self.data.get_data(person)
        form_classes = self.form_classes
        # flat form
        flat_form_class = form_classes["flat"]
        flat_form = flat_form_class(initial=plugin_data.get("flat", {}))
        flat_form.post_url = self.get_change_flat_post_url(person.pk)
        context["flat_form"] = flat_form
        # item forms
        item_form_class = form_classes["item"]
        initial_items_data = plugin_data.get("items", [])
        post_url = self.get_change_item_post_url(person.id)
        timeline_forms = []
        for initial_item_data in initial_items_data:
            form = item_form_class(
                initial=initial_item_data,
                person=person,
                existing_items=initial_items_data,
            )
            form.post_url = post_url
            form.delete_url = self.get_delete_item_url(
                person.id, initial_item_data["id"]
            )
            timeline_forms.append(form)
        context["add_item_form_url"] = self.get_item_add_form_url(person.id)
        context["item_forms"] = timeline_forms
        return render(request, self.admin_change_form_template, context)

    def post_item_view(self, request, person_id):
        """Handle post requests to create or update a single item."""
        person = get_object_or_404(Person, id=person_id)
        form_class = self.form_classes["item"]
        existing_items = self.data.get_data(person).get("items", [])
        form = form_class(request.POST, person=person, existing_items=existing_items)
        form.post_url = self.get_change_item_post_url(person.pk)
        context = {"form": form}
        if form.is_valid():
            if form.cleaned_data.get("id", False):
                item_id = form.cleaned_data["id"]
                person = self.data.update(person, form.cleaned_data)
            else:
                data = form.cleaned_data
                item_id = str(uuid4())
                data["id"] = item_id
                person = self.data.create(person, data)
                # weird hack to make the form look like it is for an existing item
                # if there's a better way to do this, please let me know FIXME
                form.data = form.data.copy()
                form.data["id"] = item_id
            person.save()
            form.delete_url = self.get_delete_item_url(person.id, item_id)
        return render(request, self.admin_item_change_form_template, context)

    def post_flat_view(self, request, person_id):
        """Handle post requests to update flat data."""
        person = get_object_or_404(Person, id=person_id)
        form_class = self.form_classes["flat"]
        form = form_class(request.POST)
        form.post_url = self.get_change_flat_post_url(person.pk)
        context = {"form": form}
        if form.is_valid():
            person = self.data.update_flat(person, form.cleaned_data)
            person.save()
        return render(request, self.admin_flat_form_template, context)

    def delete_item_view(self, _request, person_id, item_id):
        """Delete an item from the items list of this plugin."""
        person = get_object_or_404(Person, pk=person_id)
        person = self.data.delete(person, {"id": item_id})
        person.save()
        return HttpResponse(status=200)

    # urlpatterns

    def get_urls(self, admin_view: Callable) -> URLPatterns:
        """
        This method should return a list of urls that are used to manage the
        plugin data in the admin interface.
        """
        plugin_name = self.plugin_name
        urls = [
            path(
                f"<int:person_id>/plugin/{plugin_name}/change/",
                admin_view(self.get_change_view),
                name=f"{plugin_name}-admin-change",
            ),
            path(
                f"<int:person_id>/plugin/{plugin_name}/item/post/",
                admin_view(self.post_item_view),
                name=f"{plugin_name}-admin-item-post",
            ),
            path(
                f"<int:person_id>/plugin/{plugin_name}/add/",
                admin_view(self.get_add_item_form_view),
                name=f"{plugin_name}-admin-item-add",
            ),
            path(
                f"<int:person_id>/plugin/{plugin_name}/delete/<str:item_id>/",
                admin_view(self.delete_item_view),
                name=f"{plugin_name}-admin-item-delete",
            ),
            path(
                f"<int:person_id>/plugin/{plugin_name}/flat/post/",
                admin_view(self.post_flat_view),
                name=f"{plugin_name}-admin-flat-post",
            ),
        ]
        return urls


class ListInline:
    """
    This class contains the logic of the list plugin concerned with the inline editing
    of the plugin data on the website itself.
    """

    def __init__(
        self,
        *,
        plugin_name: str,
        plugin_verbose_name: str,
        form_classes: dict,
        data: ListData,
        templates: ListTemplates,
    ):
        self.plugin_name = plugin_name
        self.plugin_verbose_name = plugin_verbose_name
        self.form_classes = form_classes
        self.data = data
        self.templates = templates

    # urls

    def get_edit_flat_post_url(self, person_id):
        return reverse(
            f"django_resume:{self.plugin_name}-edit-flat-post",
            kwargs={"person_id": person_id},
        )

    def get_edit_flat_url(self, person_id):
        return reverse(
            f"django_resume:{self.plugin_name}-edit-flat",
            kwargs={"person_id": person_id},
        )

    def get_edit_item_url(self, person_id, item_id=None):
        if item_id is None:
            return reverse(
                f"django_resume:{self.plugin_name}-add-item",
                kwargs={"person_id": person_id},
            )
        else:
            return reverse(
                f"django_resume:{self.plugin_name}-edit-item",
                kwargs={"person_id": person_id, "item_id": item_id},
            )

    def get_post_item_url(self, person_id):
        return reverse(
            f"django_resume:{self.plugin_name}-item-post",
            kwargs={"person_id": person_id},
        )

    def get_delete_item_url(self, person_id, item_id):
        return reverse(
            f"django_resume:{self.plugin_name}-delete-item",
            kwargs={"person_id": person_id, "item_id": item_id},
        )

    # crud views

    def get_edit_flat_view(self, request, person_id):
        person = get_object_or_404(Person, id=person_id)
        plugin_data = self.data.get_data(person)
        flat_form_class = self.form_classes["flat"]
        flat_form = flat_form_class(initial=plugin_data.get("flat", {}))
        flat_form.post_url = self.get_edit_flat_post_url(person.pk)
        context = {
            "form": flat_form,
            "timeline": {"edit_flat_post_url": self.get_edit_flat_post_url(person.pk)},
        }
        return render(request, self.templates.flat_form, context=context)

    def post_edit_flat_view(self, request, person_id):
        print("in post edit flat view!")
        person = get_object_or_404(Person, id=person_id)
        flat_form_class = self.form_classes["flat"]
        plugin_data = self.data.get_data(person)
        flat_form = flat_form_class(request.POST, initial=plugin_data.get("flat", {}))
        context = {"timeline": {}}
        if flat_form.is_valid():
            person = self.data.update_flat(person, flat_form.cleaned_data)
            person.save()
            person.refresh_from_db()
            plugin_data = self.data.get_data(person)
            context["timeline"]["title"] = plugin_data.get("flat", {}).get(
                "title", self.plugin_verbose_name
            )
            context["timeline"]["edit_flat_url"] = self.get_edit_flat_url(person.pk)
            context["show_edit_button"] = True
            return render(request, self.templates.flat, context=context)
        else:
            context["form"] = flat_form
            context["timeline"]["edit_flat_post_url"] = self.get_edit_flat_post_url(
                person.pk
            )
            response = render(request, self.templates.flat_form, context=context)
            return response

    def get_item_view(self, request, person_id, item_id=None):
        person = get_object_or_404(Person, id=person_id)
        plugin_data = self.data.get_data(person)
        existing_items = plugin_data.get("items", [])
        # get the item data if we are editing an existing item
        initial = {
            "company_name": "company_name",
            "company_url": "https://example.com",
            "role": "role",
            "start": "start",
            "end": "end",
            "description": "description",
            "badges": "badges",
        }
        if item_id is not None:
            for item in existing_items:
                if item["id"] == item_id:
                    initial = item
        form_class = self.form_classes["item"]
        form = form_class(initial=initial, person=person, existing_items=existing_items)
        form.post_url = self.get_post_item_url(person.pk)
        context = {"form": form}
        return render(request, self.templates.item_form, context=context)

    def post_item_view(self, request, person_id):
        print("in post item view!")
        person = get_object_or_404(Person, id=person_id)
        form_class = self.form_classes["item"]
        existing_items = self.data.get_data(person).get("items", [])
        form = form_class(request.POST, person=person, existing_items=existing_items)
        form.post_url = self.get_post_item_url(person.pk)
        context = {"form": form}
        if form.is_valid():
            # try to find out whether we are updating an existing item or creating a new one
            existing = True
            item_id = form.cleaned_data.get("id", None)
            if item_id is not None:
                item = self.data.get_item_by_id(person, item_id)
                if item is None:
                    existing = False
            else:
                # no item_id -> new item
                existing = False
            if existing:
                # update existing item
                item_id = form.cleaned_data["id"]
                person = self.data.update(person, form.cleaned_data)
            else:
                # create new item
                data = form.cleaned_data
                item_id = str(uuid4())
                data["id"] = item_id
                person = self.data.create(person, data)
                # weird hack to make the form look like it is for an existing item
                # if there's a better way to do this, please let me know FIXME
                form.data = form.data.copy()
                form.data["id"] = item_id
            person.save()
            item = self.data.get_item_by_id(person, item_id)
            form.delete_url = self.get_delete_item_url(person.id, item_id)
            # populate entry because it's used in the standard item template,
            # and we are no longer rendering a form when the form was valid
            context["entry"] = {
                "id": item_id,
                "company_url": item["company_url"],
                "company_name": item["company_name"],
                "role": item["role"],
                "start": item["start"],
                "end": item["end"],
                "description": item["description"],
                "badges": item["badges"],
                "edit_url": self.get_edit_item_url(person.id, item_id),
            }
            context["show_edit_button"] = True
            return render(request, self.templates.item, context)
        else:
            # form is invalid
            return render(request, self.templates.item_form, context)

    def delete_item_view(self, _request, person_id, item_id):
        """Delete an item from the items list of this plugin."""
        person = get_object_or_404(Person, pk=person_id)
        person = self.data.delete(person, {"id": item_id})
        person.save()
        return HttpResponse(status=200)

    # urlpatterns
    def get_urls(self):
        plugin_name = self.plugin_name
        urls = [
            # flat
            path(
                f"<int:person_id>/plugin/{plugin_name}/edit/flat/",
                self.get_edit_flat_view,
                name=f"{plugin_name}-edit-flat",
            ),
            path(
                f"<int:person_id>/plugin/{plugin_name}/edit/flat/post/",
                self.post_edit_flat_view,
                name=f"{plugin_name}-edit-flat-post",
            ),
            # item
            path(
                f"<int:person_id>/plugin/{plugin_name}/edit/item/<str:item_id>",
                self.get_item_view,
                name=f"{plugin_name}-edit-item",
            ),
            path(
                f"<int:person_id>/plugin/{plugin_name}/edit/item/",
                self.get_item_view,
                name=f"{plugin_name}-add-item",
            ),
            path(
                f"<int:person_id>/plugin/{plugin_name}/edit/item/post/",
                self.post_item_view,
                name=f"{plugin_name}-item-post",
            ),
            path(
                f"<int:person_id>/plugin/{plugin_name}/delete/<str:item_id>/",
                self.delete_item_view,
                name=f"{plugin_name}-delete-item",
            ),
        ]
        return urls


class ListPlugin:
    """
    A plugin that displays a list of items. Simple crud operations are supported.
    Each item in the list is a json serializable dict and should have an "id" field.

    Additional flat data can be stored in the plugin_data['flat'] field.
    """

    name = "list_plugin"
    verbose_name = "List Plugin"
    templates: ListTemplates = ListTemplates(
        main="", flat="", flat_form="", item="", item_form=""
    )  # overwrite this

    def __init__(self):
        super().__init__()
        self.data = data = ListData(plugin_name=self.name)
        form_classes = self.get_form_classes()
        self.admin = ListAdmin(
            plugin_name=self.name,
            plugin_verbose_name=self.verbose_name,
            form_classes=form_classes,
            data=data,
        )
        self.inline = ListInline(
            plugin_name=self.name,
            plugin_verbose_name=self.verbose_name,
            form_classes=form_classes,
            data=data,
            templates=self.templates,
        )

    # main interface see Plugin class
    def get_admin_urls(self, admin_view: Callable) -> URLPatterns:
        return self.admin.get_urls(admin_view)

    def get_admin_link(self, person_id: int) -> str:
        return self.admin.get_admin_link(person_id)

    def get_inline_urls(self) -> URLPatterns:
        return self.inline.get_urls()

    def get_form_classes(self) -> dict[str, type[forms.Form]]:
        """Please implement this method."""
        return {}

    def get_data(self, person: Person) -> dict:
        return self.data.get_data(person)


class PluginRegistry:
    def __init__(self):
        self.plugins = {}

    def register(self, plugin_class):
        plugin = plugin_class()
        self.plugins[plugin.name] = plugin
        from .urls import urlpatterns

        urlpatterns.extend(plugin.get_inline_urls())

    def get_plugin(self, name):
        return self.plugins.get(name)

    def get_all_plugins(self):
        return self.plugins.values()


plugin_registry = PluginRegistry()
