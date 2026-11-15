"""Stable add-operation identity and current-revision deletion."""

import pytest
from django import forms
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from django_resume.images import ImageFormMixin
from django_resume.plugins import plugin_registry
from django_resume.plugins.education import EducationItemForm
from tests.conftest import png_bytes
from tests.plugin_stale_edit_test import editor_resume as _editor_resume, loaded_data

editor_resume = _editor_resume


@pytest.mark.django_db
@pytest.mark.parametrize("admin", [False, True])
@pytest.mark.parametrize("image", [False, True])
def test_add_form_retry_is_one_operation(
    client, editor_resume, admin, image, in_memory_storage, monkeypatch, mocker
):
    plugin = plugin_registry.get_plugin("education")
    view = plugin.admin if admin else plugin.inline
    if image:

        class ImageItemForm(ImageFormMixin, EducationItemForm):
            photo = forms.FileField(required=False)
            clear_photo = forms.BooleanField(required=False)
            image_fields = [("photo", "clear_photo")]

        monkeypatch.setitem(view.form_classes, "item", ImageItemForm)
    get_url = (
        view.get_item_add_form_url(editor_resume.pk)
        if admin
        else view.get_edit_item_url(editor_resume.pk)
    )
    post_url = (
        view.get_change_item_post_url(editor_resume.pk)
        if admin
        else view.get_post_item_url(editor_resume.pk)
    )
    first = loaded_data(client, get_url, post_url)
    fresh = loaded_data(client, get_url, post_url)
    assert first["id"] and fresh["id"] != first["id"]
    first.update(school_name="Invented school", position=1)
    fresh.update(school_name="Another invented school", position=2)
    save = mocker.spy(default_storage, "save")

    def submit(data):
        if image:
            data = {
                **data,
                "photo": SimpleUploadedFile("invented.png", png_bytes(2, 2)),
            }
        return client.post(post_url, data)

    assert submit(first).status_code == 200
    replay = submit(first)
    assert "changed since you opened it" in replay.content.decode()
    editor_resume.refresh_from_db()
    items = editor_resume.plugin_data["education"]["items"]
    assert len(items) == 2
    assert items[-1]["id"] == first["id"]
    assert save.call_count == int(image)
    assert submit(fresh).status_code == 200
    editor_resume.refresh_from_db()
    assert len(editor_resume.plugin_data["education"]["items"]) == 3
    assert save.call_count == 2 * int(image)


def rendered_delete_url(client, resume, admin):
    plugin = plugin_registry.get_plugin("education")
    if admin:
        response = client.get(plugin.admin.get_change_url(resume.pk))
        return response.context["item_forms"][0].delete_url
    response = client.get("/resume/" + resume.slug + "/cv/?edit=true")
    # Public page rendering includes item controls for its owner.
    from html.parser import HTMLParser

    class Deletes(HTMLParser):
        urls = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if "hx-delete" in attrs and "/education/" in attrs["hx-delete"]:
                self.urls.append(attrs["hx-delete"])

    parser = Deletes()
    parser.feed(response.content.decode())
    assert parser.urls
    return parser.urls[0]


@pytest.mark.django_db
@pytest.mark.parametrize("admin", [False, True])
def test_delete_requires_rendered_current_item_revision(client, editor_resume, admin):
    stale_url = rendered_delete_url(client, editor_resume, admin)
    plugin = plugin_registry.get_plugin("education")
    editor_resume.plugin_data["education"]["items"][0]["school_name"] = (
        "Concurrent invented edit"
    )
    editor_resume.save(update_fields=["plugin_data"])
    response = client.delete(stale_url)
    assert response.status_code == 409
    assert "Reload" in response.content.decode()
    editor_resume.refresh_from_db()
    assert (
        editor_resume.plugin_data["education"]["items"][0]["school_name"]
        == "Concurrent invented edit"
    )
    view = plugin.admin if admin else plugin.inline
    assert (
        client.delete(view.get_delete_item_url(editor_resume.pk, "school")).status_code
        == 409
    )
    fresh_url = rendered_delete_url(client, editor_resume, admin)
    assert client.delete(fresh_url).status_code == 200
    editor_resume.refresh_from_db()
    assert editor_resume.plugin_data["education"]["items"] == []


@pytest.mark.django_db
@pytest.mark.parametrize("admin", [False, True])
def test_delete_revision_ignores_other_items_but_rejects_other_targets(
    client, editor_resume, admin
):
    url = rendered_delete_url(client, editor_resume, admin)
    plugin = plugin_registry.get_plugin("education")
    view = plugin.admin if admin else plugin.inline
    editor_resume.plugin_data["education"]["items"].append(
        {"id": "other", "school_name": "Another invented school"}
    )
    editor_resume.plugin_data["education"]["flat"]["title"] = "Concurrent title"
    editor_resume.save(update_fields=["plugin_data"])
    wrong_url = (
        view.get_delete_item_url(editor_resume.pk, "other") + "?" + url.split("?", 1)[1]
    )
    assert client.delete(wrong_url).status_code == 409
    assert client.delete(url + "tampered").status_code == 409
    assert client.delete(url).status_code == 200
    assert client.delete(url).status_code == 409
    editor_resume.refresh_from_db()
    assert [item["id"] for item in editor_resume.plugin_data["education"]["items"]] == [
        "other"
    ]


@pytest.mark.django_db
def test_admin_delete_survives_htmx_appending_enclosing_form_fields(
    client, editor_resume
):
    """htmx sends the enclosing form's inputs as DELETE query parameters.

    The admin item form renders its own item-scope ``edit_revision`` hidden
    field around the Delete link, so the delete-scope token must not share
    that parameter name.
    """
    from urllib.parse import urlencode

    plugin = plugin_registry.get_plugin("education")
    response = client.get(plugin.admin.get_change_url(editor_resume.pk))
    form = response.context["item_forms"][0]
    fields = {
        name: form[name].value() if form[name].value() is not None else ""
        for name in form.fields
    }
    assert fields["edit_revision"]
    url = form.delete_url + "&" + urlencode({"csrfmiddlewaretoken": "x", **fields})
    assert client.delete(url).status_code == 200
    editor_resume.refresh_from_db()
    assert editor_resume.plugin_data["education"]["items"] == []
