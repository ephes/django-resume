import pytest
from django.urls import reverse

from django_resume.pages.base import ResumePage
from django_resume.pages.builtins import CoverLetterPage, CvPage, PermissionDeniedPage
from django_resume.templatetags.page_nav import page_nav_links


def test_base_page_nav_title_defaults_empty():
    assert ResumePage().nav_title == ""


@pytest.mark.django_db
def test_base_page_is_visible_default_true(resume):
    assert ResumePage().is_visible(resume) is True


@pytest.mark.django_db
def test_builtin_nav_titles_and_nav_url(resume):
    resume.owner.save()
    resume.save()

    assert CoverLetterPage().nav_title == "Cover"
    assert CvPage().nav_title == "CV"
    assert PermissionDeniedPage().nav_title == "403"

    assert CvPage().nav_url(resume) == reverse(
        "resume:cv", kwargs={"slug": resume.slug}
    )


@pytest.mark.django_db
def test_permission_denied_visibility_follows_token_requirement(resume):
    resume.owner.save()
    resume.save()
    # No token data -> a token is required by default -> the 403 editor is offered.
    assert PermissionDeniedPage().is_visible(resume) is True

    resume.plugin_data["token"] = {"flat": {"token_required": False}}
    resume.save()
    assert PermissionDeniedPage().is_visible(resume) is False


@pytest.mark.django_db
def test_page_nav_links_lists_visible_registered_pages(resume):
    resume.owner.save()
    resume.save()

    links = page_nav_links(resume)
    titles = [link["title"] for link in links]

    # Built-ins are registered in this order; 403 shows because a token is
    # required by default for a resume with no token data.
    assert titles == ["Cover", "CV", "403"]
    assert all(link["url"].startswith("/resume/") for link in links)
    assert {"title", "url"} <= set(links[0])


@pytest.mark.django_db
def test_page_nav_links_hides_token_gated_403_when_not_required(resume):
    resume.owner.save()
    resume.plugin_data["token"] = {"flat": {"token_required": False}}
    resume.save()

    titles = [link["title"] for link in page_nav_links(resume)]
    assert titles == ["Cover", "CV"]
