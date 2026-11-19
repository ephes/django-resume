import pytest
from importlib import import_module

from django.db import connection, connections, models
from django.db.migrations.exceptions import IrreversibleError
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext

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


migration = import_module("django_resume.migrations.0003_education_list_items")


@pytest.mark.django_db(transaction=True, databases=["default", "other"])
def test_education_migration_uses_selected_database():
    apps = MigrationExecutor(connection).loader.project_state(BEFORE).apps
    Resume = apps.get_model("django_resume", "Resume")
    User = apps.get_model("auth", "User")
    for alias in ("default", "other"):
        owner = User.objects.using(alias).create(username=alias)
        Resume.objects.using(alias).create(
            name=alias,
            slug=alias,
            owner_id=owner.pk,
            plugin_data={"education": {"school_name": alias}},
        )
    with connections["other"].schema_editor() as editor:
        migration.education_to_list(apps, editor)
    assert (
        Resume.objects.using("other")
        .get()
        .plugin_data["education"]["items"][0]["school_name"]
        == "other"
    )
    assert Resume.objects.get().plugin_data == {"education": {"school_name": "default"}}
    with connections["other"].schema_editor() as editor:
        migration.education_to_single_entry(apps, editor)
    assert (
        Resume.objects.using("other").get().plugin_data["education"]["school_name"]
        == "other"
    )
    assert Resume.objects.get().plugin_data == {"education": {"school_name": "default"}}


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "education",
    [
        {"items": [{"school_name": "First"}, {"school_name": "Second"}]},
        {"items": [{"school_name": "School", "degree": "PhD"}]},
        {"items": [{"school_name": "School", "extension": "curated"}]},
        {"items": [], "flat": {"title": "My schools"}},
        {"items": [], "extension": "curated"},
        {"items": "malformed"},
    ],
)
def test_reverse_preflights_every_row(education):
    apps = MigrationExecutor(connection).loader.project_state(AFTER).apps
    first = create_resume(
        apps, "first", {"education": {"items": [{"school_name": "Safe"}]}}
    )
    last = create_resume(apps, "last", {"education": education})
    with (
        connection.schema_editor() as editor,
        pytest.raises(IrreversibleError, match="backup") as error,
    ):
        migration.education_to_single_entry(apps, editor)
    assert len(str(error.value)) < 300
    for resume in (first, last):
        original = resume.plugin_data
        resume.refresh_from_db()
        assert resume.plugin_data == original


@pytest.mark.django_db(transaction=True)
def test_education_migration_lossless_round_trip():
    apps = migrate(BEFORE)
    null_root = create_resume(apps, "null-root", models.Value(None, models.JSONField()))
    resume = create_resume(
        apps,
        "roundtrip",
        {
            "education": {
                "school_name": "Example",
                "school_url": "",
                "start": "2010",
                "end": "2014",
            }
        },
    )
    original = resume.plugin_data
    migrate(AFTER)
    null_root.refresh_from_db()
    assert null_root.plugin_data is None
    apps = migrate(BEFORE)
    assert (
        apps.get_model("django_resume", "Resume").objects.get(pk=resume.pk).plugin_data
        == original
    )
    null_root.refresh_from_db()
    assert null_root.plugin_data is None
    migrate(AFTER)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize(
    "education",
    [
        {"school_name": "Example", "extension": {"custom": "value"}},
        {"extension": "extension-only"},
    ],
)
def test_forward_refuses_extensions_before_any_write(education):
    apps = MigrationExecutor(connection).loader.project_state(BEFORE).apps
    first = create_resume(apps, "safe-first", {"education": {"school_name": "Safe"}})
    last = create_resume(apps, "extension-last", {"education": education})
    with (
        connection.schema_editor() as editor,
        pytest.raises(RuntimeError, match="backup"),
    ):
        migration.education_to_list(apps, editor)
    for resume in (first, last):
        original = resume.plugin_data
        resume.refresh_from_db()
        assert resume.plugin_data == original


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("plugin_data", [["synthetic"], "synthetic", [], False])
@pytest.mark.parametrize("reverse", [False, True])
def test_education_migration_refuses_non_object_plugin_data(plugin_data, reverse):
    source, target = (AFTER, BEFORE) if reverse else (BEFORE, AFTER)
    apps = migrate(source)
    education = {"school_name": "Synthetic School"}
    valid_data = {"education": {"items": [education]} if reverse else education}
    valid = create_resume(apps, "valid-first", valid_data)
    malformed = create_resume(apps, "malformed-last", plugin_data)
    error_type = IrreversibleError if reverse else RuntimeError

    try:
        with (
            CaptureQueriesContext(connection) as queries,
            pytest.raises(error_type, match=r"plugin_data.*backup.*JSON object") as exc,
        ):
            migrate(target)

        assert f"Resume {malformed.pk} " in str(exc.value)
        assert not any(query["sql"].lstrip().startswith("UPDATE") for query in queries)
        valid.refresh_from_db()
        malformed.refresh_from_db()
        assert valid.plugin_data == valid_data
        assert malformed.plugin_data == plugin_data
    finally:
        malformed.delete()
        migrate(AFTER)
