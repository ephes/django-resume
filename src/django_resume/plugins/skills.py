from django import forms

from .base import SimplePlugin
from .badges import (
    MAX_BADGES,
    MAX_BADGE_LENGTH,
    display_badges,
    editor_badges_json,
    validate_badges as validate_skill_badges,
)
from ..interchange.pointer import get_pointer
from ..interchange.protocols import AdapterExport, AdapterImport
from ..formats.json_resume.mapping import unimported_item_fields

SKILL_IMPORTED_KEYS = ("name", "level", "keywords")
MAX_SKILL_BADGES = MAX_BADGES
MAX_SKILL_BADGE_LENGTH = MAX_BADGE_LENGTH


class SkillsForm(forms.Form):
    initial_badges = ["Some Skill", "Another Skill"]
    badges = forms.JSONField(label="Skills", required=False, initial=initial_badges)

    def clean_badges(self) -> list[str]:
        badges = self.cleaned_data["badges"]
        if badges is None and not self.data.get(self.add_prefix("badges")):
            return []
        validate_skill_badges(badges)
        return badges

    def badges_as_json(self) -> str:
        return editor_badges_json(self)


class SkillsJsonResumeAdapter:
    owned_paths = ("/skills",)
    multivalued_paths: tuple[str, ...] = ()

    def export(self, facts: dict) -> AdapterExport:
        skills = [{"name": name} for name in facts.get("skills", []) if name]
        contributions = [("/skills", skills)] if skills else []
        return AdapterExport(contributions=contributions)

    source_paths = ("/skills",)

    def import_data(self, document: dict) -> AdapterImport:
        skills = get_pointer(document, "/skills", []) or []
        notes = []
        candidates: list[tuple[str, str]] = []
        for item in skills:
            if not isinstance(item, dict):
                continue
            name = item.get("name") or "(unnamed skill)"
            if item.get("level"):
                notes.append(f"skills entry {name!r} level is not imported")
            notes.extend(
                unimported_item_fields(
                    f"skills entry {name!r}", item, SKILL_IMPORTED_KEYS
                )
            )
            keywords = item.get("keywords")
            if isinstance(keywords, list):
                imported_keywords = [
                    keyword
                    for keyword in keywords
                    if isinstance(keyword, str) and keyword.strip()
                ]
                if any(
                    isinstance(keyword, str) and not keyword.strip()
                    for keyword in keywords
                ):
                    notes.append(
                        f"skills entry {name!r} blank keywords are not imported"
                    )
                if imported_keywords:
                    candidates.extend((keyword, name) for keyword in imported_keywords)
                    notes.append(f"skills entry {name!r} category name is not imported")
                    continue
            if isinstance(item.get("name"), str) and item["name"]:
                candidates.append((item["name"], name))
        badges = _dedupe_badges(candidates, notes)
        return AdapterImport(
            plugin_data={"badges": badges} if badges else {},
            notes=notes,
        )


def _dedupe_badges(candidates: list[tuple[str, str]], notes: list[str]) -> list[str]:
    """Keep the first spelling of each badge in document order.

    Badges compare case-insensitively after trimming whitespace, so a keyword
    repeated across skill categories becomes one badge. Each skipped repeat
    is reported with the entry it came from.
    """
    badges: list[str] = []
    seen: set[str] = set()
    for badge, source in candidates:
        key = badge.strip().casefold()
        if key in seen:
            notes.append(
                f"skills entry {source!r} keyword {badge!r} duplicates an "
                "earlier skill badge; imported once"
            )
            continue
        seen.add(key)
        badges.append(badge)
    return badges


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
        return {"skills": display_badges(data.get("badges"))}

    def get_context(self, *args, **kwargs) -> dict:
        context = super().get_context(*args, **kwargs)
        context["badges"] = display_badges(context.get("badges"))
        return context

    def get_export_adapters(self) -> dict:
        return {"json_resume": SkillsJsonResumeAdapter()}

    def get_import_adapters(self) -> dict:
        return {"json_resume": SkillsJsonResumeAdapter()}
