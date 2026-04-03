import hmac
import secrets
import string
from datetime import datetime, timedelta

from django.conf import settings
from django import forms
from django.core.exceptions import ImproperlyConfigured, PermissionDenied
from django.http import HttpRequest
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils.html import format_html
from django.utils import timezone
from django.utils.safestring import SafeString

from .base import ListPlugin, ListItemFormMixin
from ..models import Resume


TOKEN_ALPHABET = string.ascii_letters + string.digits
DEFAULT_TOKEN_TTL = timedelta(days=30)
TOKEN_TTL_SETTING = "DJANGO_RESUME_TOKEN_TTL"


class _UnsetTTL:
    pass


UNSET_TTL = _UnsetTTL()


def normalize_token_created(value: object) -> datetime | None:
    if isinstance(value, datetime):
        created = value
    elif isinstance(value, str):
        created = parse_datetime(value)
        if created is None:
            try:
                created = datetime.fromisoformat(value)
            except ValueError:
                return None
    else:
        return None

    if timezone.is_naive(created):
        return timezone.make_aware(created, timezone.get_current_timezone())
    return created


def get_token_ttl() -> timedelta | None:
    ttl = getattr(settings, TOKEN_TTL_SETTING, DEFAULT_TOKEN_TTL)
    if ttl is None or isinstance(ttl, timedelta):
        return ttl
    raise ImproperlyConfigured(
        f"{TOKEN_TTL_SETTING} must be a datetime.timedelta or None."
    )


def is_token_expired(
    item: dict,
    *,
    now: datetime | None = None,
    ttl: timedelta | None | _UnsetTTL = UNSET_TTL,
) -> bool:
    if ttl is UNSET_TTL:
        ttl = get_token_ttl()
    if ttl is None:
        return False

    created = normalize_token_created(item.get("created"))
    if created is None:
        # Keep older token entries without timestamps working.
        return False

    if now is None:
        now = timezone.now()
    return created + ttl <= now


def generate_random_string(length=20) -> str:
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(length))


class HTMLLinkWidget(forms.Widget):
    def render(self, name, value, attrs=None, renderer=None) -> SafeString:
        if not value:
            return format_html("")
        return format_html(
            '<a href="{}" target="_blank" rel="noreferrer noopener">{}</a>',
            value,
            value,
        )


class TokenItemForm(ListItemFormMixin, forms.Form):
    token = forms.CharField(max_length=255, required=True, label="Token")
    receiver = forms.CharField(max_length=255)
    created = forms.DateTimeField(widget=forms.HiddenInput(), required=False)
    cv_link = forms.CharField(required=False, label="CV Link", widget=HTMLLinkWidget())

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if not self.initial.get("token"):
            self.fields["token"].initial = generate_random_string()
        self.token = self.initial.get("token") or self.fields["token"].initial

        created = normalize_token_created(self.initial.get("created"))
        if created is not None:
            self.initial["created"] = created
        else:
            # Set the 'created' field to the current time if it's not already set
            created = timezone.now()
            self.initial["created"] = created
            self.fields["created"].initial = created

        self.generate_cv_link(self.resume)

    def generate_cv_link(self, resume: Resume) -> None:
        base_url = reverse("django_resume:cv", kwargs={"slug": resume.slug})
        link = f"{base_url}?token={self.token}"
        self.fields["cv_link"].initial = link

    def clean_token(self) -> str:
        token = self.cleaned_data["token"]
        if not token:
            raise forms.ValidationError("Token required.")
        return token

    def clean_created(self) -> str:
        created = self.cleaned_data["created"]
        if created is None:
            created = timezone.now()
        return created.isoformat()

    def clean(self) -> dict:
        cleaned_data = super().clean()
        if cleaned_data is None:
            return {}
        cleaned_data.pop("cv_link", None)  # Remove 'cv_link' from cleaned_data
        return cleaned_data


class TokenForm(forms.Form):
    token_required = forms.BooleanField(required=False, label="Token Required")


class TokenViaGetForm(forms.Form):
    token = forms.CharField(max_length=255, required=True, label="Token")


class TokenPlugin(ListPlugin):
    """
    Generate tokens for a resume.

    If you want to restrict access to a resume's resume, you can generate a token.
    The token can be shared with the resume, and they can access their resume using the token.
    """

    name = "token"
    verbose_name = "CV Token"
    flat_template = "django_resume/plain/token_flat.html"
    flat_form_template = "django_resume/plain/token_flat_form.html"

    @staticmethod
    def get_admin_item_form() -> type[forms.Form]:
        return TokenItemForm

    @staticmethod
    def get_admin_form() -> type[forms.Form]:
        return TokenForm

    @staticmethod
    def get_form_classes() -> dict[str, type[forms.Form]]:
        return {"item": TokenItemForm, "flat": TokenForm}

    @staticmethod
    def token_is_required(plugin_data: dict) -> bool:
        return plugin_data.get("flat", {"token_required": True}).get(
            "token_required", True
        )

    @staticmethod
    def check_permissions(request: HttpRequest, plugin_data: dict) -> None:
        token_required = TokenPlugin.token_is_required(plugin_data)
        if not token_required or request.user.is_authenticated:
            return None
        form = TokenViaGetForm(request.GET)
        if not form.is_valid():
            raise PermissionDenied("Token required to access this page.")
        token = form.cleaned_data["token"]
        if token is None:
            raise PermissionDenied("Token required to access this page.")
        matched_token = False
        matched_unexpired_token = False
        now = timezone.now()
        ttl = get_token_ttl()
        for item in plugin_data.get("items", []):
            if not isinstance(item, dict):
                continue
            stored_token = item.get("token")
            if not isinstance(stored_token, str):
                continue
            token_matches = hmac.compare_digest(token, stored_token)
            token_is_unexpired = not is_token_expired(item, now=now, ttl=ttl)
            matched_token |= token_matches
            matched_unexpired_token |= token_matches & token_is_unexpired
        if matched_unexpired_token:
            return None
        if matched_token:
            raise PermissionDenied("Token expired.")
        raise PermissionDenied("Invalid token.")

    def get_context(
        self,
        request: HttpRequest,
        plugin_data: dict,
        resume_pk: int,
        *,
        context: dict,
        edit: bool = False,
        theme: str = "plain",
    ) -> dict:
        self.check_permissions(request, plugin_data)
        return {}
