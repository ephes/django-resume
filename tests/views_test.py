import pytest
from django.urls import reverse

from django_resume.plugins import plugin_registry, TokenPlugin


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
