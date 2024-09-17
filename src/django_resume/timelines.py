from django import forms
from .plugins import ListPlugin, ListFormMixin


class TimelineForm(ListFormMixin, forms.Form):
    role = forms.CharField(widget=forms.TextInput())
    company_url = forms.URLField(widget=forms.URLInput(), required=False)
    company_name = forms.CharField(widget=forms.TextInput())
    description = forms.CharField(widget=forms.Textarea())
    start = forms.CharField(widget=forms.TextInput(), required=False)
    end = forms.CharField(widget=forms.TextInput(), required=False)
    badges = forms.CharField(widget=forms.TextInput(), required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "badges" in self.initial and isinstance(self.initial["badges"], list):
            self.initial["badges"] = ",".join(self.initial["badges"])

    def clean_title(self):
        title = self.cleaned_data["title"]
        if title == "Senor Developer":
            print("No Senor! Validation Error!")
            raise forms.ValidationError("No Senor!")
        return title

    def clean_badges(self):
        badges = self.cleaned_data.get("badges", "")
        # Split the comma-separated values and strip any extra spaces
        badge_list = [badge.strip() for badge in badges.split(",")]
        return badge_list


class TimelineForContext:
    def __init__(self, title, ordered_entries):
        self.title = title
        self.ordered_entries = ordered_entries


class TimelinePlugin(ListPlugin):
    name = "employed_timeline"
    verbose_name = "Employed Timeline"

    def get_admin_form(self):
        return TimelineForm

    def get_data_for_context(self, person):
        timeline_data = self.get_data(person)
        timeline = TimelineForContext(
            title=self.verbose_name,
            ordered_entries=timeline_data,
        )
        print("timeline_data: ", timeline_data)
        return timeline
