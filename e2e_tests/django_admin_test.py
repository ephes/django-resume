import pytest
from django.urls import reverse
from playwright.sync_api import Page, expect


def test_admin_index_page(logged_in_page: Page, admin_index_url: str):
    page = logged_in_page

    # Then the title should be "Site administration | Django site admin"
    expect(page).to_have_title("Site administration | Django site admin")
    # And there should be a "Resume" section
    assert page.locator("th#django_resume-resume").count() > 0


def remove_resume(page: Page, name: str) -> None:
    """Remove the resume with the given name."""
    page.click("th#django_resume-resume a")
    page.click(
        f'input.action-select[aria-label="Select this object for an action - {name}"]'
    )
    page.select_option('select[name="action"]', "delete_selected")
    page.click('button.button[title="Run the selected action"]')
    page.click('input[type="submit"][value="Yes, I’m sure"]')


def test_create_resume_via_admin(logged_in_page: Page, admin_index_url: str):
    page = logged_in_page
    page.goto(admin_index_url)

    # When I click on the "Resume" section
    page.click("th#django_resume-resume a")

    # And I click on the "Add Resume" button
    page.click("ul.object-tools a.addlink")

    # And I fill out the form
    page.fill('input[name="name"]', "John Doe")
    page.fill('input[name="slug"]', "john-doe")
    page.select_option('select[name="owner"]', label="playwright")

    # And I click on the "Save" button
    page.click('input[type="submit"]')

    # Then I should see a success message
    assert page.locator("li.success").count() > 0

    # And I should see the new resume in the list
    assert page.locator('th.field-__str__ a:has-text("John doe")').count() > 0

    # Remove the resume so the test can be run again
    remove_resume(page, "John Doe")


def create_resume(page: Page, name: str, slug: str, owner: str) -> None:
    """Create a resume with the given name, slug, and owner."""
    page.click("th#django_resume-resume a")
    page.click("ul.object-tools a.addlink")
    page.fill('input[name="name"]', name)
    page.fill('input[name="slug"]', slug)
    page.select_option('select[name="owner"]', label=owner)
    page.click('input[type="submit"]')


@pytest.fixture
def page_with_resume(logged_in_page: Page, admin_index_url: str) -> Page:
    page = logged_in_page
    page.goto(admin_index_url)
    create_resume(page, "John Doe", "john-doe", "playwright")
    page.click('th.field-__str__ a:has-text("John Doe")')
    yield page
    page.goto(admin_index_url)
    remove_resume(page, "John Doe")


def test_create_resume_cover_letter(
    page_with_resume: Page, admin_index_url: str, base_url: str
):
    # Given a resume exists and I am on the resume detail page
    page = page_with_resume

    # When I click on the "Edit Cover Letter" link
    page.click('a:has-text("Edit Cover Letter")')

    # And I fill out the form
    page.fill('input[name="title"]', "Some Cover Letter Title")
    page.fill("textarea#id_text", "Your cover letter content here")

    # And I click on the "Update" button
    page.click('button[type="submit"]:has-text("Update")')

    # Then if I go to the resume detail page
    resume_path = reverse("django_resume:detail", args=["john-doe"])
    resume_url = base_url + resume_path
    page.goto(resume_url)

    # Then I should see the cover letter title
    assert page.locator("h2:has-text('Some Cover Letter Title')").count() > 0

    # And I should see the cover letter content
    assert page.locator("p:has-text('Your cover letter content here')").count() > 0
