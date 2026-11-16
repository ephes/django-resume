"""Shared browser/editor limits use Unicode code points and preserve legacy data."""

import json

import pytest

from django_resume.plugins.skills import SkillsForm
from django_resume.plugins.projects import ProjectItemForm
from django_resume.plugins.timelines import TimelineItemForm
from tests.item_badges_contract_test import item_data


@pytest.mark.parametrize("form_class", [SkillsForm, ProjectItemForm, TimelineItemForm])
def test_badge_aggregate_admission(form_class, resume):
    def form_for(badges):
        kwargs = {} if form_class is SkillsForm else {"resume": resume}
        return form_class(data=item_data(json.dumps(badges)), **kwargs)

    boundary = ["🐍" * 1024] * 64
    assert form_for(boundary).is_valid()
    form = form_for(boundary + ["x"])
    assert not form.is_valid()
    assert "badges" in form.errors


@pytest.mark.parametrize("form_class", [SkillsForm, ProjectItemForm, TimelineItemForm])
def test_editor_hydration_keeps_over_budget_initial_data(form_class, resume):
    stored = ["x" * 1024] * 65
    kwargs = {} if form_class is SkillsForm else {"resume": resume}
    form = form_class(initial={"badges": stored}, **kwargs)
    assert json.loads(form.badges_as_json()) == stored
    # Invalid submissions are redisplayed rather than replaced by old data.
    form = form_class(
        data=item_data(json.dumps(stored)), initial={"badges": ["old"]}, **kwargs
    )
    assert json.loads(form.badges_as_json()) == stored
