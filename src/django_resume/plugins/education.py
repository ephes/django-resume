from typing import Any, Type, cast

from django import forms

from .base import ListPlugin, ListItemFormMixin, ListInline, ListData, ContextDict
from ..interchange.pointer import get_pointer
from ..interchange.protocols import AdapterExport, AdapterImport
from ..formats.json_resume.mapping import unimported_item_fields
from ..formats.json_resume.dates import is_valid_resume_date
from ..models import Resume

EDUCATION_IMPORTED_KEYS = (
    "institution",
    "url",
    "area",
    "studyType",
    "startDate",
    "endDate",
)


LEGACY_EDUCATION_FIELDS = ("school_name", "school_url", "start", "end")


def normalize_education_data(data: dict) -> dict:
    """
    Convert the single-entry education data stored before education became a
    list plugin ({"school_name": ..., "start": ...}) into list plugin data.

    Data that already has the list shape is returned unchanged.
    """
    if not data or "items" in data or "flat" in data:
        return data
    if not any(data.get(field) for field in LEGACY_EDUCATION_FIELDS):
        return {}
    item = {field: data.get(field, "") for field in LEGACY_EDUCATION_FIELDS}
    item.update({"id": "education-1", "degree": "", "position": 0})
    return {"flat": {"title": "Education"}, "items": [item]}


class EducationData(ListData):
    """
    Read legacy single-entry education data as a one-item list.

    Reads do not write the normalized shape back, so stored plugin data stays
    unchanged until the plugin is edited (writes go through ``set_data``).
    """

    def get_data(self, resume: Resume) -> dict:
        return normalize_education_data(super().get_data(resume))


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
            "start": "start",
            "end": "end",
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


class EducationJsonResumeAdapter:
    owned_paths = ("/education",)
    multivalued_paths: tuple[str, ...] = ()

    def export(self, facts: dict) -> AdapterExport:
        education: list[dict] = []
        notes: list[str] = []
        for item in facts.get("education", []):
            entry: dict[str, object] = {}
            if item.get("school_name"):
                entry["institution"] = item["school_name"]
            if item.get("school_url"):
                entry["url"] = item["school_url"]
            if item.get("degree"):
                entry["studyType"] = item["degree"]
            for json_key, fact_key in (("startDate", "start"), ("endDate", "end")):
                value = item.get(fact_key, "")
                if not value:
                    continue
                if is_valid_resume_date(value):
                    entry[json_key] = value
                else:
                    school = item.get("school_name", "?")
                    notes.append(
                        f"education item {school!r} {fact_key} {value!r} is not a "
                        "valid date; not exported"
                    )
            if entry:
                education.append(entry)
        contributions = [("/education", education)] if education else []
        return AdapterExport(contributions=contributions, notes=notes)

    source_paths = ("/education",)

    def import_data(self, document: dict) -> AdapterImport:
        education = get_pointer(document, "/education", []) or []
        items = []
        notes = []
        for position, entry in enumerate(
            item for item in education if isinstance(item, dict)
        ):
            notes.extend(
                unimported_item_fields(
                    f"education entry {entry.get('institution') or '?'!r}",
                    entry,
                    EDUCATION_IMPORTED_KEYS,
                )
            )
            degree = entry.get("studyType", "")
            area = entry.get("area", "")
            if area:
                degree = f"{degree}, {area}" if degree else area
                notes.append(
                    f"education entry {entry.get('institution', '?')!r} area "
                    "was merged into the degree"
                )
            items.append(
                {
                    "id": f"json-resume-education-{position + 1}",
                    "school_name": entry.get("institution", ""),
                    "school_url": entry.get("url", ""),
                    "degree": degree,
                    "start": entry.get("startDate", ""),
                    "end": entry.get("endDate", ""),
                    "position": position,
                }
            )
        if not items:
            return AdapterImport(plugin_data={}, notes=notes)
        return AdapterImport(
            plugin_data={"flat": {"title": "Education"}, "items": items},
            notes=notes,
        )


class EducationPlugin(ListPlugin):
    name: str = "education"
    verbose_name: str = "Education"
    capabilities: tuple[str, ...] = ("education", "cv")
    data_class = EducationData
    inline: ListInline
    flat_form_class = EducationFlatForm
    sort_by_reverse_position: bool = False

    @staticmethod
    def get_form_classes() -> dict[str, Type[forms.Form]]:
        return {"item": EducationItemForm, "flat": EducationFlatForm}

    def get_structured_data(self, resume) -> dict:
        data = self.get_data(resume)
        items = self.items_ordered_by_position(data.get("items", []))
        return {
            "education": [
                {
                    "school_name": item.get("school_name", ""),
                    "school_url": item.get("school_url", ""),
                    "degree": item.get("degree", ""),
                    "start": item.get("start", ""),
                    "end": item.get("end", ""),
                }
                for item in items
            ]
        }

    def get_export_adapters(self) -> dict:
        return {"json_resume": EducationJsonResumeAdapter()}

    def get_import_adapters(self) -> dict:
        return {"json_resume": EducationJsonResumeAdapter()}
