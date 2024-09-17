import pytest

from django_resume.models import Person
from django_resume.timelines import TimelinePlugin


# admin views of the base list plugin


@pytest.fixture
def person():
    person = Person(name="John Doe", slug="john-doe")
    person.save()
    return person


@pytest.fixture
def timeline_item_data():
    return {
        "role": "Software Developer",
        "company_name": "ACME Inc.",
        "company_url": "https://example.org",
        "description": "I did some stuff",
        "start": "2020",
        "end": "2022",
        "badges": "remote, full-time",
    }


@pytest.mark.django_db
def test_timeline_plugin_create_item(admin_client, person, timeline_item_data):
    # Given a person in the database and a timeline plugin
    plugin = TimelinePlugin()
    post_url = plugin.get_admin_change_post_url(person.id)

    # When we create a new timeline item
    r = admin_client.post(post_url, timeline_item_data)

    # Then the response should be successful
    assert r.status_code == 200

    # And the item should be in the database
    person.refresh_from_db()
    plugin_data = plugin.get_data(person)
    assert len(plugin_data["items"]) == 1

    [item] = plugin_data["items"]
    # And the item should have an id
    assert len(item["id"]) > 0

    # And the item should have the correct data
    assert timeline_item_data["role"] == item["role"]
