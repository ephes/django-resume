import pytest

from django_resume.plugins import plugin_registry
from django_resume.plugins.languages import LanguagesItemForm, LanguagesPlugin


def test_languages_plugin_registered():
    assert plugin_registry.get_plugin("languages") is not None
    assert "cv" in LanguagesPlugin.capabilities


def test_languages_item_form_builds_context_with_note(resume):
    form = LanguagesItemForm(
        data={
            "id": "l1",
            "name": "English",
            "level": 100,
            "note": "Native",
            "position": 0,
        },
        resume=resume,
        existing_items=[],
    )
    assert form.is_valid(), form.errors
    context = form.set_context(form.cleaned_data, {"edit_url": "#", "delete_url": "#"})
    assert context["language"]["name"] == "English"
    assert context["language"]["level"] == 100
    assert context["language"]["note"] == "Native"


def test_languages_level_out_of_range_invalid(resume):
    form = LanguagesItemForm(
        data={"id": "l2", "name": "French", "level": 250, "position": 1},
        resume=resume,
        existing_items=[],
    )
    assert not form.is_valid()
    assert "level" in form.errors


def test_languages_forms_handle_mixed_legacy_positions(resume):
    items = [
        {"id": "valid", "name": "Example", "level": 50, "position": 4},
        {"id": "null", "name": "Legacy", "level": 50, "position": None},
        {"id": "text", "position": "99"},
        {"id": "boolean", "position": True},
        {"id": "float", "position": 2.0},
        {"id": "negative", "position": -3},
        {"id": "missing"},
    ]
    add = LanguagesItemForm(resume=resume, existing_items=items)
    edit = LanguagesItemForm(resume=resume, existing_items=items, initial=items[1])
    assert add["position"].value() == edit["position"].value() == 5
    assert items[1]["position"] is None
    edit_valid = LanguagesItemForm(
        resume=resume, existing_items=items, initial=items[0]
    )
    assert edit_valid["position"].value() == 4
    add_without_valid_positions = LanguagesItemForm(
        resume=resume, existing_items=items[1:]
    )
    assert add_without_valid_positions["position"].value() == 0

    def submit(item_id, position):
        return LanguagesItemForm(
            resume=resume,
            existing_items=items,
            data={"id": item_id, "name": "Example", "level": 50, "position": position},
        )

    for position in ("1", "2", "5"):
        form = submit("null", position)
        assert form.is_valid(), form.errors
        assert form.cleaned_data["position"] == int(position)
    duplicate = submit("new", "4")
    assert not duplicate.is_valid()
    assert duplicate.errors["position"] == ["Position must be unique - take 5 instead."]
    own_position = submit("valid", "4")
    assert own_position.is_valid(), own_position.errors
    blank = submit("new", "")
    assert blank.is_valid(), blank.errors
    assert blank.cleaned_data["position"] == 0


@pytest.mark.parametrize("position", ["-1", "1.0", 1.0, True])
def test_languages_form_rejects_non_integer_or_negative_position(resume, position):
    form = LanguagesItemForm(
        resume=resume,
        data={"id": "new", "name": "Example", "level": 50, "position": position},
    )
    assert not form.is_valid()
    assert "position" in form.errors


def test_languages_json_resume_export_and_import(resume):
    plugin = LanguagesPlugin()
    plugin.data.set_data(
        resume,
        {
            "items": [
                {"id": "b", "name": "French", "level": 40, "position": 1},
                {
                    "id": "a",
                    "name": "English",
                    "level": 100,
                    "note": "Native",
                    "position": 0,
                },
            ]
        },
    )

    exported = plugin.get_export_adapters()["json_resume"].export(
        plugin.get_structured_data(resume)
    )

    assert exported.contributions == [
        (
            "/languages",
            [{"language": "English", "fluency": "Native"}, {"language": "French"}],
        )
    ]
    assert any("levels are not exported" in note for note in exported.notes)

    imported = plugin.get_import_adapters()["json_resume"].import_data(
        {"languages": [{"language": "English", "fluency": "Native"}]}
    )
    [item] = imported.plugin_data["items"]
    assert (item["name"], item["note"], item["level"]) == ("English", "Native", 80)
