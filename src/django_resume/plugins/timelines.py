import json
from typing import Type, Any, cast

from django import forms
from django.http import HttpRequest

from .base import (
    ListPlugin,
    ListItemFormMixin,
    ListInline,
    ListThemedTemplates,
    ThemedTemplates,
    ContextDict,
)

from ..markdown import (
    markdown_to_html,
    textarea_input_to_markdown,
    markdown_to_textarea_input,
)


def link_handler(text: str, url: str) -> str:
    return f'<a href="{url}" class="underlined">{text}</a>'


class TimelineThemedTemplates(ListThemedTemplates):
    """
    Handle the template paths for the timeline plugin. This is a special case, because
    there are plugins with different names that use the same templates. So we need to
    override the plugin name in the template path.
    """

    def get_template_path(self, template_name: str) -> str:
        template_name = self.template_names[template_name]
        return f"django_resume/plugins/timelines/{self.theme}/{template_name}"


class TimelineItemForm(ListItemFormMixin, forms.Form):
    role = forms.CharField(widget=forms.TextInput())
    company_url = forms.URLField(
        widget=forms.URLInput(), required=False, assume_scheme="https"
    )
    company_name = forms.CharField(widget=forms.TextInput(), max_length=50)
    description = forms.CharField(widget=forms.Textarea())
    start = forms.CharField(widget=forms.TextInput(), required=False)
    end = forms.CharField(widget=forms.TextInput(), required=False)
    initial_badges = [
        "Some Badge",
    ]
    badges = forms.JSONField(
        widget=forms.TextInput(), required=False, initial=initial_badges
    )
    position = forms.IntegerField(widget=forms.NumberInput(), required=False)
    initial: dict[str, Any]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.set_initial_position()
        # Transform initial text from markdown to textarea input.
        initial = cast(dict[str, Any], self.initial)
        initial["description"] = markdown_to_textarea_input(
            initial.get("description", "")
        )
        self.initial = initial

    def badges_as_json(self) -> str:
        """
        Return the initial badges which should already be a normal list of strings
        or the initial_badged list for the first render of the form encoded as json.
        """
        existing_badges = self.initial.get("badges")
        if existing_badges is not None:
            return json.dumps(existing_badges)
        return json.dumps(self.initial_badges)

    @staticmethod
    def get_initial() -> dict[str, Any]:
        """Just some default values."""
        return {
            "company_name": "company_name",
            "company_url": "https://example.com",
            "role": "role",
            "start": "start",
            "end": "end",
            "description": "description",
            "badges": TimelineItemForm.initial_badges,
        }

    def set_context(self, item: dict, context: dict[str, Any]) -> dict[str, Any]:
        context["entry"] = {
            "id": item["id"],
            "company_url": item["company_url"],
            "company_name": item["company_name"],
            "role": item["role"],
            "start": item["start"],
            "end": item["end"],
            "description": markdown_to_html(
                item["description"], handlers={"link": link_handler}
            ),
            "badges": item["badges"],
            "edit_url": context["edit_url"],
            "delete_url": context["delete_url"],
        }
        return context

    @staticmethod
    def get_max_position(items) -> int:
        """Return the maximum position value from the existing items."""
        positions = [item.get("position", 0) for item in items]
        return max(positions) if positions else -1

    def set_initial_position(self) -> None:
        """Set the position to the next available position."""
        if "position" not in self.initial:
            self.initial["position"] = self.get_max_position(self.existing_items) + 1

    def clean_title(self) -> str:
        title = self.cleaned_data["title"]
        if title == "Senor Developer":
            print("No Senor! Validation Error!")
            raise forms.ValidationError("No Senor!")
        return title

    def clean_description(self) -> str:
        return textarea_input_to_markdown(self.cleaned_data["description"])

    def clean_position(self) -> int:
        position = self.cleaned_data.get("position", 0)
        if position < 0:
            raise forms.ValidationError("Position must be a positive integer.")
        for item in self.existing_items:
            if item["id"] == self.cleaned_data["id"]:
                # updating the existing item, so we can skip checking its position
                continue
            if item.get("position") == position:
                max_position = self.get_max_position(self.existing_items)
                raise forms.ValidationError(
                    f"Position must be unique - take {max_position + 1} instead."
                )
        return position


class TimelineFlatForm(forms.Form):
    title = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=50, initial="Timeline"
    )

    @staticmethod
    def set_context(item: dict, context: dict[str, Any]) -> dict[str, Any]:
        context["timeline"] = {"title": item.get("title", "")}
        context["timeline"]["edit_flat_url"] = context["edit_flat_url"]
        return context


class TimelineMixin:
    name: str
    verbose_name: str
    inline: ListInline
    template_class: type[ThemedTemplates] = TimelineThemedTemplates

    @staticmethod
    def get_form_classes() -> dict[str, Type[forms.Form]]:
        return {"item": TimelineItemForm, "flat": TimelineFlatForm}

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
        list_plugin = cast(ListPlugin, self)
        context = ListPlugin.get_context(
            list_plugin,
            _request,
            plugin_data,
            resume_pk,
            context=context,
            edit=edit,
            theme=theme,
        )
        # convert markdown to html for rendering
        items = plugin_data.get("items", [])
        for item in items:
            item["description"] = markdown_to_html(
                item["description"], handlers={"link": link_handler}
            )
        return context


class FreelanceTimelinePlugin(TimelineMixin, ListPlugin):
    name = "freelance_timeline"
    verbose_name = "Freelance Timeline"


class EmployedTimelinePlugin(TimelineMixin, ListPlugin):
    name = "employed_timeline"
    verbose_name = "Employed Timeline"
