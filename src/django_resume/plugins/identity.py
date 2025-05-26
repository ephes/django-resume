from django import forms
from django.core.files.storage import default_storage
from django.http import HttpRequest

from .base import SimplePlugin, ContextDict
from ..images import ImageFormMixin


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


class IdentityPlugin(SimplePlugin):
    name: str = "identity"
    verbose_name: str = "Identity Information"
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
