from typing import Type, cast, Any

from django import forms

from .base import ListPlugin, ListItemFormMixin, ListInline, ContextDict


class LanguagesItemForm(ListItemFormMixin, forms.Form):
    name = forms.CharField(widget=forms.TextInput())
    level = forms.IntegerField(
        widget=forms.NumberInput(attrs={"min": 0, "max": 100}),
        min_value=0,
        max_value=100,
    )
    position = forms.IntegerField(widget=forms.NumberInput(), required=False)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.set_initial_position()

    @staticmethod
    def get_initial() -> ContextDict:
        return {"name": "Sprache", "level": 80}

    def set_context(self, item: dict, context: ContextDict) -> ContextDict:
        context["language"] = {
            "id": item.get("id"),
            "name": item["name"],
            "level": item["level"],
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


class LanguagesFlatForm(forms.Form):
    title = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=50, initial="Languages"
    )

    @staticmethod
    def set_context(item: dict, context: ContextDict) -> ContextDict:
        context["languages"] = {"title": item.get("title", "")}
        context["languages"]["edit_flat_url"] = context["edit_flat_url"]
        return context


class LanguagesPlugin(ListPlugin):
    name: str = "languages"
    verbose_name: str = "Languages"
    inline: ListInline
    flat_form_class = LanguagesFlatForm
    sort_by_reverse_position: bool = False

    @staticmethod
    def get_form_classes() -> dict[str, Type[forms.Form]]:
        return {"item": LanguagesItemForm, "flat": LanguagesFlatForm}
