import re
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from django_resume.plugins import plugin_registry
from django_resume.plugins.cover import CoverFlatForm

from .conftest import png_bytes


LETTER_DETAILS = {
    "title": "Application",
    "recipient": "Example Corp\nHiring Team\nMain Street 1\n12345 Example City",
    "place_date": "Example City, 2026-01-01",
    "subject": "Application as Senior Designer",
    "salutation": "Dear hiring team,",
    "closing": "Best regards",
    "signature_name": "Jane Doe",
}


def test_cover_flat_form_context_carries_letter_details():
    context = CoverFlatForm.set_context(
        {**LETTER_DETAILS, "signature_img": ""}, {"edit_flat_url": "#"}
    )

    cover = context["cover"]
    assert cover["subject"] == "Application as Senior Designer"
    assert cover["place_date"] == "Example City, 2026-01-01"
    assert "Main Street 1" in cover["recipient"]
    assert cover["salutation"] == "Dear hiring team,"
    assert cover["closing"] == "Best regards"
    assert cover["signature_name"] == "Jane Doe"
    assert cover["signature_img_url"] == ""


def test_cover_flat_form_defaults_closing():
    assert CoverFlatForm().fields["closing"].initial == "Kind regards"


@pytest.mark.django_db
@pytest.mark.parametrize("theme", ["plain", "headwind"])
def test_cover_flat_form_template_posts_letter_details(client, resume, theme):
    resume.owner.save()
    resume.plugin_data = {
        "theme": {"name": theme},
        "cover": {"flat": dict(LETTER_DETAILS)},
    }
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_registry.get_plugin("cover")

    response = client.get(plugin.inline.get_edit_flat_url(resume.pk))

    content = response.content.decode()
    for field in ("recipient", "place_date", "subject", "salutation", "closing"):
        assert f'name="{field}"' in content
    assert 'name="signature_name"' in content
    assert "Application as Senior Designer" in content


@pytest.mark.django_db
def test_cover_signature_upload_without_avatar_is_kept_on_next_save(
    client, resume, in_memory_storage
):
    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_registry.get_plugin("cover")
    url = plugin.inline.get_edit_flat_post_url(resume.pk)

    # When a signature is uploaded on a cover letter without an avatar
    response = client.post(
        url,
        {
            **LETTER_DETAILS,
            "signature_img": SimpleUploadedFile(
                "signature.png", png_bytes(12, 4), content_type="image/png"
            ),
        },
    )

    # Then the upload is stored with its own dimensions
    assert response.status_code == 200
    resume.refresh_from_db()
    flat = resume.plugin_data["cover"]["flat"]
    assert re.fullmatch(r"uploads/[0-9a-f]{32}\.png", flat["signature_img"])
    assert (flat["signature_img_width"], flat["signature_img_height"]) == (12, 4)
    assert flat["closing"] == "Best regards"

    # And saving the letter again without a new upload keeps the signature
    client.post(url, {**LETTER_DETAILS, "subject": "Updated subject"})
    resume.refresh_from_db()
    flat = resume.plugin_data["cover"]["flat"]
    assert flat["subject"] == "Updated subject"
    assert re.fullmatch(r"uploads/[0-9a-f]{32}\.png", flat["signature_img"])


@pytest.mark.django_db
def test_cover_admin_flat_save_keeps_signature(client, resume, in_memory_storage):
    # Given a cover letter with a stored signature image
    resume.owner.is_staff = True
    resume.owner.is_superuser = True
    resume.owner.save()
    client.force_login(resume.owner)
    resume.plugin_data = {
        "cover": {
            "flat": {
                **LETTER_DETAILS,
                "signature_img": "uploads/signature.png",
                "avatar_img": "uploads/avatar.png",
            }
        }
    }
    resume.save()
    plugin = plugin_registry.get_plugin("cover")

    # When the flat data is saved in the Django admin without a new upload
    response = client.post(
        plugin.admin.get_change_flat_post_url(resume.pk),
        {**LETTER_DETAILS, "signature_name": "J. Doe"},
    )

    # Then both stored images are kept
    assert response.status_code == 200
    resume.refresh_from_db()
    flat = resume.plugin_data["cover"]["flat"]
    assert flat["signature_name"] == "J. Doe"
    assert flat["signature_img"] == "uploads/signature.png"
    assert flat["avatar_img"] == "uploads/avatar.png"


@pytest.mark.django_db
def test_cover_rejects_svg_signature_upload(client, resume, in_memory_storage):
    # Given the owner editing a cover letter
    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_registry.get_plugin("cover")
    url = plugin.inline.get_edit_flat_post_url(resume.pk)

    # When an SVG with a script is uploaded under an image name
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'
    response = client.post(
        url,
        {
            **LETTER_DETAILS,
            "signature_img": SimpleUploadedFile(
                "signature.png", svg, content_type="image/png"
            ),
        },
    )

    # Then the form is shown again with an error and nothing is stored
    assert response.status_code == 200
    assert "Upload a valid image" in response.context["form"].errors["signature_img"][0]
    resume.refresh_from_db()
    assert "signature_img" not in resume.plugin_data.get("cover", {}).get("flat", {})


@pytest.mark.django_db
def test_cover_shows_error_when_replacing_avatar_with_svg(
    client, resume, in_memory_storage
):
    # Given a cover letter with a stored avatar
    resume.plugin_data = {
        "cover": {"flat": {**LETTER_DETAILS, "avatar_img": "uploads/avatar.png"}}
    }
    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_registry.get_plugin("cover")

    # When the avatar is replaced with an SVG
    response = client.post(
        plugin.inline.get_edit_flat_post_url(resume.pk),
        {
            **LETTER_DETAILS,
            "avatar_img": SimpleUploadedFile(
                "avatar.svg", b"<svg></svg>", content_type="image/svg+xml"
            ),
        },
    )

    # Then the rendered form shows the validation error and the avatar is kept
    assert "Upload a valid image" in response.content.decode()
    resume.refresh_from_db()
    assert resume.plugin_data["cover"]["flat"]["avatar_img"] == "uploads/avatar.png"
