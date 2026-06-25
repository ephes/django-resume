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
    textarea_input_to_html,
    markdown_to_textarea_input,
    underlined_link_handler,
)
from ..interchange.pointer import get_pointer
from ..interchange.protocols import AdapterExport, AdapterImport
from ..formats.json_resume.dates import is_valid_resume_date


def _work_description(summary: object, highlights: object) -> str:
    parts = []
    if isinstance(summary, str) and summary:
        parts.append(summary)
    if isinstance(highlights, list):
        bullet_lines = [
            "- " + highlight.replace("\n", " ")
            for highlight in highlights
            if isinstance(highlight, str) and highlight
        ]
        if bullet_lines:
            parts.append("\n".join(bullet_lines))
    return "\n\n".join(parts)


class TimelineJsonResumeAdapter:
    owned_paths = ("/work",)
    multivalued_paths = ("/work",)

    def export(self, facts: dict) -> AdapterExport:
        work: list[dict] = []
        notes: list[str] = []
        for item in facts.get("work", []):
            entry: dict[str, object] = {}
            if item.get("company_name"):
                entry["name"] = item["company_name"]
            if item.get("company_url"):
                entry["url"] = item["company_url"]
            if item.get("role"):
                entry["position"] = item["role"]
            if item.get("description"):
                entry["summary"] = item["description"]
            highlights = [badge for badge in item.get("badges", []) if badge]
            if highlights:
                entry["highlights"] = highlights
            for json_key, fact_key, label in (
                ("startDate", "start", "start date"),
                ("endDate", "end", "end date"),
            ):
                value = item.get(fact_key, "")
                if not value:
                    continue
                if is_valid_resume_date(value):
                    entry[json_key] = value
                else:
                    company = item.get("company_name", "?")
                    notes.append(
                        f"work item {company!r} {label} {value!r} is not a valid "
                        "date; not exported"
                    )
            if entry:
                work.append(entry)
        contributions = [("/work", work)] if work else []
        return AdapterExport(contributions=contributions, notes=notes)

    source_paths = ("/work",)

    def import_data(self, document: dict) -> AdapterImport:
        work = get_pointer(document, "/work", []) or []
        items = []
        for position, entry in enumerate(
            item for item in work if isinstance(item, dict)
        ):
            items.append(
                {
                    "id": f"json-resume-work-{position + 1}",
                    "company_name": entry.get("name", ""),
                    "company_url": entry.get("url", ""),
                    "role": entry.get("position", ""),
                    "description": _work_description(
                        entry.get("summary", ""),
                        entry.get("highlights", []),
                    ),
                    "start": entry.get("startDate", ""),
                    "end": entry.get("endDate", ""),
                    "badges": [],
                    "position": position,
                }
            )
        if not items:
            return AdapterImport(plugin_data={})
        return AdapterImport(
            plugin_data={"flat": {"title": "Work Experience"}, "items": items},
            notes=[
                "JSON Resume /work imported into employed_timeline; portable "
                "JSON Resume cannot distinguish freelance and employed timelines"
            ],
        )


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
        self.description_display_html = textarea_input_to_html(
            self["description"].value() or ""
        )

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
                item["description"], handlers={"link": underlined_link_handler}
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
                item["description"], handlers={"link": underlined_link_handler}
            )
        return context

    def get_structured_data(self, resume) -> dict:
        list_plugin = cast(ListPlugin, self)
        data = list_plugin.get_data(resume)
        work: list[dict] = []
        for item in data.get("items", []):
            badges = item.get("badges") or []
            if isinstance(badges, str):
                try:
                    badges = json.loads(badges)
                except (ValueError, TypeError):
                    badges = []
            if not isinstance(badges, list):
                badges = []
            work.append(
                {
                    "company_name": item.get("company_name", ""),
                    "company_url": item.get("company_url", ""),
                    "role": item.get("role", ""),
                    "description": item.get("description", ""),
                    "start": item.get("start", ""),
                    "end": item.get("end", ""),
                    "badges": badges,
                    "position": item.get("position", 0),
                }
            )
        work.sort(key=lambda entry: entry["position"])
        return {"work": work}

    def get_export_adapters(self) -> dict:
        return {"json_resume": TimelineJsonResumeAdapter()}


class FreelanceTimelinePlugin(TimelineMixin, ListPlugin):
    name = "freelance_timeline"
    verbose_name = "Freelance Timeline"
    capabilities: tuple[str, ...] = ("experience", "cv")

    def get_import_adapters(self) -> dict:
        return {}


class EmployedTimelinePlugin(TimelineMixin, ListPlugin):
    name = "employed_timeline"
    verbose_name = "Employed Timeline"
    capabilities: tuple[str, ...] = ("experience", "cv")

    def get_import_adapters(self) -> dict:
        return {"json_resume": TimelineJsonResumeAdapter()}
