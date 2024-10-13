from django_resume.markdown import (
    markdown_to_html,
    textarea_input_to_markdown,
    markdown_to_textarea_input,
)


def test_markdown_textarea_input_to_markdown():
    # Given a textarea input with HTML
    textarea_input = "Some text<br>with a line break and a <div>div</div></div> foobar"
    # When the textarea input is converted to markdown
    text = textarea_input_to_markdown(textarea_input)
    # Then the markdown should contain a newline and no div elements
    assert text == "Some text\nwith a line break and a div foobar"


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


def test_markdown_link():
    # Given a markdown string with a link
    markdown = "Foobar baz [foobar](https://example.com) blub blah"

    # When the markdown is converted to HTML
    html = markdown_to_html(markdown)

    # Then the HTML should contain the correct elements
    assert '<a href="https://example.com">foobar</a>' in html
