import html
import re
from urllib.parse import unquote
from typing import Callable

import nh3


MAX_MARKDOWN_CHARS = 256 * 1024
MAX_EDITOR_INPUT_CHARS = 2 * 1024 * 1024


ALLOWED_TAGS = {
    "a",
    "br",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "li",
    "strong",
    "ul",
}
LIST_ITEM_RE = re.compile(r"^\s*[-*•]\s+(.*)$")
# Marks list items before inline formatting runs, so an asterisk list marker is
# never mistaken for the start of an italic span.
LIST_ITEM_MARKER = "\x00li\x00"
ALLOWED_ATTRIBUTES = {"a": {"class", "href", "target"}}
ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}
URL_SCHEME_RE = re.compile(r"^([a-zA-Z][a-zA-Z0-9+.-]*):")


def _link_attribute(url: str) -> str:
    # Keep destination newlines out of the later newline -> <br> assembly.
    return html.escape(url, quote=True).replace("\n", "&#10;")


def underlined_link_handler(text: str, url: str) -> str:
    return f'<a href="{_link_attribute(url)}" class="underlined">{text}</a>'


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


def safe_link_url(value: str) -> str:
    """Return ``value`` if it is safe as a link target, otherwise an empty string."""
    scheme = _get_normalized_url_scheme(value)
    if scheme is not None and scheme not in ALLOWED_URL_SCHEMES:
        return ""
    return value


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


def _strip_html_tags(text: str) -> str:
    """Remove the legacy <[^>]+> subset without rescanning failed suffixes."""
    pieces = []
    cursor = search = 0
    while (start := text.find("<", search)) != -1:
        end = text.find(">", start + 1)
        if end == -1:
            break
        search = end + 1
        if end == start + 1:  # <> was never a tag in the editor format.
            continue
        pieces.append(text[cursor:start])
        cursor = search
    pieces.append(text[cursor:])
    return "".join(pieces)


def textarea_input_to_markdown(text: str) -> str:
    if len(text) > MAX_EDITOR_INPUT_CHARS:
        raise ValueError("Editor input exceeds 2097152 character limit")
    # Replace div tags with newlines
    content = re.sub(r"<div>", "\n", text, flags=re.IGNORECASE)
    content = re.sub(r"</div>", "", content, flags=re.IGNORECASE)

    # Replace <br> and <br/> with newlines
    content = re.sub(r"<br\s*/?>", "\n", content, flags=re.IGNORECASE)

    # Remove any remaining HTML tags
    content = _strip_html_tags(content)

    # Decode once after stripping tags: encoded markup remains literal text.
    content = html.unescape(content)

    # Fix multiple newlines (more than 2) to maximum 2 newlines
    content = re.sub(r"\n{3,}", "\n\n", content)

    # Trim whitespace
    content = content.strip()

    return content


def markdown_to_textarea_input(text: str) -> str:
    """Encode stored text as editor input: an HTML fragment in which literal
    text is entity-escaped and ``<br>`` is the only markup. It is the inverse
    of ``textarea_input_to_markdown``, so an unchanged save stores the same
    text again."""
    return html.escape(text, quote=False).replace("\n", "<br>")


def textarea_input_to_html(text: str) -> str:
    """Render editor input (stored text encoded by
    ``markdown_to_textarea_input`` or submitted ``innerHTML``) for a
    contenteditable field: the text it would be saved as, escaped, with line
    breaks as the only markup."""
    # Bound redisplay too: a refused bound form still carries its original
    # submitted data, but must not convert it again while showing field errors.
    if len(text) > MAX_EDITOR_INPUT_CHARS:
        return ""
    return markdown_to_textarea_input(textarea_input_to_markdown(text))


def markdown_to_plain_text(text: str) -> str:
    text = markdown_to_html(text)
    text = text.replace("<br>", "\n")
    text = text.replace("<ul>", "\n").replace("</li>", "\n")
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _replace_links(text: str, render: Callable[[str, str], str]) -> str:
    """Match the existing label + URL subset in two linear passes.

    Labels cannot cross newlines. URLs allow flat parenthesized groups but
    no deeper nesting. Precompute each suffix's closing URL delimiter so a
    failed candidate never rescans the remaining text.
    """
    ends = [-1] * (len(text) + 1)
    next_paren = len(text)
    for index in range(len(text) - 1, -1, -1):
        char = text[index]
        if char == ")":
            ends[index] = index
            next_paren = index
        elif char == "(":
            if next_paren < len(text) and text[next_paren] == ")":
                ends[index] = ends[next_paren + 1]
            next_paren = index
        else:
            ends[index] = ends[index + 1]

    pieces = []
    start = None
    cursor = 0
    index = 0
    while index < len(text):
        char = text[index]
        if char == "\n":
            start = None
        elif char == "[" and start is None:
            start = index
        elif start is not None and text.startswith("](", index):
            end = ends[index + 2]
            if end != -1:
                pieces.append(text[cursor:start])
                pieces.append(render(text[start + 1 : index], text[index + 2 : end]))
                cursor = end + 1
                index = cursor
                start = None
                continue
        index += 1
    pieces.append(text[cursor:])
    return "".join(pieces)


def markdown_to_html(text: str, handlers: dict[str, Callable] | None = None) -> str:
    """
    Really simple markdown to HTML converter.

    You can pass a dictionary of handlers to customize the output.
    """
    if len(text) > MAX_MARKDOWN_CHARS:
        raise ValueError("Markdown input exceeds 262144 character limit")
    if handlers is None:
        handlers = {}

    # Protect destinations before formatting, including multiline URLs that
    # contain what would otherwise look like a heading or list item. Source
    # NULs are removed so the numeric markers cannot collide with input.
    text = text.replace("\x00", "")
    destinations: dict[str, str] = {}

    def protect_destination(label, url):
        marker = f"\x00{len(destinations)}\x00"
        destinations[marker] = url
        return f"[{label}]({marker})"

    text = _replace_links(text, protect_destination)

    def restore_destinations(content: str) -> str:
        # Custom formatting callbacks keep their source-text arguments. Protect
        # any links in their result again before the next formatting pass.
        return re.sub(r"\x00\d+\x00", lambda m: destinations.get(m[0], m[0]), content)

    # Mark list items first; inline formatting must not consume their markers.
    text = "\n".join(
        LIST_ITEM_MARKER + match.group(1).strip()
        if (match := LIST_ITEM_RE.match(line))
        else line
        for line in text.split("\n")
    )

    # Headings
    def render_heading(m):
        level = len(m.group(1))
        content = m.group(2).strip()
        if "heading" in handlers:
            return _replace_links(
                handlers["heading"](level, restore_destinations(content)),
                protect_destination,
            )
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
            return _replace_links(
                handlers["bold"](restore_destinations(content)), protect_destination
            )
        else:
            return f"<strong>{content}</strong>"

    text = re.sub(r"\*\*(.*?)\*\*", render_bold, text)

    # Italic
    def render_italic(m):
        content = m.group(1)
        if "italic" in handlers:
            return _replace_links(
                handlers["italic"](restore_destinations(content)), protect_destination
            )
        else:
            return f"<em>{content}</em>"

    text = re.sub(r"\*(.*?)\*", render_italic, text)

    # Links
    def render_link(link_text, url):
        url = destinations.get(url, url)
        if "link" in handlers:
            return handlers["link"](link_text, url)
        else:
            return f'<a href="{_link_attribute(url)}">{link_text}</a>'

    text = _replace_links(text, render_link)

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
        if line.startswith(LIST_ITEM_MARKER):
            pending_items.append(line.removeprefix(LIST_ITEM_MARKER))
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
