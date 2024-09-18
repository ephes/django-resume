from django_resume.timelines import TimelinePlugin


def test_timeline_plugin():
    plugin = TimelinePlugin()
    assert plugin.name == "employed_timeline"


def test_timeline_items_ordered_by_position():
    plugin = TimelinePlugin()
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
