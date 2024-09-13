import json

from django import forms

from .plugins import BasePlugin


class TimelineForm(forms.Form):
    title = forms.CharField(widget=forms.TextInput())
    description = forms.CharField(widget=forms.Textarea())
    start = forms.CharField(widget=forms.TextInput(), required=False)
    end = forms.CharField(widget=forms.TextInput(), required=False)

    def __init__(self, *args, **kwargs):
        initial = kwargs.get("initial", {})
        if "timeline_items" in initial and isinstance(initial["timeline_items"], list):
            initial["timeline_items"] = json.dumps(initial["timeline_items"])
        super().__init__(*args, **kwargs)

    def clean_timeline_items(self):
        items = self.cleaned_data.get("timeline_items")
        if not items:
            return []
        try:
            return json.loads(items)
        except json.JSONDecodeError:
            raise forms.ValidationError("Invalid JSON data for timeline items")


class TimelinePlugin(BasePlugin):
    name = "employed_timeline"
    verbose_name = "Employed Timeline"
    change_form_template = "resume/admin/timeline_admin_change_form_htmx.html"

    def get_admin_form(self):
        return TimelineForm

    def get_data(self, person):
        return person.plugin_data.get(self.name, [])

    def set_data(self, person, data):
        if not person.plugin_data:
            person.plugin_data = {}
        person.plugin_data[self.name] = data
        person.save()
