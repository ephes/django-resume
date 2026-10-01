from typing import Type, cast, Any

from django import forms

from .base import ListPlugin, ListItemFormMixin, ListInline, ContextDict
from ..interchange.pointer import get_pointer
from ..interchange.protocols import AdapterExport, AdapterImport
from ..formats.json_resume.dates import is_valid_resume_date


class AwardsItemForm(ListItemFormMixin, forms.Form):
    title = forms.CharField(widget=forms.TextInput())
    project = forms.CharField(widget=forms.TextInput(), required=False)
    year = forms.CharField(widget=forms.TextInput(), required=False)
    position = forms.IntegerField(widget=forms.NumberInput(), required=False)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.set_initial_position()

    @staticmethod
    def get_initial() -> ContextDict:
        return {"title": "Award title", "project": "Project", "year": "2024"}

    def set_context(self, item: dict, context: ContextDict) -> ContextDict:
        context["award"] = {
            "id": item.get("id"),
            "title": item["title"],
            "project": item.get("project", ""),
            "year": item.get("year", ""),
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


class AwardsFlatForm(forms.Form):
    title = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=50, initial="Awards"
    )

    @staticmethod
    def set_context(item: dict, context: ContextDict) -> ContextDict:
        context["awards"] = {"title": item.get("title", "")}
        context["awards"]["edit_flat_url"] = context["edit_flat_url"]
        return context


class AwardsJsonResumeAdapter:
    owned_paths = ("/awards",)
    multivalued_paths: tuple[str, ...] = ()

    def export(self, facts: dict) -> AdapterExport:
        awards: list[dict] = []
        notes: list[str] = []
        for item in facts.get("awards", []):
            entry: dict[str, object] = {}
            if item.get("title"):
                entry["title"] = item["title"]
            if item.get("project"):
                entry["summary"] = item["project"]
            year = item.get("year", "")
            if year and is_valid_resume_date(year):
                entry["date"] = year
            elif year:
                notes.append(
                    f"awards item {item.get('title', '?')!r} year {year!r} is not a "
                    "valid date; not exported"
                )
            if entry:
                awards.append(entry)
        contributions = [("/awards", awards)] if awards else []
        return AdapterExport(contributions=contributions, notes=notes)

    source_paths = ("/awards",)

    def import_data(self, document: dict) -> AdapterImport:
        awards = get_pointer(document, "/awards", []) or []
        items = []
        notes = []
        for position, entry in enumerate(
            item for item in awards if isinstance(item, dict)
        ):
            title = entry.get("title", "")
            if entry.get("awarder"):
                notes.append(f"awards entry {title!r} awarder is not imported")
            items.append(
                {
                    "id": f"json-resume-award-{position + 1}",
                    "title": title,
                    "project": entry.get("summary", ""),
                    "year": entry.get("date", ""),
                    "position": position,
                }
            )
        if not items:
            return AdapterImport(plugin_data={})
        return AdapterImport(
            plugin_data={"flat": {"title": "Awards"}, "items": items}, notes=notes
        )


class AwardsPlugin(ListPlugin):
    name: str = "awards"
    verbose_name: str = "Awards"
    capabilities: tuple[str, ...] = ("awards", "cv")
    inline: ListInline
    flat_form_class = AwardsFlatForm
    sort_by_reverse_position: bool = False

    @staticmethod
    def get_form_classes() -> dict[str, Type[forms.Form]]:
        return {"item": AwardsItemForm, "flat": AwardsFlatForm}

    def get_structured_data(self, resume) -> dict:
        items = self.items_ordered_by_position(self.get_data(resume).get("items", []))
        return {
            "awards": [
                {
                    "title": item.get("title", ""),
                    "project": item.get("project", ""),
                    "year": item.get("year", ""),
                }
                for item in items
            ]
        }

    def get_export_adapters(self) -> dict:
        return {"json_resume": AwardsJsonResumeAdapter()}

    def get_import_adapters(self) -> dict:
        return {"json_resume": AwardsJsonResumeAdapter()}
