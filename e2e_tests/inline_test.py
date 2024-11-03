import pytest

from playwright.sync_api import Page


def test_resume_list_page(logged_in_page: Page, resume_list_url: str):
    # Given I am logged in on the admin index page
    page = logged_in_page

    # When I go to the resume list page
    page.goto(resume_list_url)

    # Then the title should be "My Resumes"
    assert page.locator("h1:has-text('My Resumes')").count() > 0


def remove_resume(page: Page, slug: str) -> None:
    """Remove the resume with the given slug."""
    delete_button = page.locator(f"#resume-{slug} .resume-delete-button")
    delete_button.click()
    page.wait_for_selector("#resume-john-doe", state="detached")


def remove_uploads() -> None:
    """Remove all uploaded files."""
    import shutil
    import os

    shutil.rmtree("e2e_tests/media", ignore_errors=True)
    os.makedirs("e2e_tests/media", exist_ok=True)


def test_create_resume_via_list_page(logged_in_page: Page, resume_list_url: str):
    # Given I am logged in on the admin index page
    page = logged_in_page
    page.goto(resume_list_url)

    # When I fill out the form and click the "Create Resume" button
    page.fill('input[name="name"]', "John Doe")
    page.fill('input[name="slug"]', "john-doe")

    page.click('button[type="submit"]')

    # Then the resume should be created
    page.wait_for_selector("#resume-john-doe", state="visible")
    resume_item = page.locator("#resume-john-doe")

    # Check for the existence of the "Cover" link
    cover_link = resume_item.locator("a.underlined[href='/resume/john-doe/']")
    assert cover_link.is_visible(), "Cover link not found"

    # Check for the existence of the "CV" link
    cv_link = resume_item.locator("a.underlined[href='/resume/john-doe/cv/']")
    assert cv_link.is_visible(), "CV link not found"

    # Remove the resume so the test can be run again
    remove_resume(page, "john-doe")


def create_resume(page: Page, name: str, slug: str) -> None:
    """Create a resume with the given name and slug."""
    page.fill('input[name="name"]', name)
    page.fill('input[name="slug"]', slug)
    page.click('button[type="submit"]')


@pytest.fixture
def page_with_resume(logged_in_page: Page, resume_list_url: str) -> Page:
    page = logged_in_page
    page.goto(resume_list_url)
    create_resume(page, "John Doe", "john-doe")
    yield page
    page.goto(resume_list_url)
    remove_resume(page, "john-doe")
    remove_uploads()


def test_create_resume_cover_letter_inline(
    page_with_resume: Page, admin_index_url: str, base_url: str
):
    # Given a resume exists and I am on the resume detail page
    page = page_with_resume

    # When I click on the "Edit Cover Letter" link
    page.click("a.underlined[href='/resume/john-doe/']")

    # And I click on the "Edit Mode" checkbox
    checkbox = page.locator("#edit-mode")
    checkbox.click()

    # And I click on the flat form "Edit" button
    edit_button = page.locator(".edit-icon-h1")
    edit_button.click()

    # And I fill out the inline form
    page.locator('[contenteditable="true"][data-field="title"]').fill("New Cover Title")
    page.locator('svg.avatar.editable-avatar[data-field="avatar_img"]').click()
    page.set_input_files("#avatar-img", "e2e_tests/fixtures/bartleby-cover.webp")
    page.wait_for_selector(
        'img.avatar.editable-avatar[data-field="avatar_img"]', state="visible"
    )
    page.locator('[contenteditable="true"][data-field="avatar_alt"]').fill(
        "New profile photo description"
    )
    page.locator("#submit-cover").click()
    page.wait_for_selector("#cover-flat", state="attached")

    # Then I should see the new cover letter title, avatar, and avatar alt text
    assert page.locator("h1:has-text('New Cover Title')").is_visible()
    assert page.locator("img[alt='New profile photo description']").is_visible()

    # When I click on the "Add Item" button
    page.locator(".edit-icon-small[hx-target='#cover-items'] use[href='#add']").click()

    # And I fill out the inline form
    page.locator('[contenteditable="true"][data-field="title"]').fill(
        "New Cover Item Title"
    )
    page.locator('[contenteditable="true"][data-field="text"][data-type="html"]').fill(
        "New cover paragraph content..."
    )

    # And I click on the "Ok" button
    page.locator('[id^="cover-submit-item-"]').click()

    # Then I should see the new cover item
    assert page.locator("h3:has-text('Cover item title')").is_visible()
    assert page.locator("p:has-text('Cover paragraph content...')").is_visible()


def test_create_resume_cv_inline(
    page_with_resume: Page, admin_index_url: str, base_url: str
):
    # Given a resume exists and I am on the resume detail page
    page = page_with_resume

    # When I click on the "Edit CV" link
    page.click("a.underlined[href='/resume/john-doe/cv/']")

    # And I click on the "Edit Mode" checkbox
    checkbox = page.locator("#edit-mode")
    checkbox.click()

    # And I click on the timeline "Edit" button
    page.locator("#freelance_timeline .edit-icon-small").first.click()

    # And I fill out the inline form and submit it
    page.locator('input.editable-h2[name="title"]').fill("New Timeline Title")
    page.locator('button[type="submit"]').click()

    # Then I should see the new timeline title
    assert page.locator("h2:has-text('New Timeline Title')").is_visible()

    # When I click on the "Add Item" button
    page.locator("#add-freelance_timeline-icon").click()

    # And I fill out the inline form and submit it
    page.locator('[contenteditable="true"][data-field="company_name"]').fill(
        "New Company Name"
    )
    page.locator('button[type="submit"]').click()

    # Then I should see the new timeline item
    assert page.locator("h3:has-text('New Company Name')").is_visible()
