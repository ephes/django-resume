import re
from typing import Callable


def textarea_input_to_markdown(text: str) -> str:
    # <br> to \n
    text = text.replace("<br>", "\n")

    # remove <div> and </div>
    text = text.replace("<div>", "")
    print("remove: ", text)
    text = text.replace("</div>", "")
    return text


def markdown_to_textarea_input(text: str) -> str:
    # \n to <br>
    text = text.replace("\n", "<br>")

    return text


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

    text = re.sub(r"\[(.*?)\]\((.*?)\)", render_link, text)

    # Just replace newlines with <br>
    text = text.replace("\n", "<br>")

    return text
