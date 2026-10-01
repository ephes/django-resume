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
