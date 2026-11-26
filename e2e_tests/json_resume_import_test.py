"""Browser checks for the JSON Resume upload preview and confirmation flow."""

import json

from playwright.sync_api import expect

from django_resume.models import Resume


def test_stale_upload_confirmation_shows_conflict_and_allows_retry(
    logged_in_page, resume_list_url, tmp_path
):
    page = logged_in_page
    previewed = tmp_path / "previewed.json"
    previewed.write_text(json.dumps({"basics": {"name": "Synthetic Previewed"}}))
    changed = tmp_path / "changed.json"
    changed.write_text(json.dumps({"basics": {"name": "Synthetic Changed"}}))
    import_statuses = []
    page.on(
        "response",
        lambda response: (
            import_statuses.append(response.status)
            if response.request.method == "POST"
            else None
        ),
    )

    page.goto(resume_list_url)
    page.set_input_files("#json-resume-file", str(previewed))
    page.fill("#json-resume-slug", "synthetic-import")
    page.click('button[value="preview"]')
    expect(page.locator("#json-resume-import-preview")).to_be_visible()

    # htmx does not swap 4xx responses by default; the list template opts the
    # import form's 409 in so the retry message is visible.
    page.set_input_files("#json-resume-file", str(changed))
    page.click('button[value="create"]')
    expect(page.locator("#json-resume-import-form .error").first).to_contain_text(
        "does not match the previewed file"
    )
    assert import_statuses[-1] == 409
    assert not Resume.objects.filter(slug="synthetic-import").exists()

    page.set_input_files("#json-resume-file", str(previewed))
    page.click('button[value="preview"]')
    expect(page.locator("#json-resume-import-preview")).to_be_visible()
    page.set_input_files("#json-resume-file", str(previewed))
    page.click('button[value="create"]')
    expect(page.locator("#main-resumes-list")).to_contain_text(
        "Imported Synthetic Previewed"
    )
    assert import_statuses[-1] == 200
    assert Resume.objects.filter(slug="synthetic-import").count() == 1
