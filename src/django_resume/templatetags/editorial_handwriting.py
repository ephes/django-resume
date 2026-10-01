from django import template
from django.utils.html import escape
from django.utils.safestring import SafeString, mark_safe

from ..handwriting.compose import compose_label

register = template.Library()


@register.simple_tag
def handwriting_label(text: object, orientation: str = "horizontal") -> SafeString:
    """
    Render a label as a self-writing handwriting SVG with a plain-text fallback.

    Supported text renders visually hidden real text (for screen readers, print
    and selection) plus an ``aria-hidden`` animated SVG. Empty text or text with
    characters the glyph data does not cover renders as plain escaped text.
    ``orientation="vertical"`` rotates the SVG for the rotated rail labels.
    """
    text = "" if text is None else str(text)
    safe = escape(text)
    svg = compose_label(text, orientation)
    if svg is None:
        return mark_safe(f'<span class="hw-label hw-fallback">{safe}</span>')
    css_class = "hw-label hw-label--rail" if orientation == "vertical" else "hw-label"
    return mark_safe(
        f'<span class="{css_class}" data-hw><span class="hw-text">{safe}</span>{svg}</span>'
    )
