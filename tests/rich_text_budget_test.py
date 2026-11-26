import pytest

from django_resume.markdown import MAX_MARKDOWN_CHARS, markdown_to_textarea_input
from django_resume.plugins import plugin_registry
from tests.editor_helpers import post_current_editor


@pytest.fixture(params=["projects", "employed_timeline", "freelance_timeline"])
def description_editor(request, resume):
    plugin_name = request.param
    plugin = plugin_registry.get_plugin(plugin_name)
    item = {
        **plugin.get_form_classes()["item"].get_initial(),
        "id": "synthetic-item",
        "description": "Original description",
        "position": 0,
    }
    resume.plugin_data = {
        plugin_name: {"flat": {"title": "Synthetic section"}, "items": [item]},
        "tokens": {"flat": {"token_required": False}},
    }
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    return plugin, item


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["admin", "inline"])
def test_description_posts_respect_decoded_markdown_budget(
    client, resume, description_editor, surface
):
    plugin, item = description_editor
    client.force_login(resume.owner)
    url = (
        plugin.admin.get_change_item_post_url(resume.pk)
        if surface == "admin"
        else plugin.inline.get_post_item_url(resume.pk)
    )
    markup = "<em>&</em>"
    boundary = "x" * (MAX_MARKDOWN_CHARS - len(markup)) + markup

    def post(text):
        return post_current_editor(
            client,
            url,
            {**item, "description": markdown_to_textarea_input(text), "badges": "[]"},
        )

    response = post(boundary + "é")
    assert response.status_code == 200
    assert b"262144 characters" in response.content
    resume.refresh_from_db()
    assert plugin.get_data(resume)["items"][0]["description"] == "Original description"

    assert post(boundary).status_code == 200
    resume.refresh_from_db()
    assert plugin.get_data(resume)["items"][0]["description"] == boundary
