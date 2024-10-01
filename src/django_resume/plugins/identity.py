from django import forms

from .base import SimplePlugin, SimpleTemplates


class IdentityForm(forms.Form):
    name = forms.CharField(label="Your name", max_length=100, initial="Your name")
    pronouns = forms.CharField(label="Pronouns", max_length=100, initial="they/them")
    location_name = forms.CharField(
        label="Location", max_length=100, initial="City, Country, Timezone"
    )
    location_url = forms.URLField(
        label="Location url",
        max_length=100,
        initial="https://maps.app.goo.gl/TkuHEzeGpr7u2aCD7",
        assume_scheme="https",
    )
    profile_photo_url = forms.URLField(
        label="Profile photo url",
        max_length=100,
        initial="https://example.com/photo.jpg",
        assume_scheme="https",
    )
    tagline = forms.CharField(label="Tagline", max_length=512, initial="Tagline")
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


class IdentityPlugin(SimplePlugin):
    name: str = "identity"
    verbose_name: str = "Identity Information"
    templates = SimpleTemplates(
        main="django_resume/identity/plain/content.html",
        form="django_resume/identity/plain/form.html",
    )
    admin_form_class = inline_form_class = IdentityForm
