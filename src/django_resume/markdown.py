import re


def textarea_input_to_markdown(text):
    # <br> to \n
    text = text.replace("<br>", "\n")

    # remove <div> and </div>
    text = text.replace("<div>", "")
    print("remove: ", text)
    text = text.replace("</div>", "")
    return text


def markdown_to_textarea_input(text):
    # \n to <br>
    text = text.replace("\n", "<br>")

    return text


def markdown_to_html(text):
    # Headings
    text = re.sub(
        r"^(#{1,6})\s*(.*)",
        lambda m: f"<h{len(m.group(1))}>{m.group(2)}</h{len(m.group(1))}>",
        text,
        flags=re.MULTILINE,
    )

    # Bold
    text = re.sub(r"\*\*(.*?)\*\*", r"<strong>\1</strong>", text)

    # Italic
    text = re.sub(r"\*(.*?)\*", r"<em>\1</em>", text)

    # Links [text](url)
    text = re.sub(r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>', text)

    # Paragraphs
    text = re.sub(r"(^|\n)([^\n]+)\n", r"\1<p>\2</p>\n", text)

    return text
