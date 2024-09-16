import random
import string
from datetime import datetime
from uuid import uuid4

from django import forms
from django.http import HttpResponse
from django.urls import path, reverse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import Person
from .plugins import ListPlugin


def generate_random_string(length=20):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


class TokenForm(forms.Form):
    token = forms.CharField(max_length=255, required=True, label="Token")
    receiver = forms.CharField(max_length=255)
    created = forms.DateTimeField(widget=forms.HiddenInput(), required=False)
    cv_link = forms.CharField(
        required=False, label="CV Link", widget=forms.HiddenInput()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.initial.get("token"):
            self.fields["token"].initial = generate_random_string()
        self.token = self.initial.get("token") or self.fields["token"].initial

        if "created" in self.initial and isinstance(self.initial["created"], str):
            self.initial["created"] = datetime.fromisoformat(self.initial["created"])
        else:
            # Set the 'created' field to the current time if it's not already set
            self.fields["created"].initial = timezone.now()

    def generate_cv_link(self, person):
        base_url = reverse("django_resume:cv", kwargs={"slug": person.slug})
        link = f"{base_url}?token={self.token}"
        self.fields["cv_link"].initial = mark_safe(
            f'<a href="{link}" target="_blank">{link}</a>'
        )

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

    def clean_token(self):
        token = self.cleaned_data["token"]
        if not token:
            raise forms.ValidationError("Token required.")
        # try:
        #     return CVToken.objects.get(token=token)
        # except CVToken.DoesNotExist:
        #     raise forms.ValidationError("Invalid token.")

    def clean_created(self):
        created = self.cleaned_data["created"]
        return created.isoformat()


class TokenPlugin(ListPlugin):
    """
    Generate tokens for a person.

    If you want to restrict access to a person's resume, you can generate a token.
    The token can be shared with the person and they can access their resume using the token.
    """

    name = "token"
    verbose_name = "CV Token"
    change_form_template = "django_resume/admin/timeline_admin_change_form_htmx.html"
    item_change_form_template = "django_resume/admin/timeline_item_form.html"

    @staticmethod
    def get_admin_change_post_url(person_id):
        return reverse("admin:token-plugin-admin-post", kwargs={"person_id": person_id})

    @staticmethod
    def get_admin_delete_link(person_id, item_id):
        return reverse(
            "admin:token-plugin-admin-delete",
            kwargs={"person_id": person_id, "item_id": item_id},
        )

    @staticmethod
    def get_admin_change_url(person_id):
        return reverse(
            "admin:token-plugin-admin-change", kwargs={"person_id": person_id}
        )

    @staticmethod
    def get_admin_add_form_link(person_id):
        return reverse("admin:token-plugin-admin-add", kwargs={"person_id": person_id})

    def get_admin_form(self):
        return TokenForm

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
                name="token-plugin-admin-change",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/post/",
                admin_view(self.admin_post_view),
                name="token-plugin-admin-post",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/add/",
                admin_view(self.add_admin_form_view),
                name="token-plugin-admin-add",
            ),
            path(
                f"<int:person_id>/plugin/{self.name}/delete/<str:item_id>/",
                admin_view(self.delete_admin_view),
                name="token-plugin-admin-delete",
            ),
        ]
        return urls

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
            form = form_class(initial=form_data)
            form.generate_cv_link(person)
            form.post_url = post_url
            form.delete_url = self.get_admin_delete_link(person.id, form_data["id"])
            timeline_forms.append(form)
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
            form.generate_cv_link(person)

        print("after is valid check!")
        return render(request, self.item_change_form_template, context)
