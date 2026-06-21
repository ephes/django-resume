import json

from django import forms

from .base import SimplePlugin
from ..interchange.protocols import AdapterExport


class SkillsForm(forms.Form):
    initial_badges = ["Some Skill", "Another Skill"]
    badges = forms.JSONField(
        label="Skills", max_length=1024, required=False, initial=initial_badges
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


class SkillsJsonResumeAdapter:
    owned_paths = ("/skills",)
    multivalued_paths: tuple[str, ...] = ()

    def export(self, facts: dict) -> AdapterExport:
        skills = [{"name": name} for name in facts.get("skills", []) if name]
        contributions = [("/skills", skills)] if skills else []
        return AdapterExport(contributions=contributions)


class SkillsPlugin(SimplePlugin):
    name: str = "skills"
    verbose_name: str = "Skills"
    capabilities: tuple[str, ...] = ("skills", "portfolio", "cv")
    admin_form_class = inline_form_class = SkillsForm
    prompt = """
        Create a django-resume plugin to display a list of skills as badges on a webpage. The plugin
        should allow users to view their skills in a structured format and edit them through an
        intuitive interface. Skills are represented as individual badges that can be added or
        removed, with changes taking effect only after submitting the form.
        
        The plugin should display the section title “Skills” followed by a list of badges. Each
        skill should be shown as a separate list item. When editing, a badge editor interface
        should allow users to manage their skills dynamically. The badge list should update in
        real-time within the form but persist only upon submission.
        
        The editing interface should provide a smooth user experience, allowing users to add new
        skills or remove existing ones efficiently. The updated skill set should be stored in
        JSON format and submitted securely via the form.
        
        This plugin ensures a user-friendly way to manage and present professional skills,
        keeping content editable while maintaining data integrity.
    """

    def get_structured_data(self, resume) -> dict:
        data = self.get_data(resume)
        badges = data.get("badges") or []
        if isinstance(badges, str):
            try:
                badges = json.loads(badges)
            except (ValueError, TypeError):
                badges = []
        if not isinstance(badges, list):
            badges = []
        return {"skills": list(badges)}

    def get_export_adapters(self) -> dict:
        return {"json_resume": SkillsJsonResumeAdapter()}
