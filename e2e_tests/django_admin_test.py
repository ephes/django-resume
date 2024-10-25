from playwright.sync_api import Page, expect

from .pages import AdminPage


def test_admin_index_page(page: Page, admin_index: AdminPage):
    # Then the title should be "Site administration | Django site admin"
    expect(page).to_have_title("Site administration | Django site admin")

    # And there should be a "Resume" section
    assert page.locator("th#django_resume-resume").count() > 0


def test_create_resume_via_admin(page: Page, admin_index: AdminPage):
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
    admin_index.remove_resume(page, "John Doe")
