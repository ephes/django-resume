from django_resume.timelines import TimelinePlugin


def test_timeline_plugin():
    plugin = TimelinePlugin()
    assert plugin.name == "employed_timeline"
