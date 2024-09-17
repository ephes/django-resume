import pytest

from django_resume.models import Person
from django_resume.timelines import TimelinePlugin, TimelineItemForm


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
    post_url = plugin.get_admin_change_item_post_url(person.id)

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
    assert item["role"] == timeline_item_data["role"]
    badges_list = [badge.strip() for badge in timeline_item_data["badges"].split(",")]
    assert item["badges"] == badges_list


@pytest.fixture
def person_with_timeline_item(timeline_item_data):
    person: Person = Person(name="John Doe", slug="john-doe")
    timeline_item_data["id"] = "123"
    plugin = TimelinePlugin()
    form = TimelineItemForm(data=timeline_item_data, person=person)
    assert form.is_valid()
    person = plugin.create(person, form.cleaned_data)
    person.save()
    return person


@pytest.mark.django_db
def test_timeline_plugin_update_item(
    admin_client, person_with_timeline_item, timeline_item_data
):
    # Given a person in the database with a timeline item
    person: Person = person_with_timeline_item
    plugin = TimelinePlugin()

    plugin_data = plugin.get_data(person)
    [item] = plugin_data["items"]
    timeline_item_data["id"] = item["id"]
    timeline_item_data["role"] = "Updated Developer"
    update_url = plugin.get_admin_change_item_post_url(person.id)

    # When we update the timeline item
    r = admin_client.post(update_url, timeline_item_data)

    # Then the response should be successful
    assert r.status_code == 200

    # And the item should be updated in the database
    person.refresh_from_db()
    plugin_data = plugin.get_data(person)
    [item] = plugin_data["items"]
    assert item["role"] == timeline_item_data["role"]


@pytest.mark.django_db
def test_timeline_plugin_delete_item(admin_client, person_with_timeline_item):
    # Given a person in the database with a timeline item
    person: Person = person_with_timeline_item
    plugin = TimelinePlugin()

    # When we delete the timeline item
    delete_url = plugin.get_admin_delete_item_url(person.id, "123")
    r = admin_client.post(delete_url)

    # Then the response should be successful
    assert r.status_code == 200  # yes, 200 not 204 - htmx won't work with 204

    # And the item should be removed from the database
    person.refresh_from_db()
    plugin_data = plugin.get_data(person)
    assert len(plugin_data["items"]) == 0
