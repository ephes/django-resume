from django import forms
from django.core.files.storage import default_storage
from django.http import HttpRequest

from .base import SimplePlugin, ContextDict
from ..images import ImageFormMixin
from ..interchange.pointer import get_pointer
from ..interchange.protocols import AdapterExport, AdapterImport


class IdentityForm(ImageFormMixin, forms.Form):
    name = forms.CharField(label="Your name", max_length=100, initial="Your name")
    pronouns = forms.CharField(
        label="Pronouns", max_length=100, initial="your/pronouns"
    )
    tagline = forms.CharField(
        label="Tagline", max_length=512, initial="Some tagline text."
    )
    location_name = forms.CharField(
        label="Location", max_length=100, initial="City, Country, Timezone"
    )
    location_url = forms.URLField(
        label="Location url",
        max_length=100,
        initial="https://maps.app.goo.gl/TkuHEzeGpr7u2aCD7",
        assume_scheme="https",
    )
    avatar_img = forms.FileField(
        label="Profile Image",
        max_length=100,
        required=False,
    )
    avatar_alt = forms.CharField(
        label="Profile photo alt text",
        max_length=100,
        initial="Profile photo",
        required=False,
    )
    clear_avatar = forms.BooleanField(
        widget=forms.CheckboxInput, initial=False, required=False
    )
    email = forms.EmailField(
        label="Email address",
        max_length=100,
        initial="foobar@example.com",
    )
    phone = forms.CharField(
        label="Phone number",
        max_length=100,
        initial="+1 555 555 5555",
    )
    github = forms.URLField(
        label="GitHub url",
        max_length=100,
        initial="https://github.com/foobar/",
        assume_scheme="https",
    )
    linkedin = forms.URLField(
        label="LinkedIn profile url",
        max_length=100,
        initial="https://linkedin.com/foobar/",
        assume_scheme="https",
    )
    mastodon = forms.URLField(
        label="Mastodon url",
        max_length=100,
        initial="https://fosstodon.org/@foobar",
        assume_scheme="https",
    )
    image_fields = [("avatar_img", "clear_avatar")]

    @property
    def avatar_img_url(self) -> str:
        return self.get_image_url_for_field(self.initial.get("avatar_img", ""))


class IdentityJsonResumeAdapter:
    owned_paths = (
        "/basics/name",
        "/basics/label",
        "/basics/email",
        "/basics/phone",
        "/basics/image",
        "/basics/location",
        "/basics/profiles",
    )
    multivalued_paths: tuple[str, ...] = ()

    def export(self, facts: dict) -> AdapterExport:
        contributions: list[tuple[str, object]] = []
        notes: list[str] = []
        for pointer, key in (
            ("/basics/name", "name"),
            ("/basics/label", "tagline"),
            ("/basics/email", "email"),
            ("/basics/phone", "phone"),
            ("/basics/image", "avatar_url"),
        ):
            value = facts.get(key, "")
            if value:
                contributions.append((pointer, value))
        profiles = []
        for network, key in (
            ("GitHub", "github"),
            ("LinkedIn", "linkedin"),
            ("Mastodon", "mastodon"),
        ):
            url = facts.get(key, "")
            if url:
                profiles.append({"network": network, "url": url})
        if profiles:
            contributions.append(("/basics/profiles", profiles))
        location_name = facts.get("location_name", "")
        if location_name:
            contributions.append(("/basics/location", {"address": location_name}))
        for key in ("pronouns", "location_url", "avatar_alt"):
            if facts.get(key):
                notes.append(f"identity.{key} has no JSON Resume mapping; not exported")
        return AdapterExport(contributions=contributions, notes=notes)

    source_paths = (
        "/basics/name",
        "/basics/label",
        "/basics/email",
        "/basics/phone",
        "/basics/image",
        "/basics/url",
        "/basics/location",
        "/basics/profiles",
    )

    def import_data(self, document: dict) -> AdapterImport:
        basics = get_pointer(document, "/basics", {}) or {}
        if not isinstance(basics, dict):
            return AdapterImport(plugin_data={}, notes=["basics is not an object"])
        plugin_data = {
            "name": basics.get("name", ""),
            "tagline": basics.get("label", ""),
            "email": basics.get("email", ""),
            "phone": basics.get("phone", ""),
            "github": "",
            "linkedin": "",
            "mastodon": "",
            "pronouns": "",
            "location_name": "",
            "location_url": "",
            "avatar_img": "",
            "avatar_alt": "",
        }
        notes = []
        for profile in basics.get("profiles", []) or []:
            if not isinstance(profile, dict):
                continue
            network = str(profile.get("network", "")).lower()
            url = profile.get("url", "")
            if network == "github":
                plugin_data["github"] = url
            elif network == "linkedin":
                plugin_data["linkedin"] = url
            elif network == "mastodon":
                plugin_data["mastodon"] = url
            else:
                label = profile.get("network") or profile.get("url") or "(unknown)"
                notes.append(f"basics.profiles entry {label!r} is not imported")
        if basics.get("url"):
            notes.append("basics.url is not imported by the identity plugin")
        if basics.get("image"):
            notes.append("basics.image cannot be imported into local avatar storage")
        if basics.get("location"):
            notes.append("basics.location is not imported by the identity plugin")
        return AdapterImport(plugin_data=plugin_data, notes=notes)


class IdentityPlugin(SimplePlugin):
    name: str = "identity"
    verbose_name: str = "Identity Information"
    capabilities: tuple[str, ...] = ("identity", "contact", "portfolio", "cv")
    admin_form_class = inline_form_class = IdentityForm
    prompt = """
        Create a django-resume plugin to display and manage a person’s profile information. The plugin
        should include fields for the user’s name, pronouns, tagline, location, email, phone
        number, and social media links such as GitHub, LinkedIn, and Mastodon. Additionally, an
        avatar image can be uploaded to personalize the profile further.
        
        The plugin presents the profile with the user’s name as a heading, followed by pronouns,
        a tagline, and a location link. Contact details and social media icons are displayed as
        clickable links. An avatar image, if provided, is shown alongside the profile
        information; otherwise, a default placeholder is used.
        
        The editing interface allows users to update their profile details inline, including
        changing the avatar image, updating contact links, and modifying text content. Changes
        take effect only after submitting the form, ensuring data integrity and preventing
        accidental modifications.
        
        This plugin offers an intuitive way to manage and display profile information, providing
        a professional and visually appealing representation of an individual.    
    """

    def get_context(
        self,
        _request: HttpRequest,
        plugin_data: dict,
        resume_pk: int,
        *,
        context: ContextDict,
        edit: bool = False,
        theme: str = "plain",
    ) -> ContextDict:
        context = super().get_context(
            _request, plugin_data, resume_pk, context=context, edit=edit, theme=theme
        )
        context["avatar_img_url"] = default_storage.url(
            plugin_data.get("avatar_img", "")
        )
        return context

    def get_structured_data(self, resume) -> dict:
        data = self.get_data(resume)
        avatar = data.get("avatar_img") or ""
        return {
            "name": data.get("name", ""),
            "tagline": data.get("tagline", ""),
            "email": data.get("email", ""),
            "phone": data.get("phone", ""),
            "avatar_url": default_storage.url(avatar) if avatar else "",
            "github": data.get("github", ""),
            "linkedin": data.get("linkedin", ""),
            "mastodon": data.get("mastodon", ""),
            "pronouns": data.get("pronouns", ""),
            "location_name": data.get("location_name", ""),
            "location_url": data.get("location_url", ""),
            "avatar_alt": data.get("avatar_alt", ""),
        }

    def get_export_adapters(self) -> dict:
        return {"json_resume": IdentityJsonResumeAdapter()}

    def get_import_adapters(self) -> dict:
        return {"json_resume": IdentityJsonResumeAdapter()}
