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

    def remove_resume(self, page: Page, name: str):
        """Remove the resume with the given name."""
        page.click("th#django_resume-resume a")
        page.click(
            f'input.action-select[aria-label="Select this object for an action - {name}"]'
        )
        page.select_option('select[name="action"]', "delete_selected")
        page.click('button.button[title="Run the selected action"]')
        page.click('input[type="submit"][value="Yes, I’m sure"]')
