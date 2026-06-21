"""Capability-based section selection.

A page can pick the section plugins it renders by *capability tag* instead of
by explicit name or the ``"__all__"`` wildcard. Capabilities live on the
plugins (``Plugin.capabilities``); a page declares
``section_names = by_capability("portfolio")`` to include every plugin tagged
with that capability. Existing list/``"__all__"`` selection is unchanged.
"""

import pytest
from django.test import RequestFactory

from django_resume.pages.base import (
    ByCapability,
    ResumePage,
    build_section_context,
    by_capability,
)
from django_resume.plugins import (
    AboutPlugin,
    CoverPlugin,
    EducationPlugin,
    FreelanceTimelinePlugin,
    IdentityPlugin,
    ProjectsPlugin,
    SkillsPlugin,
    ThemePlugin,
    TokenPlugin,
)


def test_builtin_plugins_expose_capabilities():
    # Capabilities are static class attributes (asserted on the classes so the
    # test is independent of the mutable global registry's state). Content
    # sections carry capability tags; access/UI-control plugins carry none --
    # they are not selectable content.
    assert "portfolio" in IdentityPlugin.capabilities
    assert "portfolio" in AboutPlugin.capabilities
    assert "portfolio" in SkillsPlugin.capabilities
    assert "portfolio" in ProjectsPlugin.capabilities
    assert "cv" in EducationPlugin.capabilities
    assert "cv" in FreelanceTimelinePlugin.capabilities

    assert TokenPlugin.capabilities == ()
    assert ThemePlugin.capabilities == ()
    assert "portfolio" not in CoverPlugin.capabilities


def test_by_capability_factory_normalizes():
    selector = by_capability("portfolio")
    assert isinstance(selector, ByCapability)
    assert selector.capabilities == ("portfolio",)
    assert selector.match == "any"

    multi = by_capability("a", "b", match="all")
    assert multi.capabilities == ("a", "b")
    assert multi.match == "all"


def test_by_capability_matches_any_and_all():
    # "any": one shared capability is enough.
    assert by_capability("portfolio", "cover").matches(IdentityPlugin) is True
    assert by_capability("portfolio").matches(CoverPlugin) is False

    # "all": the plugin must carry every requested capability.
    assert by_capability("portfolio", "cv", match="all").matches(IdentityPlugin) is True
    assert (
        by_capability("portfolio", "cover", match="all").matches(IdentityPlugin)
        is False
    )


def test_by_capability_empty_matches_nothing():
    assert by_capability().matches(IdentityPlugin) is False


@pytest.mark.django_db
def test_build_section_context_by_capability(resume):
    resume.owner.save()
    resume.save()
    request = RequestFactory().get("/john-doe/")
    request.user = resume.owner

    context = build_section_context(request, resume, {}, by_capability("portfolio"))

    # The "portfolio" capability resolves to exactly these content sections.
    assert set(context) == {"identity", "about", "skills", "projects"}


@pytest.mark.django_db
def test_build_section_context_unknown_capability_is_empty(resume):
    resume.owner.save()
    resume.save()
    request = RequestFactory().get("/john-doe/")
    request.user = resume.owner

    context = build_section_context(
        request, resume, {}, by_capability("does-not-exist")
    )

    assert context == {}


@pytest.mark.django_db
def test_page_selects_sections_by_capability(resume):
    # A page (built-in or third-party) can drive section selection purely off
    # capabilities through the normal get_context path.
    resume.owner.save()
    resume.save()
    request = RequestFactory().get("/john-doe/")
    request.user = resume.owner

    class CvByCapabilityPage(ResumePage):
        url_name = "cv-cap"
        section_names = by_capability("cv")

    context = CvByCapabilityPage().get_context(request, resume, base_context={})

    # Every "cv"-tagged plugin is present; an untagged one (token) is not.
    assert {"identity", "about", "education", "skills"} <= set(context)
    assert "token" not in context


def test_by_capability_rejects_invalid_match():
    # A typo in ``match`` fails loudly rather than silently widening selection.
    with pytest.raises(ValueError):
        by_capability("portfolio", match="al")


@pytest.mark.django_db
def test_explicit_list_and_all_selection_unchanged(resume):
    # Regression guard: the existing selection modes still behave as before, and
    # "__all__" stays a strict superset of a capability-filtered selection.
    resume.owner.save()
    resume.save()
    request = RequestFactory().get("/john-doe/")
    request.user = resume.owner

    by_name = build_section_context(request, resume, {}, ["identity", "about"])
    assert set(by_name) == {"identity", "about"}

    all_sections = build_section_context(request, resume, {}, "__all__")
    portfolio = build_section_context(request, resume, {}, by_capability("portfolio"))
    # Every selected section becomes a context key (even plugins whose own
    # get_context returns ``{}``), so "__all__" includes the portfolio subset
    # and strictly more (cover, theme, ... are present too).
    assert {"identity", "about", "skills", "projects", "cover"} <= set(all_sections)
    assert set(portfolio) < set(all_sections)
