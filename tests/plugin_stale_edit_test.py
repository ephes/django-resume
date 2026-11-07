"""Real GET/POST editor revisions, with synthetic rows and in-memory uploads."""

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile

from django_resume.models import Resume
from django_resume.plugins.education import EducationPlugin
from django_resume.plugins.identity import IdentityPlugin
from tests.conftest import png_bytes


@pytest.fixture
def editor_resume(client, django_user_model):
    owner = django_user_model.objects.create_superuser(username="synthetic-owner")
    resume = Resume.objects.create(
        name="Synthetic",
        slug="synthetic",
        owner=owner,
        plugin_data={
            "identity": {"name": "Original"},
            "education": {
                "flat": {"title": "Education"},
                "items": [
                    {"id": "school", "school_name": "Original school", "position": 0}
                ],
            },
        },
    )
    client.force_login(owner)
    return resume


def editor_case(kind, resume):
    plugin = IdentityPlugin() if kind.startswith("simple") else EducationPlugin()
    admin = kind.endswith("admin")
    view = plugin.admin if admin else plugin.inline
    if kind.startswith("simple"):
        get_url = (
            view.get_change_url(resume.pk) if admin else view.get_edit_url(resume.pk)
        )
        post_url = (
            view.get_change_post_url(resume.pk)
            if admin
            else view.get_post_url(resume.pk)
        )
        return get_url, post_url, "name", "simple"
    if kind.startswith("flat"):
        get_url = (
            view.get_change_url(resume.pk)
            if admin
            else view.get_edit_flat_url(resume.pk)
        )
        post_url = (
            view.get_change_flat_post_url(resume.pk)
            if admin
            else view.get_edit_flat_post_url(resume.pk)
        )
        return get_url, post_url, "title", "flat"
    get_url = (
        view.get_change_url(resume.pk)
        if admin
        else view.get_edit_item_url(resume.pk, "school")
    )
    post_url = (
        view.get_change_item_post_url(resume.pk)
        if admin
        else view.get_post_item_url(resume.pk)
    )
    return get_url, post_url, "school_name", "item"


def loaded_data(client, url, scope):
    response = client.get(url)
    assert response.status_code == 200
    if scope == "flat" and "flat_form" in response.context:
        form = response.context["flat_form"]
    elif scope == "item" and "item_forms" in response.context:
        form = response.context["item_forms"][0]
    else:
        form = response.context["form"]
    return {
        name: field.value() or ""
        for name, field in ((name, form[name]) for name in form.fields)
    }


KINDS = [
    "simple-inline",
    "simple-admin",
    "flat-inline",
    "flat-admin",
    "item-inline",
    "item-admin",
]


@pytest.mark.django_db
@pytest.mark.parametrize("kind", KINDS)
def test_stale_editor_preserves_input_and_saved_state(
    client, editor_resume, kind, in_memory_storage, mocker
):
    get_url, post_url, field, scope = editor_case(kind, editor_resume)
    first = loaded_data(client, get_url, scope)
    second = loaded_data(client, get_url, scope)
    second[field] = "Saved by second browser"
    assert client.post(post_url, second).status_code == 200
    editor_resume.refresh_from_db()
    saved = editor_resume.plugin_data
    first[field] = "Unsaved first browser input"
    if scope == "simple":
        first["avatar_img"] = SimpleUploadedFile(
            "synthetic.png", png_bytes(2, 2), "image/png"
        )
    storage_save = mocker.spy(default_storage, "save")
    response = client.post(post_url, first)
    assert response.status_code == 200  # HTMX swaps the form with errors
    assert "changed since you opened it" in response.content.decode()
    assert first[field] in response.content.decode()
    storage_save.assert_not_called()
    editor_resume.refresh_from_db()
    assert editor_resume.plugin_data == saved
    assert "edit_revision" not in str(saved)
    # Admin keeps the form after a successful POST; its new token supports another save.
    if kind.endswith("admin"):
        data = loaded_data(client, get_url, scope)
        data[field] = "Fresh third save"
        assert client.post(post_url, data).context["form"].is_valid()


@pytest.mark.django_db
@pytest.mark.parametrize("revision", [None, "tampered"])
def test_missing_or_invalid_revision_cannot_store_upload(
    client, editor_resume, revision, in_memory_storage, mocker
):
    post_url = IdentityPlugin().inline.get_post_url(editor_resume.pk)
    data = {
        "name": "Rejected",
        "avatar_img": SimpleUploadedFile("synthetic.png", png_bytes(2, 2), "image/png"),
    }
    if revision is not None:
        data["edit_revision"] = revision
    save = mocker.spy(default_storage, "save")
    response = client.post(post_url, data)
    assert response.context["form"].errors["edit_revision"]
    save.assert_not_called()
    editor_resume.refresh_from_db()
    assert editor_resume.plugin_data["identity"]["name"] == "Original"


@pytest.mark.django_db
@pytest.mark.parametrize("kind", KINDS)
def test_unrelated_plugin_edit_does_not_conflict(client, editor_resume, kind):
    get_url, post_url, field, scope = editor_case(kind, editor_resume)
    data = loaded_data(client, get_url, scope)
    updated = editor_resume.plugin_data
    updated["unrelated"] = {"version": 2}
    Resume.objects.filter(pk=editor_resume.pk).update(plugin_data=updated)
    data[field] = "Accepted edit"
    response = client.post(post_url, data)
    assert "changed since you opened it" not in response.content.decode()
    editor_resume.refresh_from_db()
    assert editor_resume.plugin_data["unrelated"] == {"version": 2}
    assert "Accepted edit" in str(editor_resume.plugin_data)


@pytest.mark.django_db
@pytest.mark.parametrize("admin", [False, True])
def test_new_item_and_admin_resubmission(client, editor_resume, admin):
    view = EducationPlugin().admin if admin else EducationPlugin().inline
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
    data = loaded_data(client, get_url, "item")
    data.update(school_name="New synthetic school", position=1)
    response = client.post(post_url, data)
    editor_resume.refresh_from_db()
    assert len(editor_resume.plugin_data["education"]["items"]) == 2
    if admin:
        form = response.context["form"]
        again = {name: form[name].value() or "" for name in form.fields}
        again["school_name"] = "Renamed new school"
        response = client.post(post_url, again)
        assert response.context["form"].is_valid()
        editor_resume.refresh_from_db()
        assert len(editor_resume.plugin_data["education"]["items"]) == 2
        assert (
            editor_resume.plugin_data["education"]["items"][1]["school_name"]
            == "Renamed new school"
        )


@pytest.mark.django_db
def test_list_item_revision_ignores_other_items_and_flat_data(client, editor_resume):
    get_url, post_url, field, scope = editor_case("item-inline", editor_resume)
    data = loaded_data(client, get_url, scope)
    plugin_data = editor_resume.plugin_data
    plugin_data["education"]["flat"]["title"] = "Concurrent title"
    plugin_data["education"]["items"].append(
        {"id": "other", "school_name": "Concurrent school", "position": 1}
    )
    Resume.objects.filter(pk=editor_resume.pk).update(plugin_data=plugin_data)
    data[field] = "Updated original school"
    response = client.post(post_url, data)
    assert "changed since you opened it" not in response.content.decode()
    editor_resume.refresh_from_db()
    assert editor_resume.plugin_data["education"]["flat"]["title"] == "Concurrent title"
    assert (
        editor_resume.plugin_data["education"]["items"][1]["school_name"]
        == "Concurrent school"
    )
    assert (
        editor_resume.plugin_data["education"]["items"][0][field]
        == "Updated original school"
    )


@pytest.mark.django_db
@pytest.mark.parametrize("target", ["other-resume", "other-scope", "deleted-item"])
def test_revision_cannot_be_reused_for_a_different_target(
    client, editor_resume, target
):
    get_url, post_url, field, scope = editor_case("item-inline", editor_resume)
    data = loaded_data(client, get_url, scope)
    if target == "other-resume":
        other = Resume.objects.create(
            name="Other",
            slug="other",
            owner=editor_resume.owner,
            plugin_data=editor_resume.plugin_data,
        )
        post_url = EducationPlugin().inline.get_post_item_url(other.pk)
    elif target == "other-scope":
        post_url = EducationPlugin().inline.get_edit_flat_post_url(editor_resume.pk)
        data["title"] = "Rejected"
    else:
        editor_resume.plugin_data["education"]["items"] = []
        editor_resume.save(update_fields=["plugin_data"])
    data[field] = "Rejected"
    response = client.post(post_url, data)
    assert response.context["form"].errors["edit_revision"]
    assert all("Rejected" not in str(row.plugin_data) for row in Resume.objects.all())


@pytest.mark.django_db
@pytest.mark.parametrize("kind", ["item-inline", "item-admin"])
def test_legacy_item_without_position_can_be_saved(client, editor_resume, kind):
    editor_resume.plugin_data["education"]["items"][0].pop("position")
    editor_resume.save(update_fields=["plugin_data"])
    get_url, post_url, field, scope = editor_case(kind, editor_resume)
    data = loaded_data(client, get_url, scope)
    data[field] = "Edited legacy item"
    response = client.post(post_url, data)
    assert "changed since you opened it" not in response.content.decode()
    editor_resume.refresh_from_db()
    assert (
        editor_resume.plugin_data["education"]["items"][0][field]
        == "Edited legacy item"
    )


@pytest.mark.django_db
def test_token_admin_get_and_save_existing_token(client, editor_resume):
    from django.utils import timezone
    from django_resume.plugins import TokenPlugin

    editor_resume.plugin_data["token"] = {
        "items": [
            {
                "id": "synthetic-token",
                "token": "invented-secret",
                "receiver": "Original",
                "created": timezone.now().isoformat(),
            }
        ]
    }
    editor_resume.save(update_fields=["plugin_data"])
    plugin = TokenPlugin()
    response = client.get(plugin.admin.get_change_url(editor_resume.pk))
    assert response.status_code == 200
    form = response.context["item_forms"][0]
    data = {name: form[name].value() or "" for name in form.fields}
    data["receiver"] = "Edited receiver"
    response = client.post(
        plugin.admin.get_change_item_post_url(editor_resume.pk), data
    )
    assert response.context["form"].is_valid()
    editor_resume.refresh_from_db()
    assert (
        editor_resume.plugin_data["token"]["items"][0]["receiver"] == "Edited receiver"
    )


def test_custom_example_forms_render_one_revision(settings):
    from pathlib import Path
    from django import forms
    from django.template.loader import render_to_string
    from html.parser import HTMLParser
    from copy import deepcopy

    root = Path(__file__).resolve().parents[1]
    templates = deepcopy(settings.TEMPLATES)
    templates[0]["DIRS"] = [root / "example" / "templates"]
    settings.TEMPLATES = templates
    form = forms.Form()
    form.fields["edit_revision"] = forms.CharField(
        widget=forms.HiddenInput, initial="signed-example"
    )
    paths = [
        "django_resume/plugins/motto/plain/form.html",
        "django_resume/plugins/certifications/plain/flat_form.html",
        "django_resume/plugins/certifications/plain/item_form.html",
        "django_resume/plugins/token/plain/flat_form.html",
    ]

    class RevisionInputs(HTMLParser):
        in_form = False

        def __init__(self):
            super().__init__()
            self.values = []

        def handle_starttag(self, tag, attrs):
            if tag == "form":
                self.in_form = True
            attributes = dict(attrs)
            if (
                self.in_form
                and tag == "input"
                and attributes.get("name") == "edit_revision"
            ):
                self.values.append(attributes.get("value"))

        def handle_endtag(self, tag):
            if tag == "form":
                self.in_form = False

    for path in paths:
        parser = RevisionInputs()
        parser.feed(render_to_string(path, {"form": form}))
        assert parser.values == ["signed-example"], path
