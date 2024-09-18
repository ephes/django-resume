from django import forms
from .plugins import ListPlugin, ListItemFormMixin


class TimelineItemForm(ListItemFormMixin, forms.Form):
    role = forms.CharField(widget=forms.TextInput())
    company_url = forms.URLField(
        widget=forms.URLInput(), required=False, assume_scheme="https"
    )
    company_name = forms.CharField(widget=forms.TextInput())
    description = forms.CharField(widget=forms.Textarea())
    start = forms.CharField(widget=forms.TextInput(), required=False)
    end = forms.CharField(widget=forms.TextInput(), required=False)
    badges = forms.CharField(widget=forms.TextInput(), required=False)
    position = forms.IntegerField(widget=forms.NumberInput(), required=False)

    def __init__(self, *args, **kwargs):
        self.existing_items = kwargs.pop("existing_items", [])
        super().__init__(*args, **kwargs)
        self.set_initial_badges()

    def set_initial_badges(self):
        """Transform the list of badges into a comma-separated string."""
        if "badges" in self.initial and isinstance(self.initial["badges"], list):
            self.initial["badges"] = ",".join(self.initial["badges"])

    @staticmethod
    def get_initial(items):
        positions = [item.get("position", 0) for item in items]
        max_position = max(positions) if positions else -1
        return {"position": max_position + 1}

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


class TimelineFlatForm(forms.Form):
    title = forms.CharField(widget=forms.TextInput())

    def clean_title(self):
        title = self.cleaned_data["title"]
        if title == "Senor Developer":
            print("No Senor! Validation Error!")
            raise forms.ValidationError("No Senor!")
        return title


class TimelineForContext:
    def __init__(self, title, ordered_entries):
        self.title = title
        self.ordered_entries = ordered_entries


class TimelinePlugin(ListPlugin):
    name = "employed_timeline"
    verbose_name = "Employed Timeline"

    def get_admin_item_form(self):
        return TimelineItemForm

    def get_admin_flat_form(self):
        return TimelineFlatForm

    def get_data_for_context(self, person):
        timeline_data = self.get_data(person)
        timeline = TimelineForContext(
            title=timeline_data.get("flat", {}).get("title", self.verbose_name),
            ordered_entries=timeline_data.get("items", []),
        )
        return timeline
