"""Project and timeline badges stay portable through editors and imports."""

import json
from copy import deepcopy

import pytest

from django_resume.formats.json_resume.export import export_resume
from django_resume.formats.json_resume.importer import import_resume_document
from django_resume.formats.json_resume.validation import validate_document
from django_resume.models import Resume
from django_resume.plugins.projects import ProjectsPlugin
from django_resume.plugins.timelines import (
    EmployedTimelinePlugin,
    FreelanceTimelinePlugin,
)
from tests.editor_helpers import post_current_editor


PLUGINS = [ProjectsPlugin, EmployedTimelinePlugin, FreelanceTimelinePlugin]
INVALID = [
    "{}",
    '"badge"',
    "false",
    "0",
    "null",
    "[{}]",
    '[["nested"]]',
    "[true]",
    "[1]",
    "[null]",
    "[NaN]",
    "[Infinity]",
    "[1e999]",
    json.dumps(["x"] * 1025),
    json.dumps(["x" * 1025]),
]


def item_data(badges):
    return {
        "id": "synthetic-item",
        "title": "Synthetic project",
        "role": "Developer",
        "company_name": "Synthetic company",
        "description": "Synthetic description",
        "start": "2020",
        "end": "2022",
        "url": "",
        "company_url": "",
        "position": 0,
        "badges": badges,
    }


@pytest.mark.parametrize("plugin_class", PLUGINS)
@pytest.mark.parametrize("badges", INVALID)
def test_item_forms_reject_non_string_and_oversized_badges(
    resume, plugin_class, badges
):
    plugin = plugin_class()
    form = plugin.get_form_classes()["item"](data=item_data(badges), resume=resume)
    assert not form.is_valid()
    assert "badges" in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("plugin_class", PLUGINS)
@pytest.mark.parametrize("view", ["admin", "inline"])
@pytest.mark.parametrize("badges", INVALID)
def test_invalid_editor_badges_never_save(client, resume, plugin_class, view, badges):
    resume.owner.is_staff = True
    resume.owner.save()
    plugin = plugin_class()
    stored = item_data(["keep"])
    resume.plugin_data = {plugin.name: {"items": [stored]}}
    resume.save()
    client.force_login(resume.owner)
    response = post_current_editor(
        client,
        (
            plugin.admin.get_change_item_post_url(resume.pk)
            if view == "admin"
            else plugin.inline.get_post_item_url(resume.pk)
        ),
        item_data(badges),
    )
    assert response.status_code == 200
    resume.refresh_from_db()
    assert resume.plugin_data[plugin.name]["items"] == [stored]


@pytest.mark.django_db
@pytest.mark.parametrize("plugin_class", PLUGINS)
@pytest.mark.parametrize("view", ["admin", "inline"])
@pytest.mark.parametrize(
    "badges", [["日本語", "Café", "Python 🐍"], ["x" * 1024] * 1024, []]
)
def test_editor_to_real_adapter_preserves_valid_badges(
    client, resume, plugin_class, view, badges
):
    resume.owner.is_staff = True
    resume.owner.save()
    plugin = plugin_class()
    resume.plugin_data = {plugin.name: {"items": [item_data(["old"])]}}
    resume.save()
    client.force_login(resume.owner)
    response = post_current_editor(
        client,
        (
            plugin.admin.get_change_item_post_url(resume.pk)
            if view == "admin"
            else plugin.inline.get_post_item_url(resume.pk)
        ),
        item_data(json.dumps(badges) if badges else ""),
    )
    assert response.status_code == 200
    resume.refresh_from_db()
    assert resume.plugin_data[plugin.name]["items"][0]["badges"] == badges
    result = export_resume(resume)
    assert validate_document(result.document) == []
    section, field = (
        ("projects", "keywords")
        if plugin.name == "projects"
        else ("work", "highlights")
    )
    assert result.document[section][0].get(field, []) == badges


@pytest.mark.parametrize("plugin_class", PLUGINS)
@pytest.mark.parametrize(
    "stored",
    [
        ["日本語", {"sentinel": "private"}, True, 3, None],
        '["日本語", false]',
        {"sentinel": "private"},
        ["x" * 1025],
        ["x"] * 1025,
    ],
)
def test_legacy_export_omits_invalid_values_with_safe_diagnostics(
    resume, plugin_class, stored
):
    plugin = plugin_class()
    resume.plugin_data = {plugin.name: {"items": [item_data(stored)]}}
    original = deepcopy(resume.plugin_data)
    result = export_resume(resume)
    assert validate_document(result.document) == []
    section, field = (
        ("projects", "keywords")
        if plugin.name == "projects"
        else ("work", "highlights")
    )
    expected = (
        ["日本語"]
        if isinstance(stored, (list, str)) and "日本語" in stored
        else (["x"] * 1024 if isinstance(stored, list) and len(stored) > 1024 else [])
    )
    assert result.document[section][0].get(field, []) == expected
    assert any("badges" in note and "omitted" in note for note in result.report.notes)
    assert "private" not in " ".join(result.report.notes)
    assert resume.plugin_data == original


@pytest.mark.django_db
@pytest.mark.parametrize("plugin_class", PLUGINS)
@pytest.mark.parametrize("badges", INVALID)
def test_private_import_refuses_invalid_badges_before_creation(
    user, plugin_class, badges
):
    user.save()
    plugin = plugin_class()
    document = {
        "meta": {
            "django_resume": {
                "plugin_data": {plugin.name: {"items": [item_data(json.loads(badges))]}}
            }
        }
    }
    original = deepcopy(document)
    result = import_resume_document(document, owner=user, slug="rejected")
    assert result.resume is None
    assert not result.report.valid
    assert not Resume.objects.exists()
    assert document == original


@pytest.mark.django_db
@pytest.mark.parametrize("badges", [["x"] * 1025, ["x" * 1025]])
def test_portable_project_import_refuses_editor_limits(user, badges):
    user.save()
    document = {"projects": [{"name": "Synthetic", "keywords": badges}]}
    assert validate_document(document) == []
    result = import_resume_document(document, owner=user, slug="rejected")
    assert result.resume is None
    assert any(
        "projects.items[0].badges" in error for error in result.report.validation_errors
    )
    assert not Resume.objects.exists()
