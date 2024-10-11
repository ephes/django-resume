import pytest

from django_resume.plugins import EmployedTimelinePlugin
from django_resume.plugins.timelines import TimelineItemForm


@pytest.fixture
def resume_with_timeline_item(resume, timeline_item_data):
    timeline_item_data["id"] = "123"
    plugin = EmployedTimelinePlugin()
    form = TimelineItemForm(data=timeline_item_data, resume=resume)
    assert form.is_valid()
    resume = plugin.data.create(resume, form.cleaned_data)
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    return resume
