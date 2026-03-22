from django_resume.plugins.projects import ProjectItemForm
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
