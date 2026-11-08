"""Regressions for restored data and template namespace boundaries."""

import pytest

from django_resume.formats.json_resume.importer import _validate_restored_plugin_data
from django_resume.pages import base as pages
from django_resume.plugins import base as plugins
from django_resume.plugins.about import AboutPlugin
from django_resume.plugins.theme import ThemeForm


@pytest.mark.parametrize(
    "name", ["../about/plain", "plain/../editorial", "a\\b", "a\x00b", ".", "", None, 1]
)
def test_invalid_theme_paths_fall_back_to_plain(name):
    assert (
        pages.page_template_name(name, "resume_detail.html")
        == "django_resume/pages/plain/resume_detail.html"
    )
    templates = plugins.ThemedTemplates(
        plugin_name="about", template_names={"main": "content.html"}
    )
    # Check construction as well as subsequent mutation of the public attribute.
    assert (
        templates.for_theme(name).main
        == "django_resume/plugins/about/plain/content.html"
    )
    templates.theme = name
    assert (
        templates.get_template_path("main")
        == "django_resume/plugins/about/plain/content.html"
    )


@pytest.mark.parametrize(
    "name",
    ["../about/plain", "plain/../editorial", "a\\b", "a\x00b", ".", "a b", "café"],
)
def test_theme_form_rejects_unsafe_names(name):
    assert not ThemeForm({"name": name}).is_valid()


@pytest.mark.parametrize("name", ["plain", "custom-theme_2", "UPPER"])
def test_safe_custom_theme_names(name):
    assert ThemeForm({"name": name}).is_valid()
    assert (
        _validate_restored_plugin_data(
            {"theme": {"name": name, "language": "de-at"}, "about": {"text": "Hello"}}
        )
        == []
    )
    assert f"/{name}/" in pages.page_template_name(name, "resume_detail.html")


@pytest.mark.parametrize(
    "plugin,field,value",
    [
        ("theme", "name", "../plain"),
        ("theme", "name", "a\x00b"),
        ("theme", "name", {}),
        ("theme", "name", ""),
        ("theme", "language", "../de"),
        ("theme", "language", "de/en"),
        ("theme", "language", "a\\b"),
        ("theme", "language", None),
        ("theme", "language", "de\x00"),
        ("about", "text", {}),
        ("about", "text", None),
        ("about", "text", 123),
    ],
)
@pytest.mark.django_db
def test_restore_rejects_semantically_invalid_fields(user, plugin, field, value):
    from django_resume.formats.json_resume.importer import import_resume_document
    from django_resume.models import Resume

    user.save()
    result = import_resume_document(
        {
            "basics": {"name": "Jane"},
            "meta": {"django_resume": {"plugin_data": {plugin: {field: value}}}},
        },
        owner=user,
        slug="invalid-restore",
    )
    assert result.resume is None
    assert any(
        f"{plugin}.{field}" in error for error in result.report.validation_errors
    )
    assert not Resume.objects.filter(slug="invalid-restore").exists()


def test_restore_allows_missing_fields_and_site_language():
    assert (
        _validate_restored_plugin_data({"theme": {"language": ""}, "about": {}}) == []
    )


@pytest.mark.parametrize("module", [pages, plugins])
@pytest.mark.parametrize("error", [OSError("unreadable"), ValueError("invalid path")])
def test_template_lookup_tolerates_invalid_or_unreadable_paths(
    monkeypatch, module, error
):
    def fail(name):
        raise error

    monkeypatch.setattr(module, "get_template", fail)
    assert not module._template_exists("invalid")


@pytest.mark.parametrize("text", [{}, None, 1])
def test_about_tolerates_legacy_non_string_text(text):
    context = AboutPlugin().get_context(None, {"text": text}, 1, context={})
    assert context["text_markdown"] == ""
    assert context["text_plain"] == ""


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name", ["../about/plain", "plain/../editorial", "a\x00b", None]
)
def test_legacy_invalid_theme_and_about_render_with_plain_fallback(
    client, resume, name
):
    from django.urls import reverse

    resume.owner.save()
    resume.plugin_data = {"theme": {"name": name}, "about": {"text": {}}}
    resume.save()
    response = client.get(reverse("resume:detail", kwargs={"slug": resume.slug}))
    assert response.status_code == 200
    assert "django_resume/pages/plain/resume_detail.html" in {
        t.name for t in response.templates
    }


@pytest.mark.parametrize(
    "name", ["../about/plain", "plain/../editorial", "a\x00b", None]
)
def test_timeline_template_override_confines_theme(name):
    from django_resume.plugins.timelines import TimelineThemedTemplates

    templates = TimelineThemedTemplates(theme=name)
    assert (
        templates.get_template_path("main")
        == "django_resume/plugins/timelines/plain/content.html"
    )
    templates.theme = name
    assert (
        templates.get_template_path("item")
        == "django_resume/plugins/timelines/plain/item.html"
    )


@pytest.mark.parametrize("error", [OSError("unreadable"), ValueError("invalid")])
def test_permission_denied_probe_tolerates_loader_errors(monkeypatch, error):
    from django_resume.plugins import permission_denied

    def fail(name):
        raise error

    monkeypatch.setattr(permission_denied, "get_template", fail)
    templates = permission_denied.PermissionDeniedTemplates(
        theme="editorial", plugin_name="permission_denied"
    )
    assert (
        templates.get_template_path("main")
        == "django_resume/plugins/permission_denied/plain/content.html"
    )
