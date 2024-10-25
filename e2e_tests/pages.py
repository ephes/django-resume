"""
This module contains several page objects to store shared logic.
"""

from django.urls import reverse
from playwright.sync_api import Page


class AdminPage:
    def __init__(
        self, *, base_url: str, username: str, password: str, page: Page
    ) -> None:
        self.page = page
        self.base_url = base_url
        self.username = username
        self.password = password
        admin_url = reverse("admin:login")
        self.url = base_url + admin_url

    def login(self) -> None:
        self.page.goto(self.url)
        self.page.fill("#id_username", self.username)
        self.page.fill("#id_password", self.password)
        self.page.click('input[type="submit"][value="Log in"]')
