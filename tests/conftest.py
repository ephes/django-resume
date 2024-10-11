import pytest

from django_resume.models import Resume


@pytest.fixture
def user(django_user_model):
    return django_user_model(username="testuser", password="password")


@pytest.fixture
def resume(user):
    return Resume(name="John Doe", slug="john-doe", owner=user)


@pytest.fixture
def timeline_item_data():
    return {
        "role": "Software Developer",
        "company_name": "ACME Inc.",
        "company_url": "https://example.org",
        "description": "I did some stuff",
        "start": "2020",
        "end": "2022",
        "badges": '["remote", "full-time"]',
        "position": 1,
    }
