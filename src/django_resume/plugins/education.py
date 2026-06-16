from typing import Type, cast, Any

from django import forms

from .base import ListPlugin, ListItemFormMixin, ListInline, ContextDict


class EducationItemForm(ListItemFormMixin, forms.Form):
    school_name = forms.CharField(widget=forms.TextInput(), max_length=100)
    school_url = forms.URLField(
        widget=forms.URLInput(), required=False, assume_scheme="https"
    )
    degree = forms.CharField(widget=forms.TextInput(), required=False, max_length=200)
    start = forms.CharField(widget=forms.TextInput(), required=False)
    end = forms.CharField(widget=forms.TextInput(), required=False)
    position = forms.IntegerField(widget=forms.NumberInput(), required=False)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.set_initial_position()

    @staticmethod
    def get_initial() -> ContextDict:
        return {
            "school_name": "School name",
            "school_url": "https://example.com",
            "degree": "Degree",
            "start": "",
            "end": "Year",
        }

    def set_context(self, item: dict, context: ContextDict) -> ContextDict:
        context["entry"] = {
            "id": item.get("id"),
            "school_name": item["school_name"],
            "school_url": item.get("school_url", ""),
            "degree": item.get("degree", ""),
            "start": item.get("start", ""),
            "end": item.get("end", ""),
            "edit_url": context.get("edit_url"),
            "delete_url": context.get("delete_url"),
        }
        return context

    @staticmethod
    def get_max_position(items: list[dict]) -> int:
        positions = [item.get("position", 0) for item in items]
        return max(positions) if positions else -1

    def set_initial_position(self) -> None:
        initial = cast(dict[str, Any], self.initial)
        if "position" not in initial:
            initial["position"] = self.get_max_position(self.existing_items) + 1
        self.initial = initial

    def clean_position(self) -> int:
        position = self.cleaned_data.get("position", 0) or 0
        if position < 0:
            raise forms.ValidationError("Position must be a positive integer.")
        for item in self.existing_items:
            if item["id"] == self.cleaned_data["id"]:
                continue
            if item.get("position") == position:
                max_position = self.get_max_position(self.existing_items)
                raise forms.ValidationError(
                    f"Position must be unique - take {max_position + 1} instead."
                )
        return position


class EducationFlatForm(forms.Form):
    title = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=50, initial="Education"
    )

    @staticmethod
    def set_context(item: dict, context: ContextDict) -> ContextDict:
        context["education"] = {"title": item.get("title", "")}
        context["education"]["edit_flat_url"] = context["edit_flat_url"]
        return context


class EducationPlugin(ListPlugin):
    name: str = "education"
    verbose_name: str = "Education"
    inline: ListInline
    flat_form_class = EducationFlatForm
    sort_by_reverse_position: bool = False

    @staticmethod
    def get_form_classes() -> dict[str, Type[forms.Form]]:
        return {"item": EducationItemForm, "flat": EducationFlatForm}
