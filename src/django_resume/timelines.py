from typing import Type

from django import forms
from django.urls import reverse

from .plugins import ListPlugin, ListItemFormMixin, ListTemplates


class TimelineItemForm(ListItemFormMixin, forms.Form):
    role = forms.CharField(widget=forms.TextInput())
    company_url = forms.URLField(
        widget=forms.URLInput(), required=False, assume_scheme="https"
    )
    company_name = forms.CharField(widget=forms.TextInput(), max_length=50)
    description = forms.CharField(widget=forms.Textarea())
    start = forms.CharField(widget=forms.TextInput(), required=False)
    end = forms.CharField(widget=forms.TextInput(), required=False)
    badges = forms.CharField(widget=forms.TextInput(), required=False)
    position = forms.IntegerField(widget=forms.NumberInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_initial_badges()
        self.set_initial_position()

    def set_initial_badges(self):
        """Transform the list of badges into a comma-separated string."""
        if "badges" in self.initial and isinstance(self.initial["badges"], list):
            self.initial["badges"] = ",".join(self.initial["badges"])

    @staticmethod
    def get_max_position(items):
        """Return the maximum position value from the existing items."""
        positions = [item.get("position", 0) for item in items]
        return max(positions) if positions else -1

    def set_initial_position(self):
        """Set the position to the next available position."""
        if "position" not in self.initial:
            self.initial["position"] = self.get_max_position(self.existing_items) + 1

    def clean_title(self):
        title = self.cleaned_data["title"]
        if title == "Senor Developer":
            print("No Senor! Validation Error!")
            raise forms.ValidationError("No Senor!")
        return title

    def clean_badges(self):
        badges = self.cleaned_data.get("badges", "")
        # Split the comma-separated values and strip any extra spaces
        badge_list = [badge.strip() for badge in badges.split(",")]
        return badge_list

    def clean_position(self):
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
    title = forms.CharField(widget=forms.TextInput(), required=False, max_length=50)


class TimelineForContext:
    def __init__(
        self,
        *,
        title: str,
        ordered_entries: list[dict],
        templates: ListTemplates,
        edit_flat_url: str,
        edit_flat_post_url: str,
    ):
        self.title = title
        self.ordered_entries = ordered_entries
        self.templates = templates
        self.edit_flat_url = edit_flat_url
        self.edit_flat_post_url = edit_flat_post_url


class TimelineMixin:
    name: str
    verbose_name: str
    templates = ListTemplates(
        main="django_resume/plain/timeline.html",
        flat="django_resume/plain/timeline_flat.html",
        flat_form="django_resume/plain/timeline_flat_form.html",
        item="django_resume/plain/timeline_item.html",
        item_form="django_resume/plain/timeline_item_form.html",
    )

    @staticmethod
    def get_form_classes() -> dict[str, Type[forms.Form]]:
        return {"item": TimelineItemForm, "flat": TimelineFlatForm}

    @staticmethod
    def items_ordered_by_position(items, reverse=False):
        return sorted(items, key=lambda item: item.get("position", 0), reverse=reverse)

    def get_data_for_context(self, plugin_data, person_pk):
        print(
            "edit flat post: ",
            reverse(
                f"django_resume:{self.name}-edit-flat-post",
                kwargs={"person_id": person_pk},
            ),
        )
        ordered_entries = self.items_ordered_by_position(
            plugin_data.get("items", []), reverse=True
        )
        for entry in ordered_entries:
            entry["edit_url"] = self.inline.get_edit_item_url(
                person_pk, item_id=entry["id"]
            )
        timeline = TimelineForContext(
            title=plugin_data.get("flat", {}).get("title", self.verbose_name),
            ordered_entries=ordered_entries,
            templates=self.templates,
            edit_flat_url=reverse(
                f"django_resume:{self.name}-edit-flat", kwargs={"person_id": person_pk}
            ),
            edit_flat_post_url=reverse(
                f"django_resume:{self.name}-edit-flat-post",
                kwargs={"person_id": person_pk},
            ),
        )
        return timeline


class FreelanceTimelinePlugin(TimelineMixin, ListPlugin):
    name = "freelance_timeline"
    verbose_name = "Freelance Timeline"


class EmployedTimelinePlugin(TimelineMixin, ListPlugin):
    name = "employed_timeline"
    verbose_name = "Employed Timeline"
