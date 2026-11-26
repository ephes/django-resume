import pytest

from django_resume.markdown import (
    markdown_to_html,
    markdown_to_plain_text,
    textarea_input_to_markdown,
    textarea_input_to_html,
    markdown_to_textarea_input,
    underlined_link_handler,
)


def test_markdown_textarea_input_to_markdown():
    # Given a textarea input with HTML
    textarea_input = "Some text<br>with a line break and a <div>div</div></div> foobar"
    # When the textarea input is converted to markdown
    text = textarea_input_to_markdown(textarea_input)
    # Then the markdown should contain a newline and no div elements
    assert text == "Some text\nwith a line break and a \ndiv foobar"


def test_markdown_to_textarea_input():
    # Given a markdown string containing a newline
    markdown = "Some text\nwith a line break"
    # When the markdown is converted to a textarea input
    textarea_input = markdown_to_textarea_input(markdown)
    # Then the textarea input should contain a <br> element
    assert textarea_input == "Some text<br>with a line break"


def test_markdown_heading():
    # Given a markdown string with a heading
    markdown = "## Foobar"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the HTML should contain the correct elements
    assert "<h2>Foobar</h2>" in html


def test_markdown_strips_script_tags():
    # Given markdown with an embedded script tag
    markdown = "Hello<script>alert(1)</script>World"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the script tag and its contents should be removed
    assert html == "HelloWorld"


def test_markdown_link():
    # Given a markdown string with a link
    markdown = "Foobar baz [foobar](https://example.com) blub blah"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)
    print("html", html)

    # Then the HTML should contain the correct elements
    assert '<a href="https://example.com"' in html
    assert ">foobar</a>" in html
    assert 'rel="noopener noreferrer"' in html


def test_markdown_link_blocks_javascript_protocols():
    # Given a markdown string with a dangerous link
    markdown = "[foobar](javascript:alert(1))"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the href should be removed by the sanitizer
    assert "javascript:" not in html
    assert "href=" not in html
    assert ">foobar</a>" in html


def test_markdown_link_blocks_percent_encoded_javascript_protocols():
    # Given a markdown string with a percent-encoded dangerous link
    markdown = "[foobar](javascript%3Aalert(1))"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the href should be removed by the sanitizer
    assert "javascript%3A" not in html
    assert "href=" not in html
    assert ">foobar</a>" in html


def test_markdown_link_blocks_data_protocols():
    # Given a markdown string with a data URL
    markdown = "[foobar](data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==)"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the href should be removed by the sanitizer
    assert "data:" not in html
    assert "href=" not in html
    assert ">foobar</a>" in html


def test_markdown_with_customized_link():
    # Given a markdown string with a link
    markdown = "Foobar baz [foobar](https://example.com) blub blah"

    # When the markdown is converted to HTML with a custom link handler
    def link_handler(text, url):
        return f'<a href="{url}" target="_blank">{text}</a>'

    html = markdown_to_html(markdown, handlers={"link": link_handler})

    # Then the HTML should contain the correct elements
    assert '<a href="https://example.com" target="_blank"' in html
    assert ">foobar</a>" in html
    assert 'rel="noopener noreferrer"' in html


def test_markdown_with_underlined_link_handler_blocks_javascript_protocols():
    # Given markdown with a dangerous link using the shared handler
    markdown = "[foobar](javascript:alert(1))"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown, handlers={"link": underlined_link_handler})

    # Then the sanitizer should strip the href and class should remain if allowed
    assert "javascript:" not in html
    assert '<a class="underlined"' in html
    assert ">foobar</a>" in html


def test_markdown_with_newlines_to_html():
    # Given a markdown string with a newline
    markdown = "Some text\nwith a line break"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the HTML should contain the correct elements
    assert "Some text<br>with a line break" in html


def test_markdown_keeps_benign_formatting():
    # Given markdown with the supported formatting
    markdown = "# Heading\n**Bold** and *italic* with [link](mailto:test@example.com)"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the supported tags should survive sanitization
    assert html == (
        "<h1>Heading</h1><br><strong>Bold</strong> and <em>italic</em> "
        'with <a href="mailto:test@example.com" rel="noopener noreferrer">link</a>'
    )


def test_textarea_input_to_html_escapes_text_and_keeps_line_breaks():
    # Given editor input with line breaks, structural markup and escaped
    # literal markup
    textarea_input = (
        "Line 1<br><script>alert(1)</script>\nLine 2 &lt;b&gt; &amp; &lt;br&gt;"
    )

    # When the editor input is prepared for a contenteditable field
    html = textarea_input_to_html(textarea_input)

    # Then only line breaks are markup; literal text stays escaped
    assert html == "Line 1<br>alert(1)<br>Line 2 &lt;b&gt; &amp; &lt;br&gt;"


@pytest.mark.parametrize(
    "stored",
    [
        "R&D <3\u00a0team",
        "Use <br> here",
        "Use &lt;tag&gt; here",
        "<em>literal</em>\n\n<script>alert(1)</script>",
        "a < b > c &amp;amp; d",
    ],
)
def test_editor_input_roundtrip_is_lossless(stored):
    # Unchanged saves from the admin textarea (the encoded value itself) and
    # from the inline editor (the escaped display HTML read back as innerHTML)
    editor_input = markdown_to_textarea_input(stored)
    assert textarea_input_to_markdown(editor_input) == stored
    display = textarea_input_to_html(editor_input)
    assert "<script" not in display and "<em" not in display
    assert textarea_input_to_markdown(display) == stored
    # ... and again, without accumulating or losing escaping
    assert textarea_input_to_markdown(markdown_to_textarea_input(stored)) == stored


@pytest.mark.parametrize("line_ending", ["\r\n", "\r"], ids=["crlf", "cr"])
def test_legacy_line_endings_survive_editor_and_render_as_lf(line_ending):
    source = "# Heading\nIntro\n\n- one\n- two\n\n- three\n- four\n\nOutro"
    stored = source.replace("\n", line_ending)
    editor_input = markdown_to_textarea_input(stored)
    reopened = textarea_input_to_markdown(textarea_input_to_html(editor_input))

    assert reopened == stored
    assert markdown_to_html(reopened) == markdown_to_html(source)
    assert markdown_to_plain_text(reopened) == (
        "Heading\nIntro\n\none\ntwo\n\nthree\nfour\n\nOutro"
    )


def test_markdown_to_plain_text_removes_markdown_markup():
    # Given markdown with headings and links
    markdown = "# Heading\n**Bold** [link](https://example.com)"

    # When the markdown is converted to plain text
    text = markdown_to_plain_text(markdown)

    # Then only the readable text should remain
    assert text == "Heading\nBold link"


def test_markdown_bullet_list_with_unicode_marker():
    # Given consecutive lines prefixed with the bullet glyph
    markdown = "• one\n• two\n• three"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then a real list with the markers stripped is produced
    assert html == "<ul><li>one</li><li>two</li><li>three</li></ul>"


def test_markdown_dash_and_asterisk_list_markers():
    # Given lines using the standard markdown list markers
    assert markdown_to_html("- one\n- two") == "<ul><li>one</li><li>two</li></ul>"
    assert markdown_to_html("* one\n* two") == "<ul><li>one</li><li>two</li></ul>"


def test_markdown_list_surrounded_by_text():
    # Given a paragraph, a list, then another paragraph
    markdown = "Intro\n- one\n- two\nOutro"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the block list sits between the text without stray <br> glue
    assert html == "Intro<ul><li>one</li><li>two</li></ul>Outro"


def test_markdown_list_item_keeps_inline_formatting():
    # Given a list item with inline markup
    markdown = "- **bold** and [link](https://example.com)"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the inline formatting survives inside the <li>
    assert "<li><strong>bold</strong> and " in html
    assert '<a href="https://example.com"' in html
    assert "</li></ul>" in html


def test_markdown_to_plain_text_lists_keep_line_breaks():
    # Given a markdown list
    markdown = "- one\n- two"

    # When converted to plain text
    text = markdown_to_plain_text(markdown)

    # Then each item stays on its own line
    assert text == "one\ntwo"


def test_markdown_italic_line_is_not_treated_as_list():
    # Given an italic line that starts with an asterisk (no marker space)
    markdown = "*italic*"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then it stays a normal emphasised line, not a list
    assert html == "<em>italic</em>"


def test_markdown_asterisk_list_item_with_emphasis_stays_a_list():
    # Given asterisk list items that also contain emphasis
    markdown = "* one *emphasis*\n* two"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the markers are list markers, not the start of an italic span
    assert html == "<ul><li>one <em>emphasis</em></li><li>two</li></ul>"


def test_markdown_to_plain_text_keeps_boundary_before_list():
    assert markdown_to_plain_text("Intro\n- one\n- two\nOutro") == (
        "Intro\none\ntwo\nOutro"
    )


def test_editor_entities_roundtrip_through_about_form_and_export():
    from django_resume.plugins.about import AboutForm, AboutJsonResumeAdapter

    inner_html = (
        "<div>R&amp;D &lt;3&nbsp;team</div>"
        "<div>&lt;em&gt;literal&lt;/em&gt;<br>&amp;lt;tag&amp;gt;</div>"
        "<div>&lt;script&gt;alert(1)&lt;/script&gt;</div>"
    )
    expected = (
        "R&D <3\u00a0team\n<em>literal</em>\n&lt;tag&gt;\n<script>alert(1)</script>"
    )
    form = AboutForm(data={"title": "About", "text": inner_html})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["text"] == expected
    exported = AboutJsonResumeAdapter().export({"summary": form.cleaned_data["text"]})
    assert exported.contributions == [("/basics/summary", expected)]
    # Unchanged saves: the inline editor submits the escaped display HTML, the
    # admin textarea submits the encoded initial value as is.
    edit_form = AboutForm(initial={"title": "About", "text": expected})
    for unchanged in (edit_form.text_display_html, edit_form["text"].value()):
        again = AboutForm(data={"title": "About", "text": unchanged})
        assert again.is_valid()
        assert again.cleaned_data["text"] == expected
    assert "<script>" not in markdown_to_html(expected)


def test_editor_text_length_limit_applies_to_decoded_text():
    from django_resume.plugins.about import AboutForm

    # Given stored text exactly at the limit whose encoding is longer
    stored = "A" * 1020 + "&<>&"
    assert len(stored) == 1024
    edit_form = AboutForm(initial={"title": "About", "text": stored})
    assert len(edit_form["text"].value()) > 1024
    assert "maxlength" not in str(edit_form["text"])

    # When it is saved unchanged from the admin textarea or the inline editor
    for unchanged in (edit_form["text"].value(), edit_form.text_display_html):
        form = AboutForm(data={"title": "About", "text": unchanged})

        # Then it is accepted and stored unchanged
        assert form.is_valid(), form.errors
        assert form.cleaned_data["text"] == stored

    # And one more stored character is rejected, however it is encoded
    for too_long in (stored + "B", markdown_to_textarea_input(stored + "&")):
        form = AboutForm(data={"title": "About", "text": too_long})
        assert not form.is_valid()
        assert "at most 1024 characters" in str(form.errors["text"])


def test_markdown_unmatched_link_work_is_bounded():
    import subprocess
    import sys

    # A generous process deadline avoids machine-sensitive ratio assertions.
    # Both failed labels and failed nested URL candidates must finish linearly.
    subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from django_resume.markdown import markdown_to_html; "
                "inputs = ['[' * 100000, '[' * 80000 + '](' + '(' * 80000]; "
                "assert all(markdown_to_html(text) == text for text in inputs)"
            ),
        ],
        timeout=5,
        check=True,
        capture_output=True,
    )


def test_markdown_render_input_ceiling(monkeypatch):
    from django_resume import markdown

    monkeypatch.setattr(markdown, "MAX_MARKDOWN_CHARS", 8, raising=False)
    assert markdown.markdown_to_html("é" * 8) == "é" * 8
    with pytest.raises(ValueError, match="Markdown input"):
        markdown.markdown_to_html("é" * 9)
    with pytest.raises(ValueError, match="Markdown input"):
        markdown.markdown_to_plain_text("x" * 9)


@pytest.mark.parametrize(
    "text",
    [
        "[label](https://example.com/path_(part)?x=1&y=2)",
        "[outer [inner]](https://example.com/a(b)c(d))",
        r"\[escaped](https://example.com/a%20b#anchor)",
        "[**bold** *italic*](mailto:synthetic@example.com)",
        "[empty]() [next](relative/path)",
        "[bad](a(b(c))) [good](https://example.com)",
        "[first\nsecond](https://example.com)",
        "[bad](broken( [label](ok)",
    ],
)
def test_markdown_link_subset_compatibility(text):
    import re
    from django_resume.markdown import sanitize_html

    # Compatibility oracle for this project's deliberately small link syntax.
    formatted = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)
    formatted = re.sub(r"\*(.*?)\*", r"<em>\1</em>", formatted)
    expected = re.sub(
        r"\[(.*?)\]\(((?:[^()]|\([^()]*\))*)\)",
        lambda match: f'<a href="{match[2]}">{match[1]}</a>',
        formatted,
    ).replace("\n", "<br>")
    assert markdown_to_html(text) == sanitize_html(expected)


def test_editor_unmatched_html_tag_work_is_bounded():
    import subprocess
    import sys

    # Includes interpreter startup; the former suffix-rescanning regex takes
    # tens of seconds for this admitted input. No tight timing ratios.
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from django_resume.markdown import textarea_input_to_markdown; "
            "text = '<' * 250000; "
            "assert textarea_input_to_markdown(text) == text",
        ],
        timeout=5,
        check=True,
        capture_output=True,
    )


@pytest.mark.parametrize(
    "source,expected",
    [
        ("a<>b<<x>c<unfinished", "a<>bc<unfinished"),
        ("a<DIV>b<BR />c</DIV>d", "a\nb\ncd"),
        ("&lt;div&gt;&amp;lt;br&amp;gt;", "<div>&lt;br&gt;"),
    ],
)
def test_editor_tag_scan_compatibility(source, expected):
    assert textarea_input_to_markdown(source) == expected


@pytest.mark.django_db
def test_attributed_divs_keep_line_boundaries_in_reopened_editor(client, resume):
    from django_resume.plugins import plugin_registry
    from tests.editor_helpers import post_current_editor

    resume.owner.save()
    resume.save()
    client.force_login(resume.owner)
    inline = plugin_registry.get_plugin("about").inline
    response = post_current_editor(
        client,
        inline.get_post_url(resume.pk),
        {
            "title": "Synthetic",
            "text": (
                '<DIV class="pasted">First <em>line</em></DIV>'
                "<div data-label='2 > 1'>Second &lt;div&gt; &amp;lt;div&amp;gt;</div>"
            ),
        },
    )
    assert response.status_code == 200
    resume.refresh_from_db()
    assert resume.plugin_data["about"]["text"] == "First line\nSecond <div> &lt;div&gt;"

    editor = client.get(inline.get_edit_url(resume.pk))
    assert editor.status_code == 200
    assert b"First line<br>Second &lt;div&gt; &amp;lt;div&amp;gt;" in editor.content


def test_editor_encoded_input_ceiling_precedes_conversion(monkeypatch):
    from django_resume import markdown

    def unexpected(*args, **kwargs):
        pytest.fail("conversion ran before input admission")

    monkeypatch.setattr(markdown.html, "unescape", unexpected)
    with pytest.raises(ValueError, match="2097152"):
        markdown.textarea_input_to_markdown("x" * (2 * 1024 * 1024 + 1))


def test_editor_encoded_input_exact_ceiling():
    assert textarea_input_to_markdown("x" * (2 * 1024 * 1024)) == "x" * (
        2 * 1024 * 1024
    )


@pytest.mark.parametrize("surface", ["admin", "inline"])
@pytest.mark.parametrize("plugin_name", ["about", "cover"])
@pytest.mark.django_db
def test_oversized_editor_submission_preserves_saved_content(
    client, resume, surface, plugin_name
):
    from tests.editor_helpers import post_current_editor
    from django_resume.plugins import plugin_registry

    resume.owner.is_staff = True
    resume.owner.save()
    original = {
        "about": {"title": "Synthetic", "text": "Original"},
        "cover": {
            "items": [
                {"id": "first", "title": "Synthetic", "text": "Original", "position": 0}
            ]
        },
    }
    resume.plugin_data = original
    resume.save()
    client.force_login(resume.owner)
    plugin = plugin_registry.get_plugin(plugin_name)
    if plugin_name == "about":
        url = (
            plugin.admin.get_change_post_url(resume.pk)
            if surface == "admin"
            else plugin.inline.get_post_url(resume.pk)
        )
    else:
        url = (
            plugin.admin.get_change_item_post_url(resume.pk)
            if surface == "admin"
            else plugin.inline.get_post_item_url(resume.pk)
        )
    response = post_current_editor(
        client,
        url,
        {"id": "first", "position": 0, "title": "Synthetic", "text": "<x>" * 699051},
    )
    assert response.status_code == 200
    assert "2097152" in response.content.decode()
    resume.refresh_from_db()
    assert resume.plugin_data == original


def test_cover_encoded_valid_length_boundary(resume):
    from django_resume.plugins.cover import CoverItemForm

    for count in (4096, 4097):
        form = CoverItemForm(
            data={
                "title": "Synthetic",
                "text": "&CounterClockwiseContourIntegral;" * count,
                "position": 0,
            },
            resume=resume,
            existing_items=[],
        )
        assert form.is_valid() == (count == 4096)
        if count == 4096:
            assert form.cleaned_data["text"] == "∳" * count


def test_editor_input_ceiling_counts_whitespace_before_stripping():
    from django_resume.plugins.about import AboutForm

    form = AboutForm(data={"title": "Synthetic", "text": " " * (2 * 1024 * 1024) + "x"})
    assert not form.is_valid()
    assert "2097152" in str(form.errors["text"])


@pytest.mark.parametrize("marker", ["#", "# \t"])
@pytest.mark.parametrize(
    "following, expected",
    [
        ("Prose", "<br>Prose"),
        ("- Item", "<ul><li>Item</li></ul>"),
        ("## Heading", "<br><h2>Heading</h2>"),
    ],
)
def test_empty_markdown_heading_keeps_the_next_source_line(marker, following, expected):
    assert markdown_to_html(f"{marker}\n{following}") == "<h1></h1>" + expected
