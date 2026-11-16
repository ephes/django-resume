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


def test_controls_stay_with_their_form(editor):
    result = editor.evaluate("""() => {
        document.body.replaceChildren();
        function make(label) {
            const owner = document.createElement('editable-form');
            owner.innerHTML = `<form><input id="badges" type="hidden" name="badges" value='["${label}"]'>
              <input name="one" data-field="one" type="hidden" value="on">
              <input name="two" type="hidden" value="on">
              <input name="edit_revision" type="hidden" value="${label}"></form>
              <input type="checkbox" data-field="one"><input type="checkbox" name="two">
              <badge-editor input-field-id="badges"></badge-editor><button type="submit">Save</button>`;
            document.body.append(owner);
            return owner;
        }
        const first = make('first'), second = make('second');
        for (let i = 0; i < 3; i++) {second.remove(); document.body.append(second);}
        const badge = second.querySelector('badge-editor');
        badge.querySelector('input').value = 'local';
        badge.querySelector('li:last-child button').click();
        badge.querySelector('.badge-delete-button').click();
        const form = second.querySelector('form');
        let submitted;
        form.addEventListener('submit', e => {e.preventDefault(); submitted = Object.fromEntries(new FormData(form));});
        form.requestSubmit();
        return {submitted, first: first.querySelector('[name=badges]').value};
    }""")
    assert result == {
        "submitted": {
            "badges": '["local"]',
            "one": "",
            "two": "",
            "edit_revision": "second",
        },
        "first": '["first"]',
    }


@pytest.mark.parametrize("method", ["click", "requestSubmit", "enter"])
def test_pending_badge_is_saved_or_refused_visibly(editor, method):
    editor.evaluate("""() => {
        const owner = document.querySelector('editable-form');
        const form = owner.querySelector('form');
        form.querySelector('[name=trigger]').value = 'synthetic';
        const hidden = document.createElement('input');
        Object.assign(hidden, {type: 'hidden', name: 'badges', id: 'badges', value: '["Stored"]'});
        form.append(hidden);
        const badge = document.createElement('badge-editor');
        badge.setAttribute('input-field-id', 'badges');
        owner.append(badge);
        window.badgeSubmissions = [];
        form.addEventListener('submit', e => {e.preventDefault(); badgeSubmissions.push(new FormData(form).get('badges'));});
    }""")
    pending = editor.get_by_placeholder("Add badge")
    pending.fill("Pending")
    if method == "click":
        editor.get_by_role("button", name="Save").click()
    elif method == "requestSubmit":
        editor.locator("form").evaluate("form => form.requestSubmit()")
    else:
        pending.press("Enter")
        editor.locator("form").evaluate("form => form.requestSubmit()")
    assert editor.evaluate("badgeSubmissions") == ['["Stored","Pending"]']
    expect(pending).to_have_value("")
    pending.fill("Stored")
    editor.locator("form").evaluate("form => form.requestSubmit()")
    assert editor.evaluate("badgeSubmissions") == ['["Stored","Pending"]']
    expect(pending).to_have_value("Stored")
    expect(editor.get_by_role("alert")).to_contain_text("already exists")


def test_badge_hydration_budget_preserves_the_source(editor):
    result = editor.evaluate("""() => {
        const owner = document.querySelector('editable-form'), form = owner.querySelector('form');
        const hidden = document.createElement('input');
        const value = JSON.stringify(Array(65).fill('x'.repeat(1024)));
        Object.assign(hidden, {type: 'hidden', name: 'badges', id: 'badges', value});
        form.append(hidden);
        const badge = document.createElement('badge-editor');
        badge.setAttribute('input-field-id', 'badges');
        owner.append(badge);
        return {preserved: hidden.value === value, count: badge.querySelectorAll('.badge-name').length};
    }""")
    assert result == {"preserved": True, "count": 0}
    expect(editor.get_by_role("alert")).to_contain_text("limits")


@pytest.mark.parametrize(
    "html,expected",
    [
        ("First<div>Second</div><div>Third</div>", "First\nSecond\nThird"),
        ("<p>First</p><p>Second</p>", "First\nSecond"),
        ("First<br>Second<br><br>Fourth", "First\nSecond\n\nFourth"),
        ("&lt;widget&gt;<div>&lt;/widget&gt;</div>", "<widget>\n</widget>"),
    ],
)
def test_plain_editor_structural_lines_reach_submission(editor, html, expected):
    editor.locator('[name="trigger"]').fill("synthetic")
    editor.locator("[contenteditable]").evaluate(
        "(field, html) => field.innerHTML = html", html
    )
    editor.locator("form").evaluate("form => form.requestSubmit()")
    assert editor.evaluate("submissions") == [expected]


def test_plain_editor_keyboard_enter_reaches_submission(editor):
    editor.locator('[name="trigger"]').fill("synthetic")
    field = editor.locator("[contenteditable]")
    field.fill("First")
    field.press("End")
    field.press("Enter")
    field.press_sequentially("<literal> Second")
    editor.get_by_role("button", name="Save").click()
    assert editor.evaluate("submissions") == ["First\n<literal> Second"]
