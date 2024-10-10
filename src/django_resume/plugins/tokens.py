import random
import string
from datetime import datetime

from django import forms
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe

from .base import ListPlugin, ListItemFormMixin


def generate_random_string(length=20):
    return "".join(random.choices(string.ascii_letters + string.digits, k=length))


class HTMLLinkWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None):
        return mark_safe(value) if value else ""


class TokenItemForm(ListItemFormMixin, forms.Form):
    token = forms.CharField(max_length=255, required=True, label="Token")
    receiver = forms.CharField(max_length=255)
    created = forms.DateTimeField(widget=forms.HiddenInput(), required=False)
    cv_link = forms.CharField(required=False, label="CV Link", widget=HTMLLinkWidget())

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

        self.generate_cv_link(self.person)

    def generate_cv_link(self, person):
        base_url = reverse("django_resume:cv", kwargs={"slug": person.slug})
        link = f"{base_url}?token={self.token}"
        self.fields["cv_link"].initial = mark_safe(
            f'<a href="{link}" target="_blank">{link}</a>'
        )

    def clean_token(self):
        token = self.cleaned_data["token"]
        if not token:
            raise forms.ValidationError("Token required.")
        return token

    def clean_created(self):
        created = self.cleaned_data["created"]
        return created.isoformat()

    def clean(self):
        cleaned_data = super().clean()
        cleaned_data.pop("cv_link", None)  # Remove 'cv_link' from cleaned_data
        return cleaned_data


class TokenForm(forms.Form):
    token_required = forms.BooleanField(required=False, label="Token Required")


class TokenPlugin(ListPlugin):
    """
    Generate tokens for a person.

    If you want to restrict access to a person's resume, you can generate a token.
    The token can be shared with the person and they can access their resume using the token.
    """

    name = "token"
    verbose_name = "CV Token"
    flat_template = "django_resume/plain/token_flat.html"
    flat_form_template = "django_resume/plain/token_flat_form.html"

    def get_admin_item_form(self):
        return TokenItemForm

    def get_admin_form(self):
        return TokenForm
