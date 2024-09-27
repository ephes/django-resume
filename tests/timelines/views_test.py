import pytest

from django_resume.models import Person
from django_resume.plugins import EmployedTimelinePlugin


# inline edit view tests
# integration test for editing the title


@pytest.mark.django_db
def test_edit_timeline_title(client, person):
    # Given a person in the database and a timeline plugin
    person.save()
    plugin = EmployedTimelinePlugin()

    # When we get the title edit view
    title_edit_url = plugin.inline.get_edit_flat_url(person.pk)
    r = client.get(title_edit_url)

    # Then the response should be successful and contain the title form
    assert r.status_code == 200
    assert "form" in r.context

    # When we post a title that is too long using the edit form
    title_edit_post_url = r.context["edit_flat_post_url"]
    r = client.post(title_edit_post_url, {"title": "x" * 51})

    # Then the response should be successful and contain the title form with an error
    assert r.status_code == 200
    [error_message] = r.context["form"].errors["title"]
    assert "Ensure this value has at most 50 characters" in error_message

    # When we post a valid title using the edit form
    title_edit_post_url = r.context["edit_flat_post_url"]
    r = client.post(title_edit_post_url, {"title": "Updated title"})

    # Then the response should be successful and contain the updated title
    assert r.status_code == 200
    content = r.content.decode("utf-8")
    assert "Updated title" in content

    # And the edit button should be still visible and the edit and delete url should be in the context
    assert '<use href="#edit"></use>' in content
    assert r.context["timeline"]["edit_flat_url"] == title_edit_url

    # And the title should be updated in the database
    person.refresh_from_db()
    plugin_data = plugin.data.get_data(person)
    assert plugin_data["flat"]["title"] == "Updated title"


# item edit view tests


@pytest.mark.django_db
def test_get_add_item_form(client, person):
    # Given a person in the database and a timeline plugin
    person.save()
    plugin = EmployedTimelinePlugin()

    # When we get the add item form
    add_item_url = plugin.inline.get_edit_item_url(person.pk)
    r = client.get(add_item_url)

    # Then the response should be successful and contain the item form but no item_id
    assert r.status_code == 200
    assert "form" in r.context
    assert r.context["form"].fields["id"].initial is None


@pytest.mark.django_db
def test_get_update_item_form(client, person_with_timeline_item):
    # Given a person in the database and a timeline plugin with an item
    person: Person = person_with_timeline_item
    plugin = EmployedTimelinePlugin()
    plugin_data = plugin.data.get_data(person)
    [item] = plugin_data["items"]

    # When we get the update item form
    update_item_url = plugin.inline.get_edit_item_url(person.pk, item["id"])
    r = client.get(update_item_url)

    # Then the response should be successful and contain the item form with the right item_id
    assert r.status_code == 200
    assert r.context["form"].initial["id"] == item["id"]


@pytest.mark.django_db
def test_create_item(client, person, timeline_item_data):
    # Given a person in the database and a timeline plugin
    person.save()
    plugin = EmployedTimelinePlugin()

    # When we post a new item
    add_item_url = plugin.inline.get_post_item_url(person.pk)
    r = client.post(add_item_url, timeline_item_data)

    # Then the response should be successful and the item should be added to the database
    assert r.status_code == 200
    person.refresh_from_db()
    [item] = plugin.data.get_data(person)["items"]
    assert item["company_name"] == timeline_item_data["company_name"]

    # And the delete and edit urls should be in the context
    assert r.context["entry"]["delete_url"] == plugin.inline.get_delete_item_url(
        person.pk, item["id"]
    )
    assert r.context["entry"]["edit_url"] == plugin.inline.get_edit_item_url(
        person.pk, item["id"]
    )


@pytest.mark.django_db
def test_update_item(client, person_with_timeline_item, timeline_item_data):
    # Given a person in the database and a timeline plugin with an item
    person: Person = person_with_timeline_item
    plugin = EmployedTimelinePlugin()
    plugin_data = plugin.data.get_data(person)
    [item] = plugin_data["items"]

    # When we post an updated item
    update_item_url = plugin.inline.get_post_item_url(person.pk)
    timeline_item_data["company_name"] = "Updated company name"
    r = client.post(update_item_url, timeline_item_data)

    # Then the response should be successful and the item should be updated in the database
    assert r.status_code == 200
    person.refresh_from_db()
    [updated_item] = plugin.data.get_data(person)["items"]
    assert updated_item["company_name"] == timeline_item_data["company_name"]

    # And the delete and edit urls should be in the context
    assert r.context["entry"]["delete_url"] == plugin.inline.get_delete_item_url(
        person.pk, item["id"]
    )
    assert r.context["entry"]["edit_url"] == plugin.inline.get_edit_item_url(
        person.pk, item["id"]
    )


@pytest.mark.django_db
def test_delete_item(client, person_with_timeline_item):
    # Given a person in the database and a timeline plugin with an item
    person: Person = person_with_timeline_item
    plugin = EmployedTimelinePlugin()
    plugin_data = plugin.data.get_data(person)
    [item] = plugin_data["items"]

    # When we post a delete request for the item
    delete_item_url = plugin.inline.get_delete_item_url(person.pk, item["id"])
    r = client.post(delete_item_url)

    # Then the response should be successful and the item should be deleted from the database
    assert r.status_code == 200
    person.refresh_from_db()
    assert plugin.data.get_data(person)["items"] == []
