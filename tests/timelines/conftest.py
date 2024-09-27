import pytest

from django_resume.plugins import EmployedTimelinePlugin
from django_resume.plugins.timelines import TimelineItemForm


@pytest.fixture
def person_with_timeline_item(person, timeline_item_data):
    timeline_item_data["id"] = "123"
    plugin = EmployedTimelinePlugin()
    form = TimelineItemForm(data=timeline_item_data, person=person)
    assert form.is_valid()
    person = plugin.data.create(person, form.cleaned_data)
    person.save()
    return person
