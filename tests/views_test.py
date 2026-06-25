import json
import re

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from django_resume.formats.json_resume.importer import MAX_INPUT_BYTES
from django_resume.models import Resume
from django_resume.plugins import plugin_registry, TokenPlugin


def anchor_with_attrs(content, href, *attrs):
    lookaheads = "".join(rf"(?=[^>]*\b{re.escape(attr)})" for attr in attrs)
    return re.search(
        rf"<a\b(?=[^>]*\bhref=\"{re.escape(href)}\"){lookaheads}[^>]*>", content
    )


def json_resume_upload(document, *, name="resume.json"):
    return SimpleUploadedFile(
        name,
        json.dumps(document).encode("utf-8"),
        content_type="application/json",
    )


@pytest.mark.django_db
def test_get_resume_list_view(client, resume):
    # Given a resume in the database
    resume.owner.save()
    resume.save()

    # When we access the resume list page without being authenticated
    r = client.get(reverse("resume:list"))

    # Then the response should be a redirect to the login page
    assert r.status_code == 302
    assert "login" in r.url

    # When we access the resume list page being authenticated
    client.force_login(resume.owner)
    r = client.get(reverse("resume:list"))

    # Then the response should be successful
    assert r.status_code == 200

    # And the list template should be used
    assert "django_resume/pages/plain/resume_list.html" in set(
        [t.name for t in r.templates]
    )

    # And the resume list should be editable
    assert r.context["is_editable"]

    # And the resume should be in the context
    assert r.context["resumes"][0] == resume

    content = r.content.decode("utf-8")
    detail_url = reverse("resume:detail", kwargs={"slug": resume.slug})
    cv_url = reverse("resume:cv", kwargs={"slug": resume.slug})
    permission_denied_url = reverse("resume:403", kwargs={"slug": resume.slug})
    assert anchor_with_attrs(content, detail_url, 'hx-boost="true"')
    assert anchor_with_attrs(content, cv_url, 'hx-boost="true"')
    assert anchor_with_attrs(content, permission_denied_url, 'hx-boost="true"')
    assert reverse("resume:json-resume-import") in content
    assert 'hx-encoding="multipart/form-data"' in content


@pytest.mark.django_db
def test_post_resume_list_view(client, django_user_model):
    # Given a user in the database
    test_user = django_user_model.objects.create_user(username="test", password="test")

    # When we access the resume list page not being authenticated
    r = client.post(reverse("resume:list"), {"name": "test", "slug": "test"})

    # Then the response should be a redirect to the login page
    assert r.status_code == 302
    assert "login" in r.url

    # When we access the resume list page being authenticated
    client.login(username="test", password="test")
    r = client.post(reverse("resume:list"), {"name": "testname", "slug": "test-slug"})

    # Then the response should be successful
    assert r.status_code == 200

    # And the new resume should be sent back in the context
    assert r.context["new_resume"].name == "testname"

    # And the list of resumes should contain the new resume
    assert r.context["resumes"][0].name == "testname"

    # And the new resume should be in the database
    assert test_user.resume_set.get().name == "testname"

    # And the html sent back should be only a snippet of main-resume-list.html
    content = r.content.decode("utf-8")
    assert content.startswith("<main")

    # When we post a resume with an invalid slug
    r = client.post(reverse("resume:list"), {"name": "testname", "slug": "test slug"})

    # Then the response should be successful
    assert r.status_code == 200

    # And the form should have an error
    content = r.content.decode("utf-8")
    assert "Enter a valid “slug”" in content


@pytest.mark.django_db
def test_import_json_resume_view_creates_resume(client, django_user_model):
    user = django_user_model.objects.create_user(username="test", password="test")
    client.login(username="test", password="test")

    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "file": json_resume_upload(
                {"basics": {"name": "Browser Jane", "email": "jane@example.com"}}
            ),
            "slug": "browser-jane",
        },
    )

    assert response.status_code == 200
    imported = Resume.objects.get(slug="browser-jane")
    assert imported.owner == user
    assert imported.name == "Browser Jane"
    content = response.content.decode("utf-8")
    assert content.startswith("<main")
    assert "Imported Browser Jane." in content
    assert "Mapped plugins:" in content


@pytest.mark.django_db
def test_import_json_resume_view_creates_resume_from_url(
    client, django_user_model, monkeypatch
):
    user = django_user_model.objects.create_user(username="test", password="test")
    client.login(username="test", password="test")

    def load_document_url(url):
        assert url == "https://example.com/resume.json"
        return {"basics": {"name": "URL Jane", "email": "jane@example.com"}}

    monkeypatch.setattr("django_resume.views.load_document_url", load_document_url)

    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "source_url": "https://example.com/resume.json",
            "slug": "url-jane",
        },
    )

    assert response.status_code == 200
    imported = Resume.objects.get(slug="url-jane")
    assert imported.owner == user
    assert imported.name == "URL Jane"
    assert "Imported URL Jane." in response.content.decode("utf-8")


@pytest.mark.django_db
def test_import_json_resume_view_requires_exactly_one_source(client, django_user_model):
    django_user_model.objects.create_user(username="test", password="test")
    client.login(username="test", password="test")

    missing_response = client.post(
        reverse("resume:json-resume-import"),
        {"slug": "missing-source"},
    )
    assert missing_response.status_code == 200
    assert "Provide either a JSON Resume file or a JSON Resume URL." in (
        missing_response.content.decode("utf-8")
    )

    both_response = client.post(
        reverse("resume:json-resume-import"),
        {
            "file": json_resume_upload({"basics": {"name": "Browser Jane"}}),
            "source_url": "https://example.com/resume.json",
            "slug": "both-sources",
        },
    )
    assert both_response.status_code == 200
    assert "Provide either a JSON Resume file or a JSON Resume URL." in (
        both_response.content.decode("utf-8")
    )
    assert not Resume.objects.filter(
        slug__in=["missing-source", "both-sources"]
    ).exists()


@pytest.mark.django_db
def test_import_json_resume_view_requires_login(client):
    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "file": json_resume_upload({"basics": {"name": "Browser Jane"}}),
            "slug": "browser-jane",
        },
    )

    assert response.status_code == 302
    assert "login" in response.url


@pytest.mark.django_db
def test_import_json_resume_view_restores_round_trip_plugin_data(
    client, django_user_model
):
    django_user_model.objects.create_user(username="test", password="test")
    client.login(username="test", password="test")

    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "file": json_resume_upload(
                {
                    "basics": {"name": "Round Trip Jane"},
                    "meta": {
                        "django_resume": {
                            "plugin_data": {
                                "token": {"flat": {"token_required": False}}
                            }
                        }
                    },
                }
            ),
            "slug": "round-trip-jane",
        },
    )

    assert response.status_code == 200
    imported = Resume.objects.get(slug="round-trip-jane")
    assert imported.plugin_data["token"] == {"flat": {"token_required": False}}
    content = response.content.decode("utf-8")
    assert "Restored plugins: token." in content


@pytest.mark.django_db
def test_import_json_resume_view_portable_only_ignores_round_trip_plugin_data(
    client, django_user_model
):
    django_user_model.objects.create_user(username="test", password="test")
    client.login(username="test", password="test")

    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "file": json_resume_upload(
                {
                    "basics": {"name": "Portable Jane"},
                    "meta": {
                        "django_resume": {
                            "plugin_data": {
                                "token": {"flat": {"token_required": False}}
                            }
                        }
                    },
                }
            ),
            "slug": "portable-jane",
            "portable_only": "on",
        },
    )

    assert response.status_code == 200
    imported = Resume.objects.get(slug="portable-jane")
    assert "token" not in imported.plugin_data
    content = response.content.decode("utf-8")
    assert "did not store source JSON Resume document" in content


@pytest.mark.django_db
def test_import_json_resume_view_surfaces_duplicate_slug(client, django_user_model):
    user = django_user_model.objects.create_user(username="test", password="test")
    Resume.objects.create(name="Existing", slug="existing", owner=user)
    client.login(username="test", password="test")

    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "file": json_resume_upload({"basics": {"name": "Browser Jane"}}),
            "slug": "existing",
        },
    )

    assert response.status_code == 200
    assert Resume.objects.filter(slug="existing").count() == 1
    content = response.content.decode("utf-8")
    assert "A resume with slug &#x27;existing&#x27; already exists" in content


@pytest.mark.django_db
def test_import_json_resume_view_surfaces_invalid_json(client, django_user_model):
    django_user_model.objects.create_user(username="test", password="test")
    client.login(username="test", password="test")
    upload = SimpleUploadedFile(
        "resume.json", b'{"basics": ', content_type="application/json"
    )

    response = client.post(
        reverse("resume:json-resume-import"),
        {"file": upload, "slug": "invalid-json"},
    )

    assert response.status_code == 200
    assert not Resume.objects.filter(slug="invalid-json").exists()
    assert "Invalid JSON:" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_import_json_resume_view_rejects_oversize_before_reading(
    client, django_user_model
):
    django_user_model.objects.create_user(username="test", password="test")
    client.login(username="test", password="test")
    upload = SimpleUploadedFile(
        "resume.json", b" " * (MAX_INPUT_BYTES + 1), content_type="application/json"
    )

    response = client.post(
        reverse("resume:json-resume-import"),
        {"file": upload, "slug": "oversize-json"},
    )

    assert response.status_code == 200
    assert not Resume.objects.filter(slug="oversize-json").exists()
    content = response.content.decode("utf-8")
    assert f"Input exceeds maximum size of {MAX_INPUT_BYTES} bytes" in content


@pytest.mark.django_db
def test_import_json_resume_view_attaches_imported_name_errors_to_name_field(
    client, django_user_model
):
    django_user_model.objects.create_user(username="test", password="test")
    client.login(username="test", password="test")

    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "file": json_resume_upload({"basics": {"name": "J" * 256}}),
            "slug": "overlong-imported-name",
        },
    )

    assert response.status_code == 200
    assert not Resume.objects.filter(slug="overlong-imported-name").exists()
    form = response.context["import_form"]
    assert "Resume name exceeds maximum length" in form.errors["name"][0]
    assert "file" not in form.errors


@pytest.mark.django_db
def test_import_json_resume_view_surfaces_schema_errors(client, django_user_model):
    django_user_model.objects.create_user(username="test", password="test")
    client.login(username="test", password="test")

    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "file": json_resume_upload(
                {"basics": {"name": "Browser Jane"}, "work": "not an array"}
            ),
            "slug": "schema-error",
        },
    )

    assert response.status_code == 200
    assert not Resume.objects.filter(slug="schema-error").exists()
    assert "work: &#x27;not an array&#x27; is not of type &#x27;array&#x27;" in (
        response.content.decode("utf-8")
    )


@pytest.mark.django_db
def test_import_json_resume_view_attaches_url_schema_errors_to_url_field(
    client, django_user_model, monkeypatch
):
    django_user_model.objects.create_user(username="test", password="test")
    client.login(username="test", password="test")
    monkeypatch.setattr(
        "django_resume.views.load_document_url",
        lambda _url: {"basics": {"name": "URL Jane"}, "work": "not an array"},
    )

    response = client.post(
        reverse("resume:json-resume-import"),
        {
            "source_url": "https://example.com/resume.json",
            "slug": "url-schema-error",
        },
    )

    assert response.status_code == 200
    assert not Resume.objects.filter(slug="url-schema-error").exists()
    form = response.context["import_form"]
    assert "work: 'not an array' is not of type 'array'" in form.errors["source_url"]
    assert "file" not in form.errors


@pytest.mark.django_db
def test_delete_resume_view(client, resume, django_user_model):
    # Given a resume in the database
    resume.owner.save()
    resume.save()

    # When we access the delete resume page without being authenticated
    delete_url = reverse("resume:delete", kwargs={"slug": resume.slug})
    r = client.delete(delete_url)

    # Then the response should be a redirect to the login page
    assert r.status_code == 302
    assert "login" in r.url

    # When we access the delete resume page being authenticated as a different user
    test_user = django_user_model.objects.create_user(username="test", password="test")
    client.login(username=test_user.username, password="test")
    r = client.delete(delete_url)

    # Then the response should be a 403
    assert r.status_code == 403

    # When we access the delete resume page being authenticated as the owner
    client.force_login(resume.owner)
    r = client.delete(delete_url)

    # Then the response should be successful
    assert r.status_code == 200

    # And the resume should be removed from the database
    assert Resume.objects.filter(slug=resume.slug).count() == 0


@pytest.mark.django_db
def test_resume_detail_view(client, resume):
    # Given a resume in the database
    resume.owner.save()
    resume.save()

    # When we access the cover page
    detail_url = reverse("resume:detail", kwargs={"slug": resume.slug})
    r = client.get(detail_url)

    # Then the response should be successful
    assert r.status_code == 200

    # And the cover template should be used
    assert "django_resume/pages/plain/resume_detail.html" in set(
        [t.name for t in r.templates]
    )

    # And the resume should be in the context
    assert r.context["resume"] == resume

    # And the CV link should not be in the content (token is required by default)
    cv_link = reverse("resume:cv", kwargs={"slug": resume.slug})
    content = r.content.decode("utf-8")
    assert cv_link not in content

    # Given a resume where the token is not required
    resume.plugin_data[TokenPlugin.name] = {"flat": {"token_required": False}}
    resume.save()

    # When we access the cover page
    r = client.get(detail_url)

    # Then the response should be successful
    assert r.status_code == 200

    # And the CV link should be in the content
    content = r.content.decode("utf-8")
    assert cv_link in content


@pytest.mark.django_db
def test_resume_detail_anonymous_cv_link_is_not_htmx_boosted(client, resume):
    # Given a public CV and an anonymous user
    resume.owner.save()
    resume.plugin_data[TokenPlugin.name] = {"flat": {"token_required": False}}
    resume.save()

    # When the anonymous user opens the cover page
    detail_url = reverse("resume:detail", kwargs={"slug": resume.slug})
    r = client.get(detail_url)

    # Then the CV link keeps normal-link behavior without HTMX boosting
    cv_link = reverse("resume:cv", kwargs={"slug": resume.slug})
    content = r.content.decode("utf-8")
    assert anchor_with_attrs(content, cv_link)
    assert not anchor_with_attrs(content, cv_link, 'hx-boost="true"')


@pytest.mark.django_db
def test_resume_detail_owner_cv_link_is_htmx_boosted(client, resume):
    # Given a public CV whose owner is logged in
    resume.owner.save()
    resume.plugin_data[TokenPlugin.name] = {"flat": {"token_required": False}}
    resume.save()
    client.force_login(resume.owner)

    # When the owner opens the cover page
    detail_url = reverse("resume:detail", kwargs={"slug": resume.slug})
    r = client.get(detail_url)

    # Then the CV navigation keeps normal-link fallback and adds HTMX boosting
    cv_link = reverse("resume:cv", kwargs={"slug": resume.slug})
    content = r.content.decode("utf-8")
    assert anchor_with_attrs(content, cv_link, 'hx-boost="true"')


@pytest.mark.django_db
def test_headwind_resume_detail_owner_loads_htmx_for_boosted_links(client, resume):
    # Given a headwind resume whose owner is logged in
    resume.owner.save()
    resume.plugin_data["theme"] = {"name": "headwind"}
    resume.plugin_data[TokenPlugin.name] = {"flat": {"token_required": False}}
    resume.save()
    client.force_login(resume.owner)

    # When the owner opens the cover page outside edit mode
    detail_url = reverse("resume:detail", kwargs={"slug": resume.slug})
    r = client.get(detail_url)

    # Then headwind loads HTMX for boosted owner navigation
    cv_link = reverse("resume:cv", kwargs={"slug": resume.slug})
    content = r.content.decode("utf-8")
    assert "htmx.org" in content
    assert "@media print" in content
    assert anchor_with_attrs(content, cv_link, 'hx-boost="true"')


@pytest.mark.django_db
def test_resume_cv_about_renders_sanitized_markdown(client, resume):
    # Given a resume using the headwind theme and markdown in the about plugin
    resume.owner.save()
    resume.plugin_data = {
        "theme": {"name": "headwind"},
        "token": {"flat": {"token_required": False}},
        "about": {
            "title": "About",
            "text": "**Bold** [profile](javascript:alert(1)) <script>alert(1)</script>",
        },
    }
    resume.save()

    # When we access the CV page
    cv_url = reverse("resume:cv", kwargs={"slug": resume.slug})
    r = client.get(cv_url)

    # Then the about section should render sanitized markdown
    assert r.status_code == 200
    assert "text" not in r.context["about"]
    assert (
        r.context["about"]["text_markdown"]
        == "**Bold** [profile](javascript:alert(1)) <script>alert(1)</script>"
    )
    assert r.context["about"]["text_plain"] == "Bold profile"
    assert "<strong>Bold</strong>" in r.context["about"]["text_html"]
    assert "alert(1)" not in r.context["about"]["text_html"]
    assert "javascript:" not in r.context["about"]["text_html"]
    content = r.content.decode("utf-8")
    assert "<strong>Bold</strong>" in content
    assert 'href="javascript:' not in content
    assert ">profile</a>" in content


@pytest.mark.django_db
def test_get_cv_view(client, resume):
    # Given a resume in the database and the token plugin activated
    resume.owner.save()
    resume.save()
    plugin_registry.register(TokenPlugin)

    # When we access the cv page without a token
    cv_url = reverse("resume:cv", kwargs={"slug": resume.slug})
    r = client.get(cv_url)

    # Then the response should be a 403
    assert r.status_code == 403
    assert r["Referrer-Policy"] == "no-referrer"

    # With a custom error message
    content = r.content.decode("utf-8")
    assert "Access Token Needed for CV" in content

    # When we access the cv page with a token
    token = "testtoken"
    resume.plugin_data["token"] = {"items": [{"token": token}]}
    resume.save()
    r = client.get(f"{cv_url}?token={token}")

    # Then the response should be successful
    assert r.status_code == 200
    assert r["Referrer-Policy"] == "no-referrer"


@pytest.mark.django_db
def test_public_cv_response_does_not_set_token_referrer_policy(client, resume):
    resume.owner.save()
    resume.plugin_data["token"] = {"flat": {"token_required": False}}
    resume.save()
    plugin_registry.register(TokenPlugin)

    cv_url = reverse("resume:cv", kwargs={"slug": resume.slug})
    r = client.get(cv_url)

    assert r.status_code == 200
    assert r.get("Referrer-Policy") != "no-referrer"


@pytest.mark.django_db
def test_cv_permission_denied_message_renders_sanitized_markdown(client, resume):
    # Given a resume with markdown in the permission denied plugin
    resume.owner.save()
    resume.plugin_data["permission_denied"] = {
        "title": "Access Token Needed for CV",
        "sub_title": "Unlock access",
        "email": "tokensupport@example.com",
        "text": "[email me](javascript:alert(1))\n\n**Thanks** <script>alert(1)</script>",
    }
    resume.save()
    plugin_registry.register(TokenPlugin)

    # When we access the cv without a token
    cv_url = reverse("resume:cv", kwargs={"slug": resume.slug})
    r = client.get(cv_url)

    # Then the rendered error message should use sanitized markdown
    assert r.status_code == 403
    assert "<strong>Thanks</strong>" in r.context["permission_denied"]["text"]
    assert "alert(1)" not in r.context["permission_denied"]["text"]
    assert "javascript:" not in r.context["permission_denied"]["text"]
    assert "email me" in r.context["permission_denied"]["text"]
    content = r.content.decode("utf-8")
    assert "<strong>Thanks</strong>" in content
    assert "alert(1)" not in content
    assert "javascript:" not in content
    assert "email me" in content


@pytest.mark.django_db
def test_cv_editable_only_for_authenticated_users(client, resume):
    # Given a resume in the database and the token plugin deactivated
    resume.owner.save()
    resume.save()
    plugin_registry.unregister(TokenPlugin)

    # When we access the cv page
    cv_url = reverse("resume:cv", kwargs={"slug": resume.slug})
    r = client.get(cv_url)

    # Then the response should be successful
    assert r.status_code == 200

    # And the edit buttons should not be shown
    assert not r.context["is_editable"]
    assert not r.context["show_edit_button"]

    # When we access the cv url being authenticated
    client.force_login(resume.owner)
    r = client.get(cv_url)

    # Then the response should be successful
    assert r.status_code == 200

    # And the global edit button should be shown but not the local ones
    assert r.context["is_editable"]
    assert not r.context["show_edit_button"]

    # When we access the cv edit url
    cv_edit_url = f"{cv_url}?edit=true"
    r = client.get(cv_edit_url)

    # Then the response should be successful
    assert r.status_code == 200

    # And the local edit buttons should be shown
    assert r.context["show_edit_button"]
