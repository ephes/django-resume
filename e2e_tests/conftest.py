import pytest
from playwright.sync_api import Page

from . import pages

TEST_USER = {
    "username": "playwright",
    "password": "password",
    "email": "playwright@example.com",
}


@pytest.fixture
def admin_index(base_url: str, page: Page) -> pages.AdminPage:
    username, password = TEST_USER["username"], TEST_USER["password"]
    admin_index = pages.AdminPage(
        base_url=base_url, username=username, password=password, page=page
    )
    admin_index.login()
    return admin_index
