from django_resume.plugins import plugin_registry
from django_resume.plugins.awards import AwardsItemForm, AwardsPlugin


def test_awards_plugin_registered():
    assert plugin_registry.get_plugin("awards") is not None
    assert "cv" in AwardsPlugin.capabilities


def test_awards_item_form_valid_and_context(resume):
    form = AwardsItemForm(
        data={
            "id": "a1",
            "title": "Design Award 2024: Bronze",
            "project": "Example Campaign",
            "year": "2024",
            "position": 0,
        },
        resume=resume,
        existing_items=[],
    )
    assert form.is_valid(), form.errors
    context = form.set_context(form.cleaned_data, {"edit_url": "#", "delete_url": "#"})
    assert context["award"]["title"] == "Design Award 2024: Bronze"
    assert context["award"]["year"] == "2024"


def test_awards_json_resume_export_and_import(resume):
    plugin = AwardsPlugin()
    plugin.data.set_data(
        resume,
        {
            "items": [
                {"id": "b", "title": "Later", "year": "someday", "position": 1},
                {
                    "id": "a",
                    "title": "Bronze",
                    "project": "Example Campaign",
                    "year": "2024",
                    "position": 0,
                },
            ]
        },
    )
    adapter = plugin.get_export_adapters()["json_resume"]

    exported = adapter.export(plugin.get_structured_data(resume))

    assert exported.contributions == [
        (
            "/awards",
            [
                {"title": "Bronze", "summary": "Example Campaign", "date": "2024"},
                {"title": "Later"},
            ],
        )
    ]
    assert any("someday" in note for note in exported.notes)

    imported = plugin.get_import_adapters()["json_resume"].import_data(
        {"awards": [{"title": "Bronze", "date": "2024", "awarder": "Jury"}]}
    )
    [item] = imported.plugin_data["items"]
    assert (item["title"], item["year"], item["position"]) == ("Bronze", "2024", 0)
    assert any("awarder is not imported" in note for note in imported.notes)
