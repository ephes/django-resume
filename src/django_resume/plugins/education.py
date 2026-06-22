from django import forms

from .base import SimplePlugin
from ..interchange.pointer import get_pointer
from ..interchange.protocols import AdapterExport, AdapterImport
from ..formats.json_resume.dates import is_valid_resume_date


class EducationForm(forms.Form):
    school_name = forms.CharField(
        label="School name", max_length=100, initial="School name"
    )
    school_url = forms.URLField(
        label="School url",
        max_length=100,
        initial="https://example.com",
        assume_scheme="https",
    )
    start = forms.CharField(widget=forms.TextInput(), required=False, initial="start")
    end = forms.CharField(widget=forms.TextInput(), required=False, initial="end")


class EducationJsonResumeAdapter:
    owned_paths = ("/education",)
    multivalued_paths: tuple[str, ...] = ()

    def export(self, facts: dict) -> AdapterExport:
        entry: dict[str, object] = {}
        notes: list[str] = []
        if facts.get("school_name"):
            entry["institution"] = facts["school_name"]
        if facts.get("school_url"):
            entry["url"] = facts["school_url"]
        for json_key, fact_key in (("startDate", "start"), ("endDate", "end")):
            value = facts.get(fact_key, "")
            if not value:
                continue
            if is_valid_resume_date(value):
                entry[json_key] = value
            else:
                notes.append(
                    f"education.{fact_key} {value!r} is not a valid date; not exported"
                )
        contributions = [("/education", [entry])] if entry else []
        return AdapterExport(contributions=contributions, notes=notes)

    source_paths = ("/education",)

    def import_data(self, document: dict) -> AdapterImport:
        education = get_pointer(document, "/education", []) or []
        if not education or not isinstance(education[0], dict):
            return AdapterImport(plugin_data={})
        entry = education[0]
        plugin_data = {
            "school_name": entry.get("institution", ""),
            "school_url": entry.get("url", ""),
            "start": entry.get("startDate", ""),
            "end": entry.get("endDate", ""),
        }
        notes = []
        if len(education) > 1:
            notes.append(
                "education entries beyond the first were not imported; "
                "the bundled education plugin stores one entry"
            )
        return AdapterImport(plugin_data=plugin_data, notes=notes)


class EducationPlugin(SimplePlugin):
    name: str = "education"
    verbose_name: str = "Education"
    capabilities: tuple[str, ...] = ("education", "cv")
    admin_form_class = inline_form_class = EducationForm
    prompt = """
        Create a django-resume plugin to display education-related information. The plugin should
        include fields for the school name, school URL, start date, and end date. The school name
        and URL are required, while the start and end dates are optional. The plugin should be
        named "education", with the verbose name set to "Education". The form’s data should be
        JSON serializable.
        
        When displayed, the plugin should show the title "Education", with the school name as
        a clickable link leading to the provided school URL, aligned to the left. The start and
        end dates should appear on the right, formatted as either `"YYYY"` or `"YYYY-MM"`.
        An edit button should be shown next to the section title when editing is enabled.
    """

    def get_structured_data(self, resume) -> dict:
        data = self.get_data(resume)
        return {
            "school_name": data.get("school_name", ""),
            "school_url": data.get("school_url", ""),
            "start": data.get("start", ""),
            "end": data.get("end", ""),
        }

    def get_export_adapters(self) -> dict:
        return {"json_resume": EducationJsonResumeAdapter()}

    def get_import_adapters(self) -> dict:
        return {"json_resume": EducationJsonResumeAdapter()}
