"""Browser tests for the editorial theme's self-writing handwriting labels.

They load the theme's handwriting CSS/JS into a blank page, so no live server
is needed. Run with::

    uv run pytest --ds=e2e_tests.settings e2e_tests/editorial_handwriting_test.py
"""

import struct
import zlib
from pathlib import Path

import django_resume
import pytest
from django.template import Context, Template

from django_resume.handwriting.compose import compose_label

STATIC = Path(django_resume.__file__).resolve().parent / "static/django_resume"
HANDWRITING_CSS = STATIC / "css/editorial/handwriting.css"
HANDWRITING_JS = STATIC / "js/editorial/handwriting.js"


def _png_gray_pixels(png: bytes) -> list[int]:
    """Decode an 8-bit RGB(A), non-interlaced PNG (as Chromium screenshots are)
    into one luminance value per pixel."""
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat = 8, b""
    while pos < len(png):
        (length,) = struct.unpack(">I", png[pos : pos + 4])
        kind = png[pos + 4 : pos + 8]
        data = png[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, depth, color, _, _, interlace = struct.unpack(
                ">IIBBBBB", data
            )
            assert depth == 8 and color in (2, 6) and interlace == 0
        elif kind == b"IDAT":
            idat += data
        pos += 12 + length
    channels = 4 if color == 6 else 3
    stride = width * channels
    raw = zlib.decompress(idat)
    previous = bytearray(stride)
    gray = []
    for row in range(height):
        start = row * (stride + 1)
        kind, line = raw[start], bytearray(raw[start + 1 : start + 1 + stride])
        for i in range(stride):
            left = line[i - channels] if i >= channels else 0
            up = previous[i]
            up_left = previous[i - channels] if i >= channels else 0
            if kind == 1:
                line[i] = (line[i] + left) & 0xFF
            elif kind == 2:
                line[i] = (line[i] + up) & 0xFF
            elif kind == 3:
                line[i] = (line[i] + (left + up) // 2) & 0xFF
            elif kind == 4:
                estimate = left + up - up_left
                pa, pb, pc = (
                    abs(estimate - left),
                    abs(estimate - up),
                    abs(estimate - up_left),
                )
                predictor = (
                    left if pa <= pb and pa <= pc else up if pb <= pc else up_left
                )
                line[i] = (line[i] + predictor) & 0xFF
        gray.extend(
            (299 * line[i] + 587 * line[i + 1] + 114 * line[i + 2]) // 1000
            for i in range(0, stride, channels)
        )
        previous = line
    return gray


def _dark_px(shot):
    """Count near-black (revealed ink) pixels in a PNG screenshot."""
    return sum(1 for value in _png_gray_pixels(shot) if value < 128)


def _reveal_pens(page, dashoffset):
    """Set every pen's --L = its length and freeze stroke-dashoffset.

    dashoffset 0 == fully written; "L - 1" == only just started (1 unit drawn).
    """
    page.eval_on_selector_all(
        ".hw-pen",
        "(els, off) => els.forEach(p => {"
        "  const L = p.getTotalLength();"
        "  p.style.setProperty('--L', L);"
        "  p.style.strokeDashoffset = off === 'start' ? (L - 1) : 0;"
        "})",
        dashoffset,
    )


def test_pens_reveal_no_ink_dot_when_a_stroke_just_starts(page):
    """Regression: a stroke that has only just begun must not reveal an ink blob.

    The reveal mask animates stroke-dashoffset from L to 0. With
    `stroke-linecap: round`, a stroke at the very start of its animation renders
    a round cap (a full dot, diameter = stroke-width) at its origin, which the
    mask exposes as a black dot floating ahead of the writing — most visible on
    mobile. `butt` caps draw nothing until the stroke has real length, so the
    just-started state reveals (almost) no ink. We assert the just-started state
    exposes a negligible fraction of the fully-written ink.
    """
    svg = compose_label("Work Experience")
    assert svg is not None
    page.set_viewport_size({"width": 2400, "height": 420})
    page.set_content(
        f"<!doctype html><meta charset=utf-8>"
        f"<style>body{{margin:20px;background:#fff;color:#000;font-size:140px}}</style>"
        f"<body>{svg}"
    )
    page.add_style_tag(path=str(HANDWRITING_CSS))

    _reveal_pens(page, "start")
    just_started = _dark_px(page.locator(".hw-svg").screenshot())
    _reveal_pens(page, 0)
    written = _dark_px(page.locator(".hw-svg").screenshot())

    assert written > 5000, "fully-written label should reveal substantial ink"
    # round caps expose ~3.6% here (the dots); butt caps expose ~0%.
    assert just_started < 0.005 * written, (
        f"just-started strokes reveal too much ink ({just_started}px of "
        f"{written}px written) — round-cap dots are leaking through the mask"
    )


def _animation_durations(page):
    return page.evaluate("""
        Array.from(document.querySelectorAll(".hw-svg.hw-go .hw-pen")).map(function (pen) {
          return getComputedStyle(pen).animationDuration;
        })
        """)


def _label(text):
    return f"""
    <span class="hw-label" data-hw>
      <span class="hw-text">{text}</span>
      <svg class="hw-svg" viewBox="0 0 120 20" aria-hidden="true" focusable="false">
        <g class="hw-ink-group">
          <path class="hw-ink" d="M 0 0 H 100 V 20 H 0 Z"></path>
        </g>
        <path class="hw-pen" d="M 0 10 L 100 10" style="stroke-width:20"></path>
      </svg>
    </span>
    """


def _load_test_page(page):
    page.set_viewport_size({"width": 800, "height": 500})
    page.set_content(f"""
        <!doctype html>
        <html>
          <head>
            <script>
              window.__hwEvents = [];
              document.addEventListener("animationstart", function (event) {{
                var label = event.target.closest(".hw-label");
                if (label) {{
                  window.__hwEvents.push(label.querySelector(".hw-text").textContent);
                }}
              }}, true);
            </script>
          </head>
          <body>
            <main>
              <section style="height: 700px">{_label("First")}</section>
              <section style="height: 700px">{_label("Second")}</section>
            </main>
          </body>
        </html>
        """)
    page.evaluate(
        "document.documentElement.setAttribute('data-hw-replay-cooldown', '2000')"
    )
    page.add_style_tag(path=str(HANDWRITING_CSS))
    page.add_script_tag(path=str(HANDWRITING_JS))


def test_handwriting_labels_replay_at_top_only_after_cooldown(page):
    _load_test_page(page)

    page.wait_for_function("window.__hwEvents.includes('First')")
    page.wait_for_timeout(900)
    assert page.evaluate("Array.from(new Set(window.__hwEvents))") == ["First"]
    assert any(duration != "0s" for duration in _animation_durations(page))

    page.evaluate("window.__hwEvents = []")
    page.evaluate("window.scrollTo(0, 700)")
    page.wait_for_function("window.__hwEvents.includes('Second')")
    page.wait_for_timeout(900)
    assert page.evaluate("Array.from(new Set(window.__hwEvents))") == ["Second"]

    page.evaluate("window.__hwEvents = []")
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)
    assert page.evaluate("window.__hwEvents") == []

    page.wait_for_timeout(2100)
    page.evaluate("window.scrollTo(0, 700)")
    page.wait_for_timeout(100)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_function("window.__hwEvents.includes('First')")
    page.wait_for_timeout(900)
    assert page.evaluate("Array.from(new Set(window.__hwEvents))") == ["First"]
    assert any(duration != "0s" for duration in _animation_durations(page))

    page.evaluate("window.__hwEvents = []")
    page.evaluate("window.scrollTo(0, 700)")
    page.wait_for_timeout(100)
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(400)

    assert page.evaluate("window.__hwEvents") == []


def test_handwriting_labels_replay_when_returning_to_tab_after_cooldown(page):
    _load_test_page(page)

    page.wait_for_function("window.__hwEvents.includes('First')")
    page.wait_for_timeout(900)
    page.evaluate("window.__hwEvents = []")

    page.wait_for_timeout(2100)
    page.evaluate("""
        Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
        document.dispatchEvent(new Event("visibilitychange"));
        Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
        document.dispatchEvent(new Event("visibilitychange"));
        """)
    page.wait_for_function("window.__hwEvents.includes('First')")
    page.wait_for_timeout(900)
    assert page.evaluate("Array.from(new Set(window.__hwEvents))") == ["First"]
    assert any(duration != "0s" for duration in _animation_durations(page))

    page.evaluate("window.__hwEvents = []")
    page.evaluate("""
        Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
        document.dispatchEvent(new Event("visibilitychange"));
        Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
        document.dispatchEvent(new Event("visibilitychange"));
        """)
    page.wait_for_timeout(400)

    assert page.evaluate("window.__hwEvents") == []


@pytest.mark.parametrize("document", ["resume_cv", "resume_detail"])
@pytest.mark.parametrize("failure", ["blocked_script", "stroke_measurement"])
def test_editorial_labels_stay_written_when_enhancement_fails(page, document, failure):
    # Inherit the real editorial head/styles, including any premature inline
    # enhancement marker, while keeping this browser regression database-free.
    svg = compose_label("Education")
    html = Template(
        '{% extends "django_resume/pages/editorial/' + document + '.html" %}'
        '{% block body %}<body style="background:white;color:black;font-size:100px">'
        '<span class="hw-label"><span class="hw-text">Education</span>'
        + svg
        + "</span>"
        '<script src="/handwriting.js" defer></script></body>{% endblock %}'
    ).render(Context())
    script_requests = []

    def respond(route):
        url = route.request.url
        if route.request.resource_type == "document":
            route.fulfill(body=html, content_type="text/html")
        elif "handwriting.css" in url:
            route.fulfill(path=str(HANDWRITING_CSS), content_type="text/css")
        elif url.endswith("/handwriting.js"):
            script_requests.append(url)
            if failure == "blocked_script":
                route.abort()
            else:
                route.fulfill(path=str(HANDWRITING_JS), content_type="text/javascript")
        else:
            route.abort()

    if failure == "stroke_measurement":
        page.add_init_script(
            "window.__measurements = 0; SVGGeometryElement.prototype.getTotalLength = function () {"
            "window.__measurements++; throw new Error('simulated geometry failure'); };"
        )
    page.route("**/*", respond)
    page.goto("http://handwriting.test/", wait_until="networkidle")
    assert script_requests
    if failure == "stroke_measurement":
        assert page.evaluate("window.__measurements") > 0
    assert not page.evaluate("document.documentElement.classList.contains('js-hw')")
    assert (
        page.locator(".hw-ink-group").evaluate("el => getComputedStyle(el).visibility")
        == "visible"
    )
    assert (
        page.locator(".hw-pen").first.evaluate(
            "el => getComputedStyle(el).strokeDashoffset"
        )
        == "0px"
    )
    assert _dark_px(page.locator(".hw-svg").screenshot()) > 1000


def test_handwriting_runtime_failure_restores_all_labels(page):
    # Fail after setup succeeds, in the asynchronous observer/pump path. Ink
    # must reopen for both the active label and labels still waiting in queue.
    page.set_content(_label("First") + _label("Second"))
    page.add_style_tag(path=str(HANDWRITING_CSS))
    page.evaluate(
        "() => { document.querySelector('.hw-svg').getBoundingClientRect = function () {"
        "throw new Error('simulated animation failure'); }; }"
    )
    page.add_script_tag(path=str(HANDWRITING_JS))
    page.wait_for_function("!document.documentElement.classList.contains('js-hw')")
    assert page.locator(".hw-ink-group").evaluate_all(
        "els => els.every(el => getComputedStyle(el).visibility === 'visible')"
    )
    assert page.locator(".hw-pen").evaluate_all(
        "els => els.every(el => getComputedStyle(el).strokeDashoffset === '0px')"
    )


def test_reduced_motion_skips_measurement_and_animation(page):
    page.emulate_media(reduced_motion="reduce")
    page.set_content(_label("First"))
    page.add_style_tag(path=str(HANDWRITING_CSS))
    page.evaluate(
        "() => { SVGGeometryElement.prototype.getTotalLength = function () {"
        "throw new Error('reduced motion must not measure'); }; }"
    )
    errors = []
    page.on("pageerror", lambda error: errors.append(error))
    page.add_script_tag(path=str(HANDWRITING_JS))
    assert not errors
    assert not page.evaluate("document.documentElement.classList.contains('js-hw')")
    assert (
        page.locator(".hw-ink-group").evaluate("el => getComputedStyle(el).visibility")
        == "visible"
    )


@pytest.mark.parametrize(
    "label",
    [
        "Work Experience",
        "Let's talk about",
        "Contact",
        "Education",
        "Resources",
        "Awards",
    ],
)
def test_real_composed_labels_animate_successfully(page, label):
    svg = compose_label(label)
    assert svg is not None
    page.emulate_media(reduced_motion="no-preference")
    page.set_viewport_size({"width": 1600, "height": 500})
    page.set_content('<body style="font-size:60px">' + svg + "</body>")
    page.add_style_tag(path=str(HANDWRITING_CSS))
    page.add_script_tag(path=str(HANDWRITING_JS))
    page.wait_for_function(
        "document.querySelector('.hw-svg').classList.contains('hw-go')"
    )
    assert page.evaluate("document.documentElement.classList.contains('js-hw')")
    lengths_and_durations = page.locator(".hw-pen").evaluate_all(
        "els => els.map(p => [p.getTotalLength(), parseFloat(getComputedStyle(p).animationDuration)])"
    )
    positive_pens = [
        (length, duration) for length, duration in lengths_and_durations if length > 0
    ]
    assert positive_pens
    assert all(duration > 0 for _, duration in positive_pens)


def test_zero_length_skeleton_does_not_disable_other_strokes(page):
    # Add a legitimate single-point skeleton to real composed geometry without
    # changing production glyphs; it must consume no animation time.
    svg = compose_label("Education").replace(
        "</mask>", '<path class="hw-pen zero-pen" d="M 1 1"/></mask>'
    )
    page.set_content('<body style="font-size:60px">' + svg + "</body>")
    page.add_style_tag(path=str(HANDWRITING_CSS))
    page.add_script_tag(path=str(HANDWRITING_JS))
    page.wait_for_function(
        "document.querySelector('.hw-svg').classList.contains('hw-go')"
    )
    assert page.evaluate("document.documentElement.classList.contains('js-hw')")
    assert page.locator(".zero-pen").evaluate("p => p.getTotalLength()") == 0
    assert (
        page.locator(".zero-pen").evaluate("p => getComputedStyle(p).animationName")
        == "none"
    )
    assert (
        page.locator(".zero-pen").evaluate("p => getComputedStyle(p).strokeDashoffset")
        == "0px"
    )
    assert page.locator(".hw-pen:not(.zero-pen)").evaluate_all(
        "els => els.filter(p => p.getTotalLength() > 0)"
        ".every(p => parseFloat(getComputedStyle(p).animationDuration) > 0)"
    )


def test_nonfinite_stroke_length_still_fails_open(page):
    page.set_content(compose_label("Education"))
    page.add_style_tag(path=str(HANDWRITING_CSS))
    page.evaluate("() => { SVGGeometryElement.prototype.getTotalLength = () => NaN; }")
    page.add_script_tag(path=str(HANDWRITING_JS))
    assert not page.evaluate("document.documentElement.classList.contains('js-hw')")
    assert (
        page.locator(".hw-ink-group").evaluate("el => getComputedStyle(el).visibility")
        == "visible"
    )
