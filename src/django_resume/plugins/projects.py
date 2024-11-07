import json

from typing import Type, cast, Any

from django import forms
from django.http import HttpRequest

from .base import ListPlugin, ListItemFormMixin, ListInline, ContextDict

from ..markdown import (
    markdown_to_html,
    textarea_input_to_markdown,
    markdown_to_textarea_input,
)


def link_handler(text: str, url: str) -> str:
    return f'<a href="{url}" class="underlined">{text}</a>'


class ProjectItemForm(ListItemFormMixin, forms.Form):
    title = forms.CharField(widget=forms.TextInput())
    url = forms.URLField(widget=forms.URLInput(), required=False, assume_scheme="https")
    description = forms.CharField(widget=forms.Textarea())
    initial_badges = ["Some Badge", "Another Badge"]
    badges = forms.JSONField(
        widget=forms.TextInput(), required=False, initial=initial_badges
    )
    position = forms.IntegerField(widget=forms.NumberInput(), required=False)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.set_initial_position()
        # Transform initial text from markdown to textarea input.
        initial = cast(dict[str, Any], self.initial)
        initial["description"] = markdown_to_textarea_input(
            self.initial.get("description", "")
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
    def get_initial() -> ContextDict:
        """Just some default values."""
        return {
            "title": "Project Title",
            "url": "https://example.com/project/",
            "description": "description",
            "badges": ProjectItemForm.initial_badges,
        }

    def set_context(self, item: dict, context: ContextDict) -> ContextDict:
        context["project"] = {
            "id": item["id"],
            "url": item["url"],
            "title": item["title"],
            "description": markdown_to_html(
                item["description"], handlers={"link": link_handler}
            ),
            "badges": item["badges"],
            "edit_url": context["edit_url"],
            "delete_url": context["delete_url"],
        }
        return context

    def set_initial_badges(self) -> None:
        """Transform the list of badges into a comma-separated string."""
        initial = cast(dict[str, Any], self.initial)
        if "badges" in initial and isinstance(initial["badges"], list):
            initial["badges"] = ",".join(initial["badges"])
        self.initial = initial

    @staticmethod
    def get_max_position(items: list[dict]) -> int:
        """Return the maximum position value from the existing items."""
        positions = [item.get("position", 0) for item in items]
        return max(positions) if positions else -1

    def set_initial_position(self) -> None:
        """Set the position to the next available position."""
        initial = cast(dict[str, Any], self.initial)
        if "position" not in initial:
            initial["position"] = self.get_max_position(self.existing_items) + 1
        self.initial = initial

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


class ProjectFlatForm(forms.Form):
    title = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=50, initial="Projects"
    )

    @staticmethod
    def set_context(item: dict, context: ContextDict) -> ContextDict:
        context["projects"] = {"title": item.get("title", "")}
        context["projects"]["edit_flat_url"] = context["edit_flat_url"]
        return context


class ProjectsPlugin(ListPlugin):
    name: str = "projects"
    verbose_name: str = "Projects"
    inline: ListInline
    flat_form_class = ProjectFlatForm
    sort_by_reverse_position: bool = False

    @staticmethod
    def get_form_classes() -> dict[str, Type[forms.Form]]:
        return {"item": ProjectItemForm, "flat": ProjectFlatForm}

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
