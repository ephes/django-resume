import pytest
from django.contrib.auth.models import User
from django.middleware.csrf import _get_new_csrf_string, _mask_cipher_secret
from django.test import Client

from django_resume.models import Resume
from django_resume.plugins import EmployedTimelinePlugin, plugin_registry


def item_ids(resume: Resume) -> list[str]:
    resume.refresh_from_db()
    plugin = EmployedTimelinePlugin()
    return [item["id"] for item in plugin.data.get_data(resume)["items"]]


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "head", "put", "patch"])
def test_inline_delete_rejects_other_methods(client, resume_with_timeline_item, method):
    # Given the owner is logged in and has a timeline item
    resume = resume_with_timeline_item
    client.force_login(resume.owner)
    url = EmployedTimelinePlugin().inline.get_delete_item_url(resume.pk, "123")

    # When the delete URL is requested with a method other than POST or DELETE
    r = getattr(client, method)(url)

    # Then the request is refused and the item survives
    assert r.status_code == 405
    assert item_ids(resume) == ["123"]


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["post", "delete"])
def test_inline_delete_by_owner(client, resume_with_timeline_item, method):
    resume = resume_with_timeline_item
    client.force_login(resume.owner)
    url = EmployedTimelinePlugin().inline.get_delete_item_url(resume.pk, "123")

    r = getattr(client, method)(url)

    assert r.status_code == 200
    assert item_ids(resume) == []


@pytest.mark.django_db
def test_inline_delete_by_other_user_is_forbidden(client, resume_with_timeline_item):
    # Given another logged-in user
    resume = resume_with_timeline_item
    other = User.objects.create_user(username="mallory", password="x")
    client.force_login(other)
    url = EmployedTimelinePlugin().inline.get_delete_item_url(resume.pk, "123")

    # When they try to delete the owner's item
    r = client.delete(url)

    # Then it is forbidden and the item survives
    assert r.status_code == 403
    assert item_ids(resume) == ["123"]


@pytest.mark.django_db
def test_inline_delete_requires_csrf_token(resume_with_timeline_item):
    # Given a client that enforces CSRF checks like a real browser request
    resume = resume_with_timeline_item
    client = Client(enforce_csrf_checks=True)
    client.force_login(resume.owner)
    url = EmployedTimelinePlugin().inline.get_delete_item_url(resume.pk, "123")

    # When the DELETE is sent without a CSRF token, it is rejected
    r = client.delete(url)
    assert r.status_code == 403
    assert item_ids(resume) == ["123"]

    # And with the token in the header htmx sends, the item is deleted
    secret = _get_new_csrf_string()
    client.cookies["csrftoken"] = secret
    r = client.delete(url, headers={"X-CSRFToken": _mask_cipher_secret(secret)})
    assert r.status_code == 200
    assert item_ids(resume) == []


@pytest.mark.django_db
@pytest.mark.parametrize("method", ["get", "put"])
def test_admin_delete_rejects_other_methods(
    admin_client, resume_with_timeline_item, method
):
    resume = resume_with_timeline_item
    admin_client.force_login(resume.owner)
    url = EmployedTimelinePlugin().admin.get_delete_item_url(resume.pk, "123")

    r = getattr(admin_client, method)(url)

    assert r.status_code == 405
    assert item_ids(resume) == ["123"]


@pytest.mark.django_db
def test_admin_delete_with_delete_method(admin_client, resume_with_timeline_item):
    resume = resume_with_timeline_item
    admin_client.force_login(resume.owner)
    url = EmployedTimelinePlugin().admin.get_delete_item_url(resume.pk, "123")

    r = admin_client.delete(url)

    assert r.status_code == 200
    assert item_ids(resume) == []


@pytest.mark.django_db
def test_post_views_reject_get(client, resume_with_timeline_item):
    # Mutating views only accept POST, so a GET (which skips CSRF) changes nothing
    resume = resume_with_timeline_item
    client.force_login(resume.owner)
    timeline = EmployedTimelinePlugin()
    about = plugin_registry.get_plugin("about")
    urls = [
        timeline.inline.get_post_item_url(resume.pk),
        timeline.inline.get_edit_flat_post_url(resume.pk),
        about.inline.get_post_url(resume.pk),
    ]
    for url in urls:
        assert client.get(url).status_code == 405, url
    assert item_ids(resume) == ["123"]
