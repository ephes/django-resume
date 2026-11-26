import html

from bs4 import BeautifulSoup
from django.urls import reverse
import pytest

from django_resume.markdown import markdown_to_html, underlined_link_handler


DESTINATIONS = [
    "https://example.test/a*b*c",
    "https://example.test/a**b**c?x=1&copy;=2&y=3",
    'https://example.test/path" target="_blank',
    "https://example.test/a'b(c)d(e)?q=é&n=2",
    "mailto:synthetic+*cv*@example.test?subject=R&D",
    "relative/path\nnext",
    "relative/path\n# heading\n- list",
    "https://example.test/<em>literal</em>?x=&quot;",
]


@pytest.mark.parametrize("url", DESTINATIONS)
@pytest.mark.parametrize("underlined", [False, True])
def test_builtin_links_keep_literal_destinations_and_formatted_labels(url, underlined):
    handlers = {"link": underlined_link_handler} if underlined else None
    rendered = markdown_to_html(f"[**CV** *link*]({url})", handlers=handlers)
    document = BeautifulSoup(rendered, "html.parser")
    [anchor] = document.find_all("a")
    expected = {"href": url, "rel": ["noopener", "noreferrer"]}
    if underlined:
        expected["class"] = ["underlined"]
    assert anchor.attrs == expected
    assert anchor.decode_contents() == "<strong>CV</strong> <em>link</em>"


def test_custom_link_handler_receives_raw_destination_and_formatted_label():
    received = []
    url = 'https://example.test/a*b*c?x="yes"&copy;=2'

    def render(label, destination):
        received.append((label, destination))
        return f'<a href="{html.escape(destination, quote=True)}">{label}</a>'

    rendered = markdown_to_html(f"[**CV**]({url})", handlers={"link": render})
    assert received == [("<strong>CV</strong>", url)]
    assert BeautifulSoup(rendered, "html.parser").a["href"] == url


def test_custom_list_handler_receives_rendered_links():
    received = []

    def render(items):
        received.extend(items)
        return "<ul>" + "".join(f"<li>{item}</li>" for item in items) + "</ul>"

    rendered = markdown_to_html(
        "- [**CV**](https://example.test/a*b*c)", handlers={"list": render}
    )
    assert len(received) == 1
    anchor = BeautifulSoup(received[0], "html.parser").a
    assert anchor["href"] == "https://example.test/a*b*c"
    assert anchor.strong.get_text() == "CV"
    assert BeautifulSoup(rendered, "html.parser").li.a["href"] == anchor["href"]


def test_formatting_handlers_keep_original_markdown_arguments():
    received = []
    url = "https://example.test/a*b*c"

    def heading(level, content):
        received.append(("heading", level, content))
        return f"<h{level}>{content}</h{level}>"

    def bold(content):
        received.append(("bold", content))
        return f"<strong>{content}</strong>"

    def italic(content):
        received.append(("italic", content))
        return f"<em>{content}</em>"

    source = f"# **[CV]({url})** *[More]({url})*"
    rendered = markdown_to_html(
        source, handlers={"heading": heading, "bold": bold, "italic": italic}
    )
    assert received == [
        ("heading", 1, source[2:]),
        ("bold", f"[CV]({url})"),
        ("italic", f"[More]({url})"),
    ]
    document = BeautifulSoup(rendered, "html.parser")
    assert [a["href"] for a in document.find_all("a")] == [url, url]
    assert document.h1.strong.a.get_text() == "CV"
    assert document.h1.em.a.get_text() == "More"


@pytest.mark.parametrize(
    "url", ["javascript:alert(1)", "data:text/html,test", "java%73cript:alert(1)"]
)
@pytest.mark.parametrize("underlined", [False, True])
def test_literal_links_still_refuse_unsafe_schemes(url, underlined):
    handlers = {"link": underlined_link_handler} if underlined else None
    rendered = markdown_to_html(f"[CV]({url})", handlers=handlers)
    anchor = BeautifulSoup(rendered, "html.parser").a
    assert anchor.get("href") is None
    assert anchor.get_text() == "CV"


@pytest.mark.django_db
@pytest.mark.parametrize("theme", ["plain", "headwind"])
def test_about_and_project_pages_render_literal_markdown_links(client, resume, theme):
    from copy import deepcopy

    url = 'https://example.test/a*b*c?x="yes"&copy;=2'
    text = f"[**Synthetic CV**]({url})"
    resume.owner.save()
    resume.plugin_data = {
        "theme": {"name": theme},
        "token": {"flat": {"token_required": False}},
        "about": {"title": "About", "text": text},
        "projects": {
            "flat": {"title": "Projects"},
            "items": [
                {
                    "id": "p1",
                    "title": "Synthetic project",
                    "url": "",
                    "description": text,
                    "badges": [],
                    "position": 0,
                }
            ],
        },
    }
    before = deepcopy(resume.plugin_data)
    resume.save()
    response = client.get(reverse("resume:cv", kwargs={"slug": resume.slug}))
    assert response.status_code == 200
    document = BeautifulSoup(response.content, "html.parser")
    anchors = [a for a in document.find_all("a") if a.get_text() == "Synthetic CV"]
    assert len(anchors) == 2  # About and Project both render their stored Markdown.
    for anchor in anchors:
        assert anchor["href"] == url
        assert "target" not in anchor.attrs
        assert anchor.strong.get_text() == "Synthetic CV"
    resume.refresh_from_db()
    assert resume.plugin_data == before


@pytest.mark.parametrize("suffix", ["", "](none)", "[none]", "[none](unfinished"])
def test_markdown_without_link_delimiters_skips_the_suffix_index(monkeypatch, suffix):
    from django_resume import markdown

    visits = []

    def track_range(*args):
        if len(args) == 3 and args[2] == -1:
            visits.append(args)
        return range(*args)

    monkeypatch.setattr(markdown, "range", track_range, raising=False)
    text = "x" * (markdown.MAX_MARKDOWN_CHARS - len(suffix)) + suffix
    assert markdown.markdown_to_html(text) == text
    assert visits == []

    rendered = markdown.markdown_to_html("[CV](https://example.test/a(b)?x=1&y=2)")
    assert rendered == (
        '<a href="https://example.test/a(b)?x=1&amp;y=2" rel="noopener noreferrer">CV</a>'
    )
    assert len(visits) == 2
