import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.template.loader import render_to_string

from django_resume.plugins import plugin_registry
from django_resume.plugins.identity import IdentityForm


def test_identity_form_only_requires_name():
    # Given an identity form with nothing but a name
    form = IdentityForm(data={"name": "Jane Doe"})

    # Then the form is valid, every other field is optional
    assert form.is_valid(), form.errors
    assert all(
        not field.required for name, field in form.fields.items() if name != "name"
    )


def test_identity_form_rejects_missing_name():
    form = IdentityForm(data={})

    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.parametrize("theme", ["plain", "headwind"])
def test_identity_content_omits_empty_optional_fields(theme):
    # Given an identity that only has a name
    context = {"identity": {"name": "Jane Doe"}, "show_edit_button": False}

    # When the identity section is rendered
    html = render_to_string(
        f"django_resume/plugins/identity/{theme}/content.html", context
    )

    # Then no empty pronoun badge, location link or social link is rendered
    assert "Jane Doe" in html
    assert "pronoun-badges-list" not in html
    assert 'href=""' not in html
    assert "Mastodon" not in html


def test_identity_website_maps_to_json_resume_url(resume):
    from django_resume.plugins.identity import IdentityPlugin

    plugin = IdentityPlugin()
    plugin.data.set_data(
        resume, {"name": "Jane Doe", "website": "https://portfolio.example"}
    )
    adapter = plugin.get_export_adapters()["json_resume"]

    exported = adapter.export(plugin.get_structured_data(resume))

    assert ("/basics/url", "https://portfolio.example") in exported.contributions
    imported = adapter.import_data({"basics": {"url": "https://portfolio.example"}})
    assert imported.plugin_data["website"] == "https://portfolio.example"


@pytest.mark.parametrize("theme", ["plain", "headwind"])
def test_identity_content_links_website(theme):
    context = {
        "identity": {"name": "Jane Doe", "website": "https://portfolio.example"},
        "show_edit_button": False,
    }

    html = render_to_string(
        f"django_resume/plugins/identity/{theme}/content.html", context
    )

    assert 'href="https://portfolio.example"' in html
    assert 'aria-label="Website"' in html


@pytest.mark.parametrize("theme", ["plain", "headwind"])
def test_identity_does_not_render_dangerous_link_schemes(resume, theme):
    # Given identity data from an import that bypassed the form validation
    from django_resume.plugins.identity import IdentityPlugin

    plugin = IdentityPlugin()
    data = {
        "name": "Jane Doe",
        "website": "javascript:alert(document.domain)",
        "github": "JaVaScRiPt:alert(1)",
        "linkedin": "https://linkedin.example/jane",
    }

    # When the identity section is rendered
    context = plugin.get_context(None, data, 1, context={}, theme=theme)
    html = render_to_string(
        f"django_resume/plugins/identity/{theme}/content.html",
        {"identity": context, "show_edit_button": False},
    )

    # Then the dangerous links are dropped and safe ones are kept
    assert "javascript" not in html.lower()
    assert 'href="https://linkedin.example/jane"' in html
    assert data["website"] == "javascript:alert(document.domain)"


@pytest.mark.django_db
def test_identity_rejects_html_avatar_and_shows_error(
    client, resume, in_memory_storage
):
    # Given the owner editing the identity section
    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_registry.get_plugin("identity")

    # When an HTML file renamed to .png is uploaded as avatar
    upload = SimpleUploadedFile(
        "avatar.png",
        b"<html><script>alert(1)</script></html>",
        content_type="image/png",
    )
    response = client.post(
        plugin.inline.get_post_url(resume.pk), {"name": "Jane", "avatar_img": upload}
    )

    # Then the inline form shows the error and nothing is stored
    assert response.status_code == 200
    assert "Upload a valid image" in response.content.decode()
    resume.refresh_from_db()
    assert "identity" not in resume.plugin_data
