import pytest
from playwright.sync_api import Page

from . import pages

TEST_USER = {
    "username": "playwright",
    "password": "password",
    "email": "playwright@example.com",
}


@pytest.fixture
def admin_index_page(base_url: str, page: Page) -> pages.AdminPage:
    username, password = TEST_USER["username"], TEST_USER["password"]
    return pages.AdminPage(
        base_url=base_url, username=username, password=password, page=page
    )
