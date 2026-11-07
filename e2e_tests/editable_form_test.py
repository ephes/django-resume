"""Synthetic editor checks: no server, accounts, uploaded fixtures or network."""

from pathlib import Path

import pytest
from playwright.sync_api import Browser, expect


@pytest.fixture(scope="session")
def base_url() -> None:
    # Override e2e_tests/conftest.py for pytest-base-url's autouse URL check.
    # These synthetic tests must not start a live server or a database.
    return None


@pytest.fixture
def editor(browser: Browser):
    page = browser.new_page()
    page.set_content("""
        <editable-form>
          <form id="editor">
            <input type="hidden" name="title" data-field="title" value="old">
            <input name="trigger" required>
            <input type="file" name="avatar">
          </form>
          <div contenteditable="true" data-field="title">new &amp; text</div>
          <img class="editable-avatar" data-field="avatar" src="data:image/png;base64,b2xk">
          <button type="submit">Save</button>
        </editable-form>
        <script>
          window.submissions = [];
          // Register before component upgrade, as HTMX can do on swapped forms.
          document.querySelector('form').addEventListener('submit', event => {
            event.preventDefault();
            submissions.push(new FormData(event.target).get('title'));
          });
        </script>
    """)
    page.add_script_tag(
        path=str(
            Path(__file__).parents[1]
            / "src/django_resume/static/django_resume/js/edit.js"
        )
    )
    yield page
    page.close()


@pytest.mark.parametrize("method", ["click", "enter", "requestSubmit"])
def test_native_submit_serializes_current_text_once(editor, method):
    def submit():
        if method == "click":
            editor.get_by_role("button", name="Save").click()
        elif method == "enter":
            editor.locator('[name="trigger"]').press("Enter")
        else:
            editor.locator("form").evaluate("form => form.requestSubmit()")

    submit()
    assert editor.evaluate("submissions") == []  # Native required-field validation.
    editor.locator('[name="trigger"]').fill("synthetic")
    submit()
    assert editor.evaluate("submissions") == ["new & text"]


@pytest.mark.parametrize("failure", [None, "construct", "add", "assign"])
def test_drop_preview_matches_the_submitted_file(editor, failure):
    result = editor.evaluate(
        """async failure => {
            const input = document.querySelector('[type=file]');
            const preview = document.querySelector('img');
            const old = new File(['old'], 'old.png', {type: 'image/png'});
            const dropped = new File(['new'], 'new.png', {type: 'image/png'});
            const initial = new DataTransfer();
            initial.items.add(old);
            input.files = initial.files;
            const transfer = new DataTransfer();
            transfer.items.add(dropped);
            const event = new DragEvent('drop', {bubbles: true, cancelable: true, dataTransfer: transfer});
            if (failure === 'construct') window.DataTransfer = class {constructor() {throw new Error('synthetic');}};
            if (failure === 'add') window.DataTransfer = class {items = {add() {throw new Error('synthetic');}}};
            if (failure === 'assign') Object.defineProperty(input, 'files', {
                get: () => initial.files, set() {throw new Error('synthetic');}
            });
            preview.dispatchEvent(event);
            const submitted = new FormData(document.querySelector('form')).get('avatar');
            return {name: submitted.name, contents: await submitted.text(), exact: input.files[0] === dropped};
        }""",
        failure,
    )
    if failure:
        assert result == {"name": "old.png", "contents": "old", "exact": False}
        expect(editor.locator("img")).to_have_attribute(
            "src", "data:image/png;base64,b2xk"
        )
        expect(editor.get_by_role("status")).to_contain_text("file picker")
    else:
        assert result == {"name": "new.png", "contents": "new", "exact": True}
        expect(editor.locator("img")).to_have_attribute(
            "src", "data:image/png;base64,bmV3"
        )
