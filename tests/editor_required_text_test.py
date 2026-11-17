from copy import deepcopy

from django import forms
import pytest

from django_resume.markdown import markdown_to_textarea_input
from django_resume.plugins.about import AboutForm
from django_resume.plugins.base import EditorTextField
from django_resume.plugins.projects import ProjectItemForm
from tests.editor_helpers import post_current_editor


EMPTY_INPUTS = [
    None,
    "",
    " \t\n",
    "<div><br></div>",
    "<br>",
    "&nbsp;",
    "<div>&nbsp;<br></div>",
    "<em></em>",
    "\u00a0",
]


@pytest.mark.parametrize("submitted", EMPTY_INPUTS)
@pytest.mark.parametrize("plugin_name", ["about", "projects"])
def test_required_forms_validate_decoded_empty_text(resume, submitted, plugin_name):
    if plugin_name == "about":
        field = "text"
        form = AboutForm(data={"title": "Synthetic", field: submitted})
    else:
        field = "description"
        form = ProjectItemForm(
            data={"title": "Synthetic", field: submitted, "position": 0},
            resume=resume,
            existing_items=[],
        )
    assert not form.is_valid()
    assert form.errors.as_data()[field][0].code == "required"
    assert field not in form.cleaned_data


@pytest.mark.parametrize("submitted", EMPTY_INPUTS)
def test_optional_editor_text_accepts_decoded_empty_values(submitted):
    assert EditorTextField(required=False).clean(submitted) == ""


@pytest.mark.parametrize("stored", ["é & ∳", "<br>", "&nbsp;", "R&D\u00a0team"])
def test_required_editor_text_validates_and_returns_same_decoded_value(stored):
    seen = []
    field = EditorTextField(
        required=True,
        min_length=len(stored),
        max_length=len(stored),
        validators=[seen.append],
    )
    assert field.clean(markdown_to_textarea_input(stored)) == stored
    assert seen == [stored]
    with pytest.raises(forms.ValidationError) as error:
        field.clean(markdown_to_textarea_input(stored + "x"))
    assert error.value.error_list[0].code == "max_length"


@pytest.mark.django_db
@pytest.mark.parametrize("surface", ["admin", "inline"])
@pytest.mark.parametrize("plugin_name", ["about", "projects"])
@pytest.mark.parametrize("submitted", ["<div><br></div>", "<br>", "&nbsp;"])
def test_empty_required_editor_posts_preserve_stored_data(
    client, resume, surface, plugin_name, submitted
):
    from django_resume.plugins import plugin_registry

    resume.owner.is_staff = True
    resume.owner.save()
    resume.plugin_data = {
        "about": {"title": "Synthetic", "text": "Original about"},
        "projects": {
            "flat": {"title": "Projects"},
            "items": [
                {
                    "id": "p1",
                    "title": "Synthetic",
                    "url": "",
                    "description": "Original project",
                    "badges": [],
                    "position": 0,
                }
            ],
        },
    }
    original = deepcopy(resume.plugin_data)
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_registry.get_plugin(plugin_name)
    view = plugin.admin if surface == "admin" else plugin.inline
    if plugin_name == "about":
        field = "text"
        url = (
            view.get_change_post_url(resume.pk)
            if surface == "admin"
            else view.get_post_url(resume.pk)
        )
    else:
        field = "description"
        url = (
            view.get_change_item_post_url(resume.pk)
            if surface == "admin"
            else view.get_post_item_url(resume.pk)
        )
    response = post_current_editor(
        client,
        url,
        {
            "id": "p1",
            "title": "Synthetic",
            "position": 0,
            field: submitted,
        },
    )
    assert response.status_code == 200
    assert b"This field is required." in response.content
    resume.refresh_from_db()
    assert resume.plugin_data == original
