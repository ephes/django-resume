import os

# Playwright's sync API keeps an event loop on the main thread, which trips
# Django's async-safety guard when pytest-django sets up / tears down the test
# database on that same thread. The database work here is genuinely synchronous,
# so opt out of the guard for the live-server browser tests.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

import pytest  # noqa: E402
from django.urls import reverse  # noqa: E402
from playwright.sync_api import Browser  # noqa: E402


TEST_USER = {
    "username": "playwright",
    "password": "password",
    "email": "playwright@example.com",
}


@pytest.fixture(scope="session")
def base_url(live_server) -> str:
    """Point the browser tests at pytest-django's live server instead of an
    externally started development server (pytest-base-url's ``base_url``)."""
    return live_server.url


@pytest.fixture
def admin_index_url(base_url: str) -> str:
    admin_path = reverse("admin:index")
    return base_url + admin_path


@pytest.fixture
def resume_list_url(base_url: str) -> str:
    list_path = reverse("django_resume:list")
    return base_url + list_path


@pytest.fixture
def test_user(transactional_db, django_user_model):
    """The superuser the browser logs in as; committed so the live server sees it."""
    return django_user_model.objects.create_superuser(**TEST_USER)


@pytest.fixture
def logged_in_page(browser: Browser, test_user, base_url: str, admin_index_url: str):
    context = browser.new_context()
    page = context.new_page()
    page.goto(base_url + reverse("admin:login"))
    page.fill("#id_username", TEST_USER["username"])
    page.fill("#id_password", TEST_USER["password"])
    page.click('input[type="submit"][value="Log in"]')
    page.wait_for_url(admin_index_url)  # Wait until login is confirmed
    yield page
    page.close()
    context.close()
