import pytest
from django.urls import reverse
from playwright.sync_api import Page, Browser


TEST_USER = {
    "username": "playwright",
    "password": "password",
    "email": "playwright@example.com",
}


@pytest.fixture
def admin_index_url(base_url: str) -> str:
    admin_path = reverse("admin:index")
    return base_url + admin_path


@pytest.fixture
def resume_list_url(base_url: str) -> str:
    list_path = reverse("django_resume:list")
    return base_url + list_path


@pytest.fixture(scope="session")
def save_auth_state(base_url: str, browser: Browser):
    page = browser.new_page()
    admin_login_path = reverse("admin:login")
    login_url = base_url + admin_login_path
    admin_index_path = reverse("admin:index")
    admin_index_url = base_url + admin_index_path
    page.goto(login_url)
    page.fill("#id_username", TEST_USER["username"])
    page.fill("#id_password", TEST_USER["password"])
    page.click('input[type="submit"][value="Log in"]')
    page.wait_for_url(admin_index_url)  # Wait until login is confirmed
    page.context.storage_state(path="auth.json")  # Save the authenticated state
    page.close()


@pytest.fixture
def logged_in_page(browser: Browser, save_auth_state, admin_index_url: str) -> Page:
    context = browser.new_context(storage_state="auth.json")  # Load the saved state
    page = context.new_page()
    page.goto(admin_index_url)
    yield page
    page.close()
    context.close()
