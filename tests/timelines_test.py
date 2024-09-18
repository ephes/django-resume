from django_resume.timelines import TimelinePlugin, TimelineItemForm


def test_timeline_plugin():
    plugin = TimelinePlugin()
    assert plugin.name == "employed_timeline"


def test_timeline_item_form_position_invalid(person):
    form = TimelineItemForm({"position": "invalid"}, person=person)
    assert not form.is_valid()
    assert "position" in form.errors
