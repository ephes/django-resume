"""Inline fragments render in the theme of the edited resume, not a shared one."""

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from django_resume.models import Resume
from django_resume.plugins import plugin_registry

TIMELINE_ITEM = {
    "id": "w1",
    "company_name": "Example Ltd",
    "company_url": "",
    "role": "Designer",
    "description": "Designed things.",
    "start": "2020",
    "end": "2024",
    "badges": '["Client A"]',
    "position": 0,
}


def used_templates(response) -> set[str]:
    return {template.name for template in response.templates if template.name}


@pytest.fixture
def themed_resumes(user):
    user.save()

    def create(slug: str, theme: str) -> Resume:
        item = {**TIMELINE_ITEM, "badges": ["Client A"]}
        return Resume.objects.create(
            name=slug,
            slug=slug,
            owner=user,
            plugin_data={
                "theme": {"name": theme},
                "token": {"flat": {"token_required": False}},
                "about": {"title": "About", "text": "Hello"},
                "employed_timeline": {"flat": {"title": "Work"}, "items": [item]},
            },
        )

    return create("editorial-cv", "editorial"), create("headwind-cv", "headwind")


@pytest.mark.django_db
def test_list_fragments_alternate_between_resume_themes(client, themed_resumes):
    client.force_login(User.objects.get())
    plugin = plugin_registry.get_plugin("employed_timeline")
    for _ in range(2):
        for resume, theme in zip(themed_resumes, ("editorial", "headwind")):
            prefix = f"django_resume/plugins/timelines/{theme}/"
            item_form = client.get(plugin.inline.get_edit_item_url(resume.pk, "w1"))
            assert f"{prefix}item_form.html" in used_templates(item_form)

            item = client.post(
                plugin.inline.get_post_item_url(resume.pk), TIMELINE_ITEM
            )
            assert f"{prefix}item.html" in used_templates(item)

            flat_form = client.get(plugin.inline.get_edit_flat_url(resume.pk))
            assert f"{prefix}flat_form.html" in used_templates(flat_form)

            flat = client.post(
                plugin.inline.get_edit_flat_post_url(resume.pk), {"title": "Work"}
            )
            assert f"{prefix}flat.html" in used_templates(flat)


@pytest.mark.django_db
def test_simple_fragments_alternate_between_resume_themes(client, themed_resumes):
    client.force_login(User.objects.get())
    plugin = plugin_registry.get_plugin("about")
    editorial, headwind = themed_resumes
    # rendering the other resume's page must not leak its theme into fragments
    client.get(reverse("resume:cv", kwargs={"slug": headwind.slug}), {"edit": "true"})
    for resume, theme in ((editorial, "editorial"), (headwind, "headwind")) * 2:
        prefix = f"django_resume/plugins/about/{theme}/"
        form = client.get(plugin.inline.get_edit_url(resume.pk))
        assert f"{prefix}form.html" in used_templates(form)

        main = client.post(
            plugin.inline.get_post_url(resume.pk), {"title": "About", "text": "Hi"}
        )
        assert f"{prefix}content.html" in used_templates(main)

        invalid = client.post(plugin.inline.get_post_url(resume.pk), {"title": ""})
        assert f"{prefix}form.html" in used_templates(invalid)


@pytest.mark.django_db
def test_page_render_does_not_change_shared_plugin_templates(client, themed_resumes):
    editorial, _ = themed_resumes
    plugin = plugin_registry.get_plugin("employed_timeline")

    response = client.get(reverse("resume:cv", kwargs={"slug": editorial.slug}))

    assert response.status_code == 200
    assert "django_resume/plugins/timelines/editorial/content.html" in used_templates(
        response
    )
    assert plugin.templates.theme == "plain"


@pytest.mark.django_db
def test_fragment_falls_back_to_plain_when_theme_lacks_it(client, themed_resumes):
    _, headwind = themed_resumes
    client.force_login(User.objects.get())
    plugin = plugin_registry.get_plugin("awards")

    response = client.get(plugin.inline.get_edit_item_url(headwind.pk))

    assert response.status_code == 200
    assert "django_resume/plugins/awards/plain/item_form.html" in used_templates(
        response
    )
