from django.template import Context, Template

from django_resume.handwriting import compose


def render(text):
    template = Template("{% load editorial_handwriting %}{% handwriting_label label %}")
    return template.render(Context({"label": text}))


def test_supported_label_uses_nonzero_font_outline():
    # The ink is ONE combined path with fill-rule="nonzero" = the exact font
    # glyph (counters open, overlaps solid). Even-odd would hole the cursive
    # overlaps; a per-contour fill would blob the counters.
    svg = compose.compose_label("Contact")
    assert svg is not None
    assert 'fill-rule="evenodd"' not in svg
    assert 'fill-rule="nonzero"' in svg
    assert '<path class="hw-ink"' in svg
    assert 'mask="url(#hw' in svg
    assert 'class="hw-pen"' in svg
    # horizontal labels carry their em size as inline-size with auto height, so
    # max-inline-size:100% can shrink them proportionally on narrow columns
    assert 'style="inline-size:' in svg and 'em"' in svg
    assert 'aria-hidden="true"' in svg


def test_vertical_label_keeps_em_height():
    svg = compose.compose_label("Contact", "vertical")
    assert svg is not None
    assert 'class="hw-rot"' in svg
    assert "height:" in svg and "em" in svg


def test_unsupported_char_falls_back_to_none():
    assert compose.compose_label("Œuvre") is None


def test_empty_and_space_only_fall_back_to_none():
    assert compose.compose_label("") is None
    assert compose.compose_label("   ") is None


def test_deterministic_mask_id():
    assert compose.compose_label("Education") == compose.compose_label("Education")


def test_umlaut_label_supported():
    assert compose.compose_label("Sprechen wir über") is not None


def test_ligature_al_is_substituted():
    # "al" must use the ligature glyph, not base a + l, so spacing and shape
    # match the browser's default ligature rendering.
    data = compose._data()
    al_strokes = len(data["ligatures"]["al"]["strokes"])
    naive = len(data["glyphs"]["a"]["strokes"]) + len(data["glyphs"]["l"]["strokes"])
    assert al_strokes != naive
    assert compose.compose_label("al").count('class="hw-pen"') == al_strokes


def test_longest_ligature_wins():
    data = compose._data()
    assert compose.compose_label("alt").count('class="hw-pen"') == len(
        data["ligatures"]["alt"]["strokes"]
    )


def test_tag_renders_svg_plus_hidden_text():
    html = render("Contact")
    assert '<svg class="hw-svg"' in html
    assert 'class="hw-text"' in html
    assert "Contact" in html


def test_tag_renders_plain_text_for_unsupported_label():
    html = render("Œuvre")
    assert "<svg" not in html
    assert "hw-fallback" in html
    assert "Œuvre" in html


def test_tag_escapes_text():
    html = render("a<b")
    assert "<b" not in html
    assert "&lt;b" in html


def test_tag_handles_none():
    assert "hw-fallback" in render(None)
