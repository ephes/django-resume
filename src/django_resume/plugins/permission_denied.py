from django import forms
from django.core.files.storage import default_storage
from django.http import HttpRequest

from .base import SimplePlugin, ContextDict
from ..images import ImageFormMixin
from ..markdown import (
    markdown_to_html,
    markdown_to_textarea_input,
    textarea_input_to_markdown,
)


def link_handler(text: str, url: str) -> str:
    return f'<a href="{url}" class="underlined">{text}</a>'


class PermissionDeniedForm(ImageFormMixin, forms.Form):
    title = forms.CharField(
        label="Permission Denied Title",
        max_length=256,
        initial="Access Token Needed for CV",
    )
    sub_title = forms.CharField(
        label="Permission Denied Sub-Title",
        max_length=256,
        initial="Unlock access with a simple email",
    )
    email = forms.EmailField(
        label="Email address",
        max_length=100,
        initial="tokensupport@example.com",
    )
    text = forms.CharField(
        label="Permission Denied Message",
        max_length=1024,
        initial=(
            "Hi there! It seems that an access token is needed to view this page. "
            "Don’t worry, it’s a quick and easy step. Simply send a brief email to "
            "the owner, and she’ll gladly assist you in obtaining the access you need. "
            "We are always happy to help and will make sure you’re set up in no time. "
            "Thanks for reaching out!"
        ),
        widget=forms.Textarea,
    )
    avatar_img = forms.FileField(
        label="Profile Image",
        max_length=100,
        required=False,
    )
    clear_avatar = forms.BooleanField(
        widget=forms.CheckboxInput, initial=False, required=False
    )
    avatar_alt = forms.CharField(
        label="Profile photo alt text",
        max_length=100,
        initial="Profile photo",
        required=False,
    )
    image_fields = [("avatar_img", "clear_avatar")]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Transform initial text from markdown to textarea input.
        self.initial["text"] = markdown_to_textarea_input(self.initial.get("text", ""))

    def clean_text(self):
        text = self.cleaned_data["text"]
        text = textarea_input_to_markdown(text)
        return text

    @property
    def avatar_img_url(self):
        return self.get_image_url_for_field(self.initial.get("avatar_img", ""))


class PermissionDeniedPlugin(SimplePlugin):
    name: str = "permission_denied"
    verbose_name: str = "Permission Denied"
    admin_form_class = inline_form_class = PermissionDeniedForm
    prompt = """
        Create a django-resume plugin that displays an error message when a user attempts to access a
        page without proper authentication. The plugin should provide customizable fields for
        the title, subtitle, email, message, and profile image. The title should contain a brief
        heading explaining the restricted access. The subtitle should provide a concise message
        guiding the user on how to gain access. The email field should include a contact email
        address for requesting access. The message field should contain detailed information
        that may include links using markdown formatting. The profile image field should allow
        for an optional avatar representing the page owner or support contact.
        
        The plugin should be titled “Permission Denied” and should be displayed with a
        structured layout. The title should be prominently shown as an H1 heading, followed by
        the subtitle as an H2 heading. The message should support markdown formatting to allow
        clickable links. The email address should be displayed in an editable text field so that
        users can copy or modify it if needed. If an avatar image is provided, it should be
        displayed to the right of the message; otherwise, a default placeholder icon should be
        used.
        
        The editing interface should allow users to update the title, subtitle, email, and
        message content inline. The avatar image should be selectable via file upload, with an
        option to remove it if desired. Input validation should be applied to ensure proper
        formatting of each field.
        
        In terms of rendering behavior, the title and message content should be aligned to the
        left, while the avatar and optional date fields should be positioned on the right. If
        start and end dates are provided, they should be displayed in the format “YYYY” or
        “YYYY-MM”. The message text should retain line breaks and properly handle links using
        markdown formatting.
        
        The plugin should provide a user-friendly experience with clear guidance for
        unauthorized visitors and simple contact options for requesting access.
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
            _request, plugin_data, resume_pk, context=context, edit=edit
        )
        context["avatar_img_url"] = default_storage.url(
            plugin_data.get("avatar_img", "")
        )
        context["text"] = markdown_to_html(
            plugin_data.get("text", ""), handlers={"link": link_handler}
        )
        return context
