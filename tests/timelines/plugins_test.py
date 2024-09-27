from django_resume.plugins import EmployedTimelinePlugin


def test_employed_timeline_plugin():
    plugin = EmployedTimelinePlugin()
    assert plugin.name == "employed_timeline"


def test_items_ordered_by_position():
    plugin = EmployedTimelinePlugin()
    items = [
        {"position": 1, "title": "B"},
        {"position": 0, "title": "A"},
        {"position": 2, "title": "C"},
    ]
    assert plugin.items_ordered_by_position(items) == [
        {"position": 0, "title": "A"},
        {"position": 1, "title": "B"},
        {"position": 2, "title": "C"},
    ]
