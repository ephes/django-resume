import pytest

from django_resume.plugins import EmployedTimelinePlugin
from django_resume.plugins.projects import ProjectItemForm, ProjectsPlugin
from django_resume.plugins.timelines import TimelineItemForm


def test_project_item_form_accepts_regular_titles_without_demo_validation(resume):
    form = ProjectItemForm(
        data={
            "title": "Senor Developer",
            "url": "https://example.com/project",
            "description": "Built things",
            "badges": '["python"]',
            "position": 0,
        },
        resume=resume,
        existing_items=[],
    )

    assert form.is_valid()


def test_timeline_item_form_accepts_role_values_without_demo_validation(resume):
    form = TimelineItemForm(
        data={
            "role": "Senor Developer",
            "company_url": "https://example.com/company",
            "company_name": "ACME",
            "description": "Built things",
            "start": "2020",
            "end": "2022",
            "badges": '["remote"]',
            "position": 0,
        },
        resume=resume,
        existing_items=[],
    )

    assert form.is_valid()


PROJECT_ITEM = {
    "title": "Project",
    "url": "https://example.com/project",
    "description": "Built things",
    "badges": '["python"]',
}
TIMELINE_ITEM = {
    "role": "Developer",
    "company_url": "https://example.com/company",
    "company_name": "ACME",
    "description": "Built things",
    "start": "2020",
    "end": "2022",
    "badges": '["remote"]',
}
ITEM_FORMS = [(ProjectItemForm, PROJECT_ITEM), (TimelineItemForm, TIMELINE_ITEM)]
ITEM_PLUGINS = [(ProjectsPlugin, PROJECT_ITEM), (EmployedTimelinePlugin, TIMELINE_ITEM)]


@pytest.mark.parametrize("form_class, item", ITEM_FORMS)
def test_item_form_treats_empty_position_as_zero(resume, form_class, item):
    form = form_class(data={**item, "position": ""}, resume=resume, existing_items=[])

    assert form.is_valid(), form.errors
    assert form.cleaned_data["position"] == 0


@pytest.mark.parametrize("form_class, item", ITEM_FORMS)
def test_item_form_rejects_empty_position_taken_by_another_item(
    resume, form_class, item
):
    form = form_class(
        data={**item, "id": "new", "position": ""},
        resume=resume,
        existing_items=[{"id": "other", "position": 0}],
    )

    assert not form.is_valid()
    assert "position" in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("plugin_class, item", ITEM_PLUGINS)
@pytest.mark.parametrize("view", ["admin", "inline"])
def test_item_post_with_empty_position_saves_item(
    client, resume, plugin_class, item, view
):
    # Given a staff owner editing a list section
    resume.owner.is_staff = True
    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_class()
    if view == "admin":
        post_url = plugin.admin.get_change_item_post_url(resume.pk)
    else:
        post_url = plugin.inline.get_post_item_url(resume.pk)

    # When an item is posted with an empty position
    response = client.post(post_url, {**item, "position": ""})

    # Then it is stored at position 0 instead of failing
    assert response.status_code == 200
    resume.refresh_from_db()
    [stored] = plugin.data.get_data(resume)["items"]
    assert stored["position"] == 0
