from django_resume.plugins import plugin_registry
from django_resume.plugins.base import ListPlugin
from django_resume.plugins.education import (
    EducationItemForm,
    EducationPlugin,
    normalize_education_data,
)


def test_education_plugin_is_registered_as_list():
    plugin = plugin_registry.get_plugin("education")
    assert isinstance(plugin, ListPlugin)


def test_education_item_form_degree_round_trips_into_context(resume):
    form = EducationItemForm(
        data={
            "id": "e1",
            "school_name": "Example University",
            "school_url": "https://uni.example",
            "degree": "BSc Computer Science",
            "start": "",
            "end": "2014",
            "position": 0,
        },
        resume=resume,
        existing_items=[],
    )

    assert form.is_valid(), form.errors
    context = form.set_context(form.cleaned_data, {"edit_url": "#", "delete_url": "#"})
    assert context["entry"]["degree"] == "BSc Computer Science"
    assert context["entry"]["school_name"] == "Example University"
    assert context["entry"]["end"] == "2014"


def test_normalize_education_data_keeps_list_data_unchanged():
    data = {"flat": {"title": "Studies"}, "items": []}
    assert normalize_education_data(data) is data


def test_normalize_education_data_drops_empty_legacy_data():
    assert normalize_education_data({"school_name": "", "end": ""}) == {}


def test_legacy_education_data_is_read_as_one_item(resume):
    # Given education data in the pre-list shape
    resume.plugin_data = {"education": {"school_name": "Uni", "end": "2014"}}
    plugin = EducationPlugin()

    # When a new entry is added
    plugin.data.create(resume, {"id": "new", "school_name": "Second", "position": 1})

    # Then the legacy entry is kept as the first item of the list
    items = plugin.get_data(resume)["items"]
    assert [item["school_name"] for item in items] == ["Uni", "Second"]
    assert resume.plugin_data["education"]["flat"] == {"title": "Education"}


def test_reading_legacy_education_data_does_not_change_stored_data(resume):
    # Given legacy education data, e.g. restored from an older round-trip export
    legacy = {"school_name": "Uni", "end": "2014"}
    resume.plugin_data = {"education": dict(legacy)}

    # When the plugin reads it for rendering or export
    EducationPlugin().get_data(resume)
    EducationPlugin().get_structured_data(resume)

    # Then the stored plugin data is left untouched
    assert resume.plugin_data == {"education": legacy}
