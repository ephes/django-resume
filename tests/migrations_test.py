import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [("django_resume", "0002_resume_integration_data")]
AFTER = [("django_resume", "0003_education_list_items")]


def migrate(targets):
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(targets)
    return executor.loader.project_state(targets).apps


def create_resume(apps, slug, plugin_data):
    User = apps.get_model("auth", "User")
    Resume = apps.get_model("django_resume", "Resume")
    owner, _ = User.objects.get_or_create(username="migration-owner")
    return Resume.objects.create(
        name=slug, slug=slug, owner=owner, plugin_data=plugin_data
    )


@pytest.mark.django_db(transaction=True)
def test_education_migration_converts_single_entry_to_list():
    old_apps = migrate(BEFORE)
    legacy = create_resume(
        old_apps,
        "legacy",
        {
            "education": {
                "school_name": "Example University",
                "school_url": "https://uni.example",
                "start": "2010",
                "end": "2014",
            },
            "about": {"title": "About"},
        },
    )
    empty = create_resume(
        old_apps, "empty", {"education": {"school_name": "", "start": ""}}
    )
    untouched = create_resume(old_apps, "untouched", {"about": {"title": "About"}})

    new_apps = migrate(AFTER)
    Resume = new_apps.get_model("django_resume", "Resume")

    assert Resume.objects.get(pk=legacy.pk).plugin_data == {
        "education": {
            "flat": {"title": "Education"},
            "items": [
                {
                    "id": "education-1",
                    "school_name": "Example University",
                    "school_url": "https://uni.example",
                    "degree": "",
                    "start": "2010",
                    "end": "2014",
                    "position": 0,
                }
            ],
        },
        "about": {"title": "About"},
    }
    assert Resume.objects.get(pk=empty.pk).plugin_data == {"education": {}}
    assert Resume.objects.get(pk=untouched.pk).plugin_data == {
        "about": {"title": "About"}
    }


@pytest.mark.django_db(transaction=True)
def test_education_migration_reverse_keeps_first_entry():
    new_apps = migrate(AFTER)
    resume = create_resume(
        new_apps,
        "listed",
        {
            "education": {
                "flat": {"title": "Education"},
                "items": [
                    {"id": "b", "school_name": "Second", "position": 1},
                    {"id": "a", "school_name": "First", "end": "2014", "position": 0},
                ],
            }
        },
    )

    old_apps = migrate(BEFORE)
    Resume = old_apps.get_model("django_resume", "Resume")

    assert Resume.objects.get(pk=resume.pk).plugin_data == {
        "education": {
            "school_name": "First",
            "school_url": "",
            "start": "",
            "end": "2014",
        }
    }
    migrate(AFTER)
