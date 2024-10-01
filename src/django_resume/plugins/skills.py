import json

from django import forms

from .base import SimplePlugin, SimpleTemplates


class SkillsForm(forms.Form):
    initial_badges = ["Some Skill", "Another Skill"]
    badges = forms.JSONField(
        label="Skills", max_length=1024, required=False, initial=initial_badges
    )

    def badges_as_json(self):
        """
        Return the initial badges which should already be a normal list of strings
        or the initial_badged list for the first render of the form encoded as json.
        """
        existing_badges = self.initial.get("badges")
        if existing_badges is not None:
            return json.dumps(existing_badges)
        return json.dumps(self.initial_badges)


class SkillsPlugin(SimplePlugin):
    name: str = "skills"
    verbose_name: str = "Skills"
    templates = SimpleTemplates(
        main="django_resume/skills/plain/content.html",
        form="django_resume/skills/plain/form.html",
    )
    admin_form_class = inline_form_class = SkillsForm
