from typing import Type, Any

from django import forms

from .base import ListPlugin, ListItemFormMixin, ListTemplates, ListInline


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
            "badges": "badges",
        }

    def set_context(self, item: dict, context: dict[str, Any]) -> dict[str, Any]:
        context["entry"] = {
            "id": item["id"],
            "company_url": item["company_url"],
            "company_name": item["company_name"],
            "role": item["role"],
            "start": item["start"],
            "end": item["end"],
            "description": item["description"],
            "badges": item["badges"],
            "edit_url": context["edit_url"],
            "delete_url": context["delete_url"],
        }
        return context

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


class FreelanceTimelinePlugin(TimelineMixin, ListPlugin):
    name = "freelance_timeline"
    verbose_name = "Freelance Timeline"


class EmployedTimelinePlugin(TimelineMixin, ListPlugin):
    name = "employed_timeline"
    verbose_name = "Employed Timeline"
