import re

import pytest

from django_resume.timelines import EmployedTimelinePlugin


# inline edit view tests
# integration test for editing the title


@pytest.mark.django_db
def test_edit_timeline_title(client, person):
    # Given a person in the database and a timeline plugin
    person.save()
    plugin = EmployedTimelinePlugin()

    # When we get the title edit view
    title_edit_url = plugin.get_edit_flat_url(person.pk)
    r = client.get(title_edit_url)

    # Then the response should be successful and contain the title form
    assert r.status_code == 200
    assert "form" in r.context

    # When we post a title that is too long using the edit form
    title_edit_post_url = r.context["timeline"].edit_flat_post_url
    r = client.post(title_edit_post_url, {"title": "x" * 51})

    # Then the response should be successful and contain the title form with an error
    assert r.status_code == 200
    [error_message] = r.context["form"].errors["title"]
    assert "Ensure this value has at most 50 characters" in error_message

    # When we post a valid title using the edit form
    title_edit_post_url = r.context["timeline"]["edit_flat_post_url"]
    r = client.post(title_edit_post_url, {"title": "Updated title"})

    # Then the response should be successful and contain the updated title
    assert r.status_code == 200
    content = r.content.decode("utf-8")
    print("content: ", content)
    assert "Updated title" in content

    # And the edit button should be still visible and the edit url should be in the context
    assert re.search(r"<button[^>]*>Edit</button>", content) is not None
    assert r.context["timeline"]["edit_flat_url"] == title_edit_url

    # And the title should be updated in the database
    person.refresh_from_db()
    plugin_data = plugin.get_data(person)
    assert plugin_data["flat"]["title"] == "Updated title"
