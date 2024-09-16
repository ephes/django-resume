import json
from uuid import uuid4

from django import forms
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import reverse, path
from django.utils.html import format_html

from .models import Person
from .plugins import ListPlugin


class TimelineForm(forms.Form):
    id = forms.CharField(widget=forms.HiddenInput(), required=False)
    title = forms.CharField(widget=forms.TextInput())
    description = forms.CharField(widget=forms.Textarea())
    start = forms.CharField(widget=forms.TextInput(), required=False)
    end = forms.CharField(widget=forms.TextInput(), required=False)
    delete_url = None

    def __init__(self, *args, **kwargs):
        initial = kwargs.get("initial", {})
        if "timeline_items" in initial and isinstance(initial["timeline_items"], list):
            initial["timeline_items"] = json.dumps(initial["timeline_items"])
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

    def clean_title(self):
        title = self.cleaned_data["title"]
        if title == "Senor Developer":
            print("No Senor! Validation Error!")
            raise forms.ValidationError("No Senor!")
        return title


class TimelinePlugin(ListPlugin):
    name = "employed_timeline"
    verbose_name = "Employed Timeline"
    change_form_template = "django_resume/admin/timeline_admin_change_form_htmx.html"
    item_change_form_template = "django_resume/admin/timeline_item_form.html"

    @staticmethod
    def get_admin_change_post_url(person_id):
        return reverse(
            "admin:timeline-plugin-admin-post", kwargs={"person_id": person_id}
        )

    @staticmethod
    def get_admin_add_form_link(person_id):
        return reverse(
            "admin:timeline-plugin-admin-add", kwargs={"person_id": person_id}
        )

    @staticmethod
    def get_admin_delete_link(person_id, item_id):
        return reverse(
            "admin:timeline-plugin-admin-delete",
            kwargs={"person_id": person_id, "item_id": item_id},
        )

    @staticmethod
    def get_admin_change_url(person_id):
        return reverse(
            "admin:timeline-plugin-admin-change", kwargs={"person_id": person_id}
        )

    def get_admin_link(self, person_id):
        print("get admin link called for person: ", person_id)
        url = self.get_admin_change_url(person_id)
        return format_html('<a href="{}">{}</a>', url, f"Edit {self.verbose_name}")

    def add_admin_form_view(self, request, person_id):
        print("add admin form view called!")
        person = get_object_or_404(Person, pk=person_id)
        form_class = self.get_admin_form()
        form = form_class(initial={})
        form.post_url = self.get_admin_change_post_url(person.pk)
        context = {"form": form}
        return render(request, self.item_change_form_template, context)

    def delete_admin_view(self, _request, person_id, item_id):
        print("delete admin view called for item: ", item_id)
        person = get_object_or_404(Person, pk=person_id)
        person = self.delete(person, {"id": item_id})
        person.save()
        return HttpResponse(status=200)

    def get_admin_urls(self, admin_view):
        urls = [
            path(
                f"<int:person_id>/plugin/{self.name}/change/",
                admin_view(self.admin_change_view),
                name="timeline-plugin-admin-change",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/post/",
                admin_view(self.admin_post_view),
                name="timeline-plugin-admin-post",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/add/",
                admin_view(self.add_admin_form_view),
                name="timeline-plugin-admin-add",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/delete/<str:item_id>/",
                admin_view(self.delete_admin_view),
                name="timeline-plugin-admin-delete",
            ),
        ]
        print("get admin urls: ", urls)
        return urls

    def admin_change_view(self, request, person_id):
        person = get_object_or_404(Person, id=person_id)
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
            form = form_class(initial=form_data)
            form.post_url = post_url
            form.delete_url = self.get_admin_delete_link(person.id, form_data["id"])
            timeline_forms.append(form)
        # if len(timeline_forms) == 0:
        #     form = form_class(initial={})
        #     form.post_url = post_url
        #     timeline_forms.append(form)
        context["add_form_link"] = self.get_admin_add_form_link(person.id)
        context["forms"] = timeline_forms
        return render(request, self.change_form_template, context)

    def admin_post_view(self, request, person_id):
        person = get_object_or_404(Person, id=person_id)
        form_class = self.get_admin_form()
        form = form_class(request.POST)
        form.post_url = self.get_admin_change_post_url(person.pk)
        context = {"form": form}
        if form.is_valid():
            if form.cleaned_data.get("id", False):
                person = self.update(person, form.cleaned_data)
            else:
                person = self.create(person, form.cleaned_data)
            person.save()
            form.delete_url = self.get_admin_delete_link(
                person.id, form.cleaned_data["id"]
            )

        print("after is valid check!")
        return render(request, self.item_change_form_template, context)

    def get_admin_form(self):
        return TimelineForm
