import pytest
from django.urls import reverse

from django_resume.models import Resume
from django_resume.plugins import plugin_registry, TokenPlugin


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
    assert "django_resume/plain/resume_list.html" in set([t.name for t in r.templates])

    # And the resume list should be editable
    assert r.context["is_editable"]

    # And the resume should be in the context
    assert r.context["resumes"][0] == resume


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

    # When we access the cv page
    detail_url = reverse("resume:detail", kwargs={"slug": resume.slug})
    r = client.get(detail_url)

    # Then the response should be successful
    assert r.status_code == 200

    # And the cv template should be used
    assert "django_resume/plain/resume_detail.html" in set(
        [t.name for t in r.templates]
    )

    # And the resume should be in the context
    assert r.context["resume"] == resume


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
