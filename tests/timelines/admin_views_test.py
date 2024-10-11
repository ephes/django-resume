import json
import re

import pytest

from django_resume.models import Resume
from django_resume.plugins import EmployedTimelinePlugin


# admin views of the base list plugin


@pytest.mark.django_db
def test_get_add_form(admin_client, resume):
    # Given a resume in the database and a timeline plugin and an authenticated staff user
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    admin_client.force_login(resume.owner)
    plugin = EmployedTimelinePlugin()
    add_form_url = plugin.admin.get_item_add_form_url(resume.id)

    # When we get the item add form
    r = admin_client.get(add_form_url)

    # Then the response should be successful
    assert r.status_code == 200

    # And the form should be in the context and have the correct post url for the resume
    form = r.context["form"]
    assert f"/resume/{resume.pk}/" in form.post_url
    assert form.initial.get("position") == 0


# Test item crud views


@pytest.mark.django_db
def test_create_item(admin_client, resume, timeline_item_data):
    # Given a resume in the database and a timeline plugin and an authenticated staff user
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    admin_client.force_login(resume.owner)
    plugin = EmployedTimelinePlugin()
    post_url = plugin.admin.get_change_item_post_url(resume.id)

    # When we create a new timeline item
    r = admin_client.post(post_url, timeline_item_data)

    # Then the response should be successful
    assert r.status_code == 200

    # And the item should be in the database
    resume.refresh_from_db()
    plugin_data = plugin.data.get_data(resume)
    assert len(plugin_data["items"]) == 1

    [item] = plugin_data["items"]
    # And the item should have an id
    assert len(item["id"]) > 0

    # And the item should have the correct data
    assert item["role"] == timeline_item_data["role"]
    badges_list = json.loads(timeline_item_data["badges"])
    assert item["badges"] == badges_list


@pytest.mark.django_db
def test_update_item(admin_client, resume_with_timeline_item, timeline_item_data):
    # Given a resume in the database with a timeline item
    resume: Resume = resume_with_timeline_item
    admin_client.force_login(resume.owner)
    plugin = EmployedTimelinePlugin()

    plugin_data = plugin.data.get_data(resume)
    [item] = plugin_data["items"]
    timeline_item_data["id"] = item["id"]
    timeline_item_data["role"] = "Updated Developer"
    update_url = plugin.admin.get_change_item_post_url(resume.id)

    # When we update the timeline item
    r = admin_client.post(update_url, timeline_item_data)

    # Then the response should be successful
    assert r.status_code == 200

    # And the item should be updated in the database
    resume.refresh_from_db()
    plugin_data = plugin.data.get_data(resume)
    [item] = plugin_data["items"]
    assert item["role"] == timeline_item_data["role"]


@pytest.mark.django_db
def test_delete_item(admin_client, resume_with_timeline_item):
    # Given a resume in the database with a timeline item
    resume: Resume = resume_with_timeline_item
    admin_client.force_login(resume.owner)
    plugin = EmployedTimelinePlugin()

    # When we delete the timeline item
    delete_url = plugin.admin.get_delete_item_url(resume.id, "123")
    r = admin_client.post(delete_url)

    # Then the response should be successful
    assert r.status_code == 200  # yes, 200 not 204 - htmx won't work with 204

    # And the item should be removed from the database
    resume.refresh_from_db()
    plugin_data = plugin.data.get_data(resume)
    assert len(plugin_data["items"]) == 0


# Test flat form data


@pytest.mark.django_db
def test_update_flat_view(admin_client, resume):
    # Given a resume in the database and a timeline plugin and an authenticated staff user
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    admin_client.force_login(resume.owner)
    plugin = EmployedTimelinePlugin()
    post_url = plugin.admin.get_change_flat_post_url(resume.id)

    # When we update the flat form
    r = admin_client.post(post_url, {"title": "Updated title"})

    # Then the response should be successful
    assert r.status_code == 200

    # And the data should be in the database
    resume.refresh_from_db()
    plugin_data = plugin.data.get_data(resume)
    assert plugin_data["flat"]["title"] == "Updated title"


# Test main admin change view integration test


@pytest.mark.django_db
def test_add_and_update_via_main_change_view(admin_client, resume, timeline_item_data):
    """
    There was an issue that when an item was added the id was missing in the update
    form that came back as a response to the add post. When the update form was
    submitted, a second new item was created instead of updating the existing one.

    This test is to ensure that this won't happen again.
    """
    # Given a resume in the database and a timeline plugin and an authenticated staff user
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    admin_client.force_login(resume.owner)
    plugin = EmployedTimelinePlugin()
    change_view_url = plugin.admin.get_change_url(resume.id)
    # When we get the change view
    r = admin_client.get(change_view_url)

    # Then the response should be successful
    assert r.status_code == 200

    # And there should be an add item button with a hx-get attribute in the response content
    content = r.content.decode("utf-8")
    if match := re.search(r'<button.*?hx-get="(.*?)".*?>', content):
        add_form_url = match.group(1)
    else:
        raise AssertionError("Could not find the add form url")

    # When we get the add form and post a new item
    r = admin_client.get(add_form_url)
    assert r.status_code == 200

    post_new_item_here_url = r.context["form"].post_url
    r = admin_client.post(post_new_item_here_url, timeline_item_data)
    assert r.status_code == 200

    # Then the item should be in the database and have an id
    resume.refresh_from_db()
    [item] = plugin.data.get_data(resume)["items"]
    assert item["role"] == timeline_item_data["role"]
    expected_item_id = item["id"]

    # And there should be an update form in the response having an id field with the correct value
    content = r.content.decode("utf-8")
    if match := re.search(r'<input.*?name="id".*?value="(.*?)".*?>', content):
        item_id_from_form = match.group(1)
        print("item_id_from_form: ", item_id_from_form)
    else:
        raise AssertionError("Could not find the id field in the update form")

    assert item_id_from_form == expected_item_id
