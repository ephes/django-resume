from django import forms
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.http import HttpRequest

from .base import SimplePlugin, SimpleTemplates, ContextDict


class CustomFileObject:
    def __init__(self, filename):
        self.name = filename
        self.url = default_storage.url(filename)

    def __str__(self):
        return self.name


class IdentityForm(forms.Form):
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        initial_avatar_img_filename = self.initial.get("avatar_img")
        print("initial avatar img: ", initial_avatar_img_filename)
        if initial_avatar_img_filename is not None:
            self.fields["avatar_img"].initial = CustomFileObject(
                initial_avatar_img_filename
            )
            print("initial avatar img: ", self.fields["avatar_img"].initial)

    @property
    def avatar_img_url(self):
        return default_storage.url(self.initial.get("avatar_img", ""))

    def clean(self):
        # super ugly - FIXME
        cleaned_data = super().clean()
        avatar_img = cleaned_data.get("avatar_img")
        clear_avatar = cleaned_data.get("clear_avatar")
        print("cleaned_data: ", cleaned_data)

        avatar_handled = False
        just_clear_the_avatar = clear_avatar and not hasattr(
            avatar_img, "temporary_file_path"
        )
        if just_clear_the_avatar:
            cleaned_data["avatar_img"] = None
            avatar_handled = True

        set_new_avatar_image = (
            isinstance(avatar_img, InMemoryUploadedFile) and not avatar_handled
        )
        if set_new_avatar_image:
            if avatar_img.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Image file too large ( > 2mb )")
            cleaned_data["avatar_img"] = default_storage.save(
                f"uploads/{avatar_img.name}", ContentFile(avatar_img.read())
            )
            avatar_handled = True

        keep_current_avatar = (
            not clear_avatar and isinstance(avatar_img, str) and not avatar_handled
        )
        if keep_current_avatar:
            cleaned_data["avatar_img"] = avatar_img

        del cleaned_data["clear_avatar"]  # reset the clear_avatar field
        return cleaned_data


class IdentityPlugin(SimplePlugin):
    name: str = "identity"
    verbose_name: str = "Identity Information"
    templates = SimpleTemplates(
        main="django_resume/identity/plain/content.html",
        form="django_resume/identity/plain/form.html",
    )
    admin_form_class = inline_form_class = IdentityForm

    def get_context(
        self,
        _request: HttpRequest,
        plugin_data: dict,
        resume_pk: int,
        *,
        context: ContextDict,
        edit: bool = False,
    ) -> ContextDict:
        context = super().get_context(
            _request, plugin_data, resume_pk, context=context, edit=edit
        )
        context["avatar_img_url"] = default_storage.url(
            plugin_data.get("avatar_img", "")
        )
        return context
