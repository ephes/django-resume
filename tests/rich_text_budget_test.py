import pytest
from django.urls import reverse

from django_resume.markdown import (
    MAX_EDITOR_INPUT_CHARS,
    MAX_MARKDOWN_CHARS,
    markdown_to_textarea_input,
)
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
        "token": {"flat": {"token_required": False}},
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


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["admin", "inline"])
@pytest.mark.parametrize("over_transport", [False, True])
def test_legacy_description_can_be_recovered(
    client, resume, description_editor, surface, over_transport
):
    plugin, item = description_editor
    size = (
        MAX_EDITOR_INPUT_CHARS // len("&amp;") if over_transport else MAX_MARKDOWN_CHARS
    )
    original = "synthetic legacy source\r\n<script>" + "&" * size
    item["description"] = original
    resume.save()

    cv_url = reverse("resume:cv", kwargs={"slug": resume.slug})
    response = client.get(cv_url)
    assert response.status_code == 200
    assert b"Description exceeds the Markdown display limit." in response.content
    assert b"synthetic legacy source" not in response.content

    client.force_login(resume.owner)
    response = client.get(cv_url, {"edit": "true"})
    assert response.status_code == 200
    assert b"Description exceeds the Markdown display limit." in response.content
    if surface == "admin":
        get_url = plugin.admin.get_change_url(resume.pk)
        post_url = plugin.admin.get_change_item_post_url(resume.pk)
    else:
        get_url = plugin.inline.get_edit_item_url(resume.pk, item["id"])
        post_url = plugin.inline.get_post_item_url(resume.pk)

    response = client.get(get_url)
    assert response.status_code == 200
    assert b"private JSON Resume export" in response.content
    assert b"synthetic legacy source" not in response.content
    if surface == "admin":
        form = response.context["item_forms"][0]
    else:
        form = response.context["form"]
    assert form["description"].value() == ""

    export = client.get(reverse("resume:json-resume", kwargs={"slug": resume.slug}))
    assert export.status_code == 200
    assert (
        export.json()["meta"]["django_resume"]["plugin_data"][plugin.name]["items"][0][
            "description"
        ]
        == original
    )

    label = "title" if plugin.name == "projects" else "role"
    data = {**item, label: "Edited label", "badges": "[]"}
    response = client.post(
        post_url,
        {
            **data,
            "description": form["description"].value(),
            "edit_revision": form["edit_revision"].value(),
        },
    )
    assert response.status_code == 200
    resume.refresh_from_db()
    saved = plugin.get_data(resume)["items"][0]
    assert saved[label] == "Edited label"
    assert saved["description"] == original
    if surface == "inline":
        assert b"Description exceeds the Markdown display limit." in response.content

    for blank in ("<br>", " <div><br></div> ", "&nbsp;"):
        response = post_current_editor(
            client, post_url, {**data, label: f"Blank {blank!r}", "description": blank}
        )
        assert response.status_code == 200
        assert b"This field is required." not in response.content
        resume.refresh_from_db()
        saved = plugin.get_data(resume)["items"][0]
        assert saved[label] == f"Blank {blank!r}"
        assert saved["description"] == original

    refused = post_current_editor(
        client, post_url, {**data, "description": "x" * (MAX_MARKDOWN_CHARS + 1)}
    )
    assert refused.status_code == 200
    assert b"262144 characters" in refused.content
    resume.refresh_from_db()
    assert plugin.get_data(resume)["items"][0]["description"] == original

    replacement = "Shorter <em>&</em> description"
    response = post_current_editor(
        client,
        post_url,
        {**data, "description": markdown_to_textarea_input(replacement)},
    )
    assert response.status_code == 200
    assert b"private JSON Resume export" not in response.content
    resume.refresh_from_db()
    assert plugin.get_data(resume)["items"][0]["description"] == replacement
    response = client.get(cv_url)
    assert b"Shorter" in response.content
    assert b"Description exceeds the Markdown display limit." not in response.content
