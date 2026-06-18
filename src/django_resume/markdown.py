import html
import re
from urllib.parse import unquote
from typing import Callable

import nh3


ALLOWED_TAGS = {"a", "br", "em", "h1", "h2", "h3", "h4", "h5", "h6", "li", "strong", "ul"}
LIST_ITEM_RE = re.compile(r"^\s*[-*•]\s+(.*)$")
ALLOWED_ATTRIBUTES = {"a": {"class", "href", "target"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}
URL_SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")


def underlined_link_handler(text: str, url: str) -> str:
    return f'<a href="{url}" class="underlined">{text}</a>'


def _get_normalized_url_scheme(value: str) -> str | None:
    candidate = html.unescape(value)
    candidate = re.sub(r"[\x00-\x20]+", "", candidate)
    for _ in range(3):
        decoded = unquote(candidate)
        if decoded == candidate:
            break
        candidate = decoded
    match = URL_SCHEME_RE.match(candidate)
    if match is None:
        return None
    return match.group(1).lower()


def _attribute_filter(tag: str, attribute: str, value: str) -> str | None:
    if tag == "a" and attribute == "href":
        scheme = _get_normalized_url_scheme(value)
        if scheme is not None and scheme not in ALLOWED_URL_SCHEMES:
            return None
    return value


def sanitize_html(text: str) -> str:
    return nh3.clean(
        text,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        attribute_filter=_attribute_filter,
        url_schemes=ALLOWED_URL_SCHEMES,
    )


def textarea_input_to_markdown(text: str) -> str:
    # Replace div tags with newlines
    content = re.sub(r"<div>", "\n", text, flags=re.IGNORECASE)
    content = re.sub(r"</div>", "", content, flags=re.IGNORECASE)

    # Replace <br> and <br/> with newlines
    content = re.sub(r"<br\s*/?>", "\n", content, flags=re.IGNORECASE)

    # Remove any remaining HTML tags
    content = re.sub(r"<[^>]+>", "", content)

    # Fix multiple newlines (more than 2) to maximum 2 newlines
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Trim whitespace
    content = content.strip()

    return content


def markdown_to_textarea_input(text: str) -> str:
    # \n to <br>
    text = text.replace("\n", "<br>")

    return text


def textarea_input_to_html(text: str) -> str:
    text = html.escape(text)
    text = re.sub(r"&lt;br\s*/?&gt;", "<br>", text, flags=re.IGNORECASE)
    return text.replace("\n", "<br>")


def markdown_to_plain_text(text: str) -> str:
    text = markdown_to_html(text)
    text = text.replace("<br>", "\n")
    text = text.replace("</li>", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def markdown_to_html(text: str, handlers: dict[str, Callable] | None = None) -> str:
    """
    Really simple markdown to HTML converter.

    You can pass a dictionary of handlers to customize the output.
    """
    if handlers is None:
        handlers = {}

    # Headings
    def render_heading(m):
        level = len(m.group(1))
        content = m.group(2).strip()
        if "heading" in handlers:
            return handlers["heading"](level, content)
        else:
            return f"<h{level}>{content}</h{level}>"

    text = re.sub(
        r"^(#{1,6})\s*(.*)",
        render_heading,
        text,
        flags=re.MULTILINE,
    )

    # Bold
    def render_bold(m):
        content = m.group(1)
        if "bold" in handlers:
            return handlers["bold"](content)
        else:
            return f"<strong>{content}</strong>"

    text = re.sub(r"\*\*(.*?)\*\*", render_bold, text)

    # Italic
    def render_italic(m):
        content = m.group(1)
        if "italic" in handlers:
            return handlers["italic"](content)
        else:
            return f"<em>{content}</em>"

    text = re.sub(r"\*(.*?)\*", render_italic, text)

    # Links
    def render_link(m):
        link_text = m.group(1)
        url = m.group(2)
        if "link" in handlers:
            return handlers["link"](link_text, url)
        else:
            return f'<a href="{url}">{link_text}</a>'

    text = re.sub(r"\[(.*?)\]\(((?:[^()]|\([^()]*\))*)\)", render_link, text)

    # Group consecutive marker lines (-, *, •) into real <ul><li> lists; the
    # remaining lines keep the simple newline -> <br> behaviour. Adjacent text
    # lines are glued with <br>, but a list block (already block-level) is not.
    def render_list(items):
        if "list" in handlers:
            return handlers["list"](items)
        body = "".join(f"<li>{item}</li>" for item in items)
        return f"<ul>{body}</ul>"

    segments = []  # (kind, content)
    pending_items = []
    for line in text.split("\n"):
        match = LIST_ITEM_RE.match(line)
        if match:
            pending_items.append(match.group(1).strip())
            continue
        if pending_items:
            segments.append(("list", render_list(pending_items)))
            pending_items = []
        segments.append(("text", line))
    if pending_items:
        segments.append(("list", render_list(pending_items)))

    text = ""
    for index, (kind, content) in enumerate(segments):
        if index == 0:
            text = content
        elif kind == "text" and segments[index - 1][0] == "text":
            text += "<br>" + content
        else:
            text += content

    return sanitize_html(text)
