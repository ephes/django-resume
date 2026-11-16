"""The skills editor and export share a bounded string-list domain."""

import json
from copy import deepcopy

import pytest
from django.test import RequestFactory

from django_resume.formats.json_resume.export import export_resume
from django_resume.formats.json_resume.importer import import_resume_document
from django_resume.formats.json_resume.validation import validate_document
from django_resume.plugins.skills import SkillsForm, SkillsPlugin
from tests.editor_helpers import post_current_editor


INVALID_BADGES = [
    "{}",
    '"Python"',
    "[{}]",
    '[["Python"]]',
    "[true]",
    "[1]",
    "[NaN]",
    "[Infinity]",
    "[1e999]",
    "[null]",
    json.dumps(["x"] * 1025),
    json.dumps(["x" * 1025]),
    json.dumps(["x" * 1024] * 65),
]


@pytest.mark.parametrize("badges", INVALID_BADGES)
def test_skills_form_rejects_non_string_lists_and_limits(badges):
    form = SkillsForm(data={"badges": badges})
    assert not form.is_valid()
    assert "badges" in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("view", ["admin", "inline"])
@pytest.mark.parametrize("badges", INVALID_BADGES)
def test_invalid_badges_post_does_not_save(client, resume, view, badges):
    resume.owner.is_staff = True
    resume.owner.save()
    resume.plugin_data = {"skills": {"badges": ["Python"]}}
    resume.save()
    client.force_login(resume.owner)
    plugin = SkillsPlugin()
    post_url = (
        plugin.inline.get_post_url(resume.pk)
        if view == "inline"
        else plugin.admin.get_change_post_url(resume.pk)
    )
    response = post_current_editor(client, post_url, {"badges": badges})
    assert response.status_code == 200
    resume.refresh_from_db()
    assert resume.plugin_data == {"skills": {"badges": ["Python"]}}


@pytest.mark.parametrize(
    "stored",
    [["Python", {}, ["nested"], True, 3, None], '["Python", false]', {"x": 1}],
)
def test_legacy_badges_display_only_strings_without_writing(resume, stored):
    plugin = SkillsPlugin()
    resume.plugin_data = {"skills": {"badges": stored}}
    original = deepcopy(resume.plugin_data)
    expected = ["Python"] if isinstance(stored, (list, str)) else []
    assert plugin.get_structured_data(resume) == {"skills": expected}
    context = plugin.get_context(
        RequestFactory().get("/"), plugin.get_data(resume), 1, context={}
    )
    assert context["badges"] == expected
    assert json.loads(SkillsForm(initial={"badges": stored}).badges_as_json()) == (
        json.loads(stored) if isinstance(stored, str) else stored
    )
    assert resume.plugin_data == original
    assert validate_document(export_resume(resume).document) == []


@pytest.mark.django_db
def test_unicode_skills_render_and_export_unchanged(client, resume):
    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    badges = ["日本語", "Café", "Python 🐍"]
    plugin = SkillsPlugin()
    response = post_current_editor(
        client, plugin.inline.get_post_url(resume.pk), {"badges": json.dumps(badges)}
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert all(badge in html for badge in badges)
    resume.refresh_from_db()
    assert resume.plugin_data["skills"]["badges"] == badges
    exported = export_resume(resume).document
    assert validate_document(exported) == []
    assert exported["skills"] == [{"name": badge} for badge in badges]


@pytest.mark.django_db
def test_import_refuses_skills_that_exceed_editor_limits(user):
    user.save()
    result = import_resume_document(
        {"skills": [{"name": "x" * 1025}]}, owner=user, slug="long-skill"
    )
    assert result.resume is None
    assert not result.report.valid
    assert any("skills.badges" in error for error in result.report.validation_errors)
