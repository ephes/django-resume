from django import forms

from .base import SimplePlugin, SimpleTemplates


class SkillsForm(forms.Form):
    initial_badges = ["Some Skill", "Another Skill"]
    badges = forms.CharField(
        label="Skills", max_length=1024, required=False, initial=initial_badges
    )

    def badges_as_text(self):
        """
        Return the initial badges which should already be a comma seperated string
        or the initial_badged list joined by commas for the first render of the form.
        """
        existing_badges = self.initial.get("badges")
        if existing_badges is not None:
            return ",".join(existing_badges)
        return ",".join(self.initial_badges)

    def clean_badges(self):
        badges = self.cleaned_data.get("badges", "")
        # Split the comma-separated values and strip any extra spaces
        badge_list = [badge.strip() for badge in badges.split(",")]
        return badge_list


class SkillsPlugin(SimplePlugin):
    name: str = "skills"
    verbose_name: str = "Skills"
    templates = SimpleTemplates(
        main="django_resume/skills/plain/content.html",
        form="django_resume/skills/plain/form.html",
    )
    admin_form_class = inline_form_class = SkillsForm
