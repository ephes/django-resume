import pytest
from django.test import override_settings


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="example.example.urls", LOGIN_URL="/admin/login/")
def test_example_root_redirects_anonymous_users_to_login(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.url == "/admin/login/?next=/resume/"


@pytest.mark.django_db
@override_settings(ROOT_URLCONF="example.example.urls", LOGIN_URL="/admin/login/")
def test_example_root_redirects_authenticated_users_to_resume_list(client, resume):
    resume.owner.save()
    client.force_login(resume.owner)

    response = client.get("/")

    assert response.status_code == 302
    assert response.url == "/resume/"
