# Editorial Cover Letter + Handwriting Migration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the handwriting a native, self-contained part of the django-resume editorial theme, then build an editorial cover-letter page (the `detail` view) that reuses the CV design — same handwriting, same recognizable header — with an image-or-handwriting signature and clean A4 print.

**Architecture:** Two sequential, independently shippable phases. Phase 1 moves the runtime handwriting composer (pure-Python, font-free) + its tag + CSS/JS + tests out of the `homepage` project and into `django_resume`, wires it into the editorial `base.html` so every editorial page inherits it (coexisting with the existing `js-lines` hairline animation), and deletes the homepage overrides — with a pixel-parity gate on the CV. Phase 2 extends the `cover` plugin with closing/signature fields and rebuilds the editorial `resume_detail.html` + cover templates onto the editorial layout shell to match the reference letter, including print.

**Tech Stack:** Django templates + template tags, vanilla CSS/JS (CSS-first, JS as progressive enhancement), pytest, Playwright (Python) for visual verification, uv for env management.

**Design spec:** `docs/superpowers/specs/2026-06-22-editorial-cover-letter-and-handwriting-migration-design.md` (local/untracked).

## Global Constraints

- **CV pixel-identical (Phase 1):** the CV at `/resume/<slug>/cv/` must render identically before and after the migration, desktop + mobile. Any visual diff is a defect.
- **Recognizable elements identical:** the cover letter's shared elements (name typography, `WERSDÖRFER`, role, rotated handwritten "Contact" label, contact icons, colours, spacing, fonts) must be identical to the CV — reuse the same templates/CSS/components, do not re-create.
- **Self-contained theme:** after Phase 1 the editorial theme renders the handwriting with **no** `homepage` override and **no** `homepage.handwriting` app.
- **Handwriting pen `stroke-linecap: butt`** (never `round`) — preserves the no-ink-dots fix; keep its regression test.
- **Graceful degradation:** no-JS and `prefers-reduced-motion: reduce` show the final written handwriting and static lines, fully readable. Handwriting (`js-hw`) and hairlines (`js-lines`) are two independent before-paint class toggles + two deferred scripts; both must keep working.
- **Signature precedence:** if a signature image is set, render the image; else render the signature name (default `identity.name`) as self-writing handwriting.
- **Screen + Print (A4):** the letter must print as a clean A4 application PDF.
- **Pipeline unchanged:** the `handwriting-anim` repo stays the source of `glyph_data.json`; only the copy *target* moves to django-resume.
- **Commit messages:** no self-reference, no "Claude/Anthropic" attribution, no generated-with footer.
- **Dev env:** run the homepage server with `.venv/bin/python manage.py runserver` (NOT `uv run`, which re-syncs to the PyPI 0.2.0 and breaks the editorial theme) until Task 5 pins django-resume as an editable source.

---

## Phase 1 — Migrate the handwriting into the editorial theme

Work happens in `~/gitprojects/django-resume` (branch `editorial-theme`) and `~/gitprojects/homepage`. Take the **parity baseline screenshots first** (Task 1) so every later step can be checked against them.

### Task 1: Capture the CV parity baseline

**Files:**
- Create: `~/gitprojects/django-resume/tests/visual/baseline/` (screenshots, git-ignored or kept locally)
- Create: `~/gitprojects/django-resume/tests/visual/shoot_cv.py` (reusable shooter)

**Interfaces:**
- Produces: `shoot_cv.py` — a standalone Playwright script taking `BASE_URL`, `OUT_DIR` and writing `cv-desktop.png`, `cv-mobile.png`, `cv-anim-mobile.png`.

- [ ] **Step 1: Ensure the editorial theme is the live one.** In `~/gitprojects/homepage`: `uv pip install -e ~/gitprojects/django-resume` then start the server with `.venv/bin/python manage.py runserver 0.0.0.0:8003`. Confirm `curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8003/resume/katharina/cv/?token=localpreview2026"` prints `200`.

- [ ] **Step 2: Write the shooter** `tests/visual/shoot_cv.py`:

```python
import sys
from playwright.sync_api import sync_playwright

BASE_URL = sys.argv[1]  # e.g. http://127.0.0.1:8003/resume/katharina/cv/?token=localpreview2026
OUT = sys.argv[2]       # output dir

with sync_playwright() as p:
    b = p.chromium.launch()
    # desktop, final written state
    d = b.new_page(viewport={"width": 1280, "height": 1600}, device_scale_factor=2)
    d.goto(BASE_URL, wait_until="networkidle")
    d.wait_for_timeout(2500)  # let line + handwriting animations settle
    d.screenshot(path=f"{OUT}/cv-desktop.png", full_page=True)
    # mobile, final written state
    m = b.new_page(viewport={"width": 420, "height": 900}, device_scale_factor=2)
    m.goto(BASE_URL, wait_until="networkidle")
    m.wait_for_timeout(2500)
    m.screenshot(path=f"{OUT}/cv-mobile.png", full_page=True)
    b.close()
```

- [ ] **Step 3: Shoot the baseline.**

Run (in homepage, which has Playwright): `cd ~/gitprojects/homepage && mkdir -p ~/gitprojects/django-resume/tests/visual/baseline && uv run python ~/gitprojects/django-resume/tests/visual/shoot_cv.py "http://127.0.0.1:8003/resume/katharina/cv/?token=localpreview2026" ~/gitprojects/django-resume/tests/visual/baseline`

> NOTE: this `uv run` re-syncs homepage's venv to PyPI 0.2.0 and will break the live CV. That is fine *for taking screenshots only if the page already rendered*; to be safe, take the baseline with the server still on the editable install, i.e. run the shooter with `.venv/bin/python` instead: `~/gitprojects/homepage/.venv/bin/python ~/gitprojects/django-resume/tests/visual/shoot_cv.py ...`. Re-install editable (`uv pip install -e ~/gitprojects/django-resume`) and restart the server if any `uv run` clobbered it.
Expected: three PNGs exist and visually show the finished CV (creme sheet, handwriting labels written, hairlines drawn).

- [ ] **Step 4: Commit the shooter** (baseline PNGs may stay local):

```bash
cd ~/gitprojects/django-resume
echo "tests/visual/baseline/" >> .gitignore
git add tests/visual/shoot_cv.py .gitignore
git commit -m "Add CV visual parity shooter for the handwriting migration"
```

### Task 2: Move the composer + glyph data + tag into django-resume

**Files:**
- Create: `src/django_resume/handwriting/__init__.py`
- Create: `src/django_resume/handwriting/compose.py` (from `homepage/homepage/handwriting/compose.py`)
- Create: `src/django_resume/handwriting/glyph_data.json` (from homepage)
- Create: `src/django_resume/templatetags/handwriting.py` (adapted from homepage)
- Create: `tests/handwriting/test_compose.py`, `tests/handwriting/test_templatetag.py` (from homepage)

**Interfaces:**
- Produces: `django_resume.handwriting.compose.compose_label(text, orientation="horizontal") -> str | None` and `is_supported(text) -> bool`; template tag `{% handwriting_label text orientation="vertical" %}` (library name `handwriting`).

- [ ] **Step 1: Copy composer + data into django-resume.**

```bash
cd ~/gitprojects/django-resume
mkdir -p src/django_resume/handwriting tests/handwriting
cp ~/gitprojects/homepage/homepage/handwriting/compose.py src/django_resume/handwriting/compose.py
cp ~/gitprojects/homepage/homepage/handwriting/glyph_data.json src/django_resume/handwriting/glyph_data.json
touch src/django_resume/handwriting/__init__.py
```

(`compose.py` reads `glyph_data.json` next to itself via `os.path.dirname(__file__)`, so no path edit is needed.)

- [ ] **Step 2: Create the template tag** `src/django_resume/templatetags/handwriting.py`. It drops `handwriting_static` (base.html uses plain `{% static %}`) and imports the composer from its new home:

```python
from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from django_resume.handwriting.compose import compose_label

register = template.Library()


@register.simple_tag
def handwriting_label(text, orientation="horizontal"):
    """Render a label as a self-writing handwriting SVG, with graceful fallback.

    Supported text -> visually-hidden real text (a11y) + aria-hidden animated SVG.
    Unsupported/empty -> plain escaped text only. orientation="vertical" rotates
    the SVG for the rail labels. Default state is fully revealed (CSS);
    handwriting.js hides+animates on scroll only with JS and motion allowed.
    """
    text = "" if text is None else str(text)
    safe = escape(text)
    svg = compose_label(text, orientation)
    if svg is None:
        return mark_safe(f'<span class="hw-label hw-fallback">{safe}</span>')
    cls = "hw-label hw-label--rail" if orientation == "vertical" else "hw-label"
    return mark_safe(
        f'<span class="{cls}" data-hw>'
        f'<span class="hw-text">{safe}</span>{svg}</span>'
    )
```

- [ ] **Step 3: Move the composer tests.** Copy `homepage/homepage/handwriting/tests/test_compose.py` and `test_templatetag.py` into `tests/handwriting/`, and fix imports: replace `from homepage.handwriting...` with `from django_resume.handwriting...`, and `{% load handwriting %}` works unchanged once `django_resume` is the app. Add `tests/handwriting/__init__.py`.

- [ ] **Step 4: Run the moved tests, expect PASS.**

Run: `cd ~/gitprojects/django-resume && uv run pytest tests/handwriting/ -q`
Expected: PASS (supported labels produce `<svg class="hw-svg"`, `fill-rule="nonzero"`, `mask="url(#hw`; unsupported/empty fall back to plain text).

- [ ] **Step 5: Commit.**

```bash
git add src/django_resume/handwriting src/django_resume/templatetags/handwriting.py tests/handwriting
git commit -m "Add font-free handwriting composer + label tag to django-resume"
```

### Task 3: Move the handwriting CSS/JS and wire them into editorial base.html

**Files:**
- Create: `src/django_resume/static/django_resume/css/editorial/handwriting.css` (from homepage `static/handwriting/handwriting.css`)
- Create: `src/django_resume/static/django_resume/js/editorial/handwriting.js` (from homepage `static/handwriting/handwriting.js`)
- Modify: `src/django_resume/templates/django_resume/pages/editorial/base.html`
- Create: `tests/handwriting/test_editorial_handwriting_wiring.py`

**Interfaces:**
- Consumes: the existing `{% block styles %}` (js-lines wiring) and `{% block body %}` in base.html.
- Produces: every editorial page sets `js-hw` before paint, links `handwriting.css`, and loads `handwriting.js` (defer), alongside the `js-lines` setup.

- [ ] **Step 1: Copy the assets.**

```bash
cd ~/gitprojects/django-resume
cp ~/gitprojects/homepage/homepage/static/handwriting/handwriting.css src/django_resume/static/django_resume/css/editorial/handwriting.css
cp ~/gitprojects/homepage/homepage/static/handwriting/handwriting.js  src/django_resume/static/django_resume/js/editorial/handwriting.js
```

Confirm the CSS keeps `stroke-linecap: butt` on `.hw-pen` (Global Constraint): `grep -n "stroke-linecap" src/django_resume/static/django_resume/css/editorial/handwriting.css` → `butt`.

- [ ] **Step 2: Wire base.html `{% block styles %}`.** After the existing `editorial-lines.js` line (base.html:21), add the handwriting setup so it sits next to js-lines:

```html
    {# handwriting: set js-hw before first paint so labels start hidden when JS is on (no flash of finished text); handwriting.js then hides+animates on scroll. No JS / reduced-motion => labels stay written + readable. Independent of js-lines. #}
    <script>document.documentElement.classList.add('js-hw');</script>
    <link rel="stylesheet" type="text/css" href="{% static "django_resume/css/editorial/handwriting.css" %}?v={{ asset_version }}">
    <script src="{% static "django_resume/js/editorial/handwriting.js" %}?v={{ asset_version }}" defer></script>
```

(`asset_version` is already defined at base.html:14.)

- [ ] **Step 3: Write a wiring test** `tests/handwriting/test_editorial_handwriting_wiring.py`:

```python
from django.test import Client
import pytest


@pytest.mark.django_db
def test_editorial_cv_links_handwriting_assets(editorial_resume_with_token):
    # editorial_resume_with_token: fixture creating an editorial-themed resume +
    # returning (client_url) that renders 200 without auth. Reuse the project's
    # existing resume/token test fixtures (see tests/ for the established pattern).
    url = editorial_resume_with_token
    html = Client().get(url).content.decode()
    assert "css/editorial/handwriting.css" in html
    assert "js/editorial/handwriting.js" in html
    assert "classList.add('js-hw')" in html
    # coexists with the hairline animation
    assert "classList.add('js-lines')" in html
```

> If no ready-made fixture exists, build the resume inline following the pattern already used by the editorial template tests in `tests/`; the assertion content is what matters.

- [ ] **Step 4: Run it, expect PASS.** `uv run pytest tests/handwriting/test_editorial_handwriting_wiring.py -q` → PASS.

- [ ] **Step 5: Commit.**

```bash
git add src/django_resume/static/django_resume/css/editorial/handwriting.css \
        src/django_resume/static/django_resume/js/editorial/handwriting.js \
        src/django_resume/templates/django_resume/pages/editorial/base.html \
        tests/handwriting/test_editorial_handwriting_wiring.py
git commit -m "Wire handwriting CSS/JS into the editorial base template"
```

### Task 4: Port the handwriting labels into django-resume's editorial templates

The homepage overrides are copies of django-resume's editorial templates with `{% handwriting_label %}` swapped in. Port those swaps into django-resume's own templates, replacing each plain rail/section `<h2>` and the `handwriting_static` calls. Reference the homepage overrides for the exact label strings and class names.

**Files (modify in django-resume; reference homepage overrides):**
- Modify: `src/django_resume/templates/django_resume/pages/editorial/resume_cv.html`
- Modify: `src/django_resume/templates/django_resume/plugins/identity/editorial/content.html`
- Modify: `src/django_resume/templates/django_resume/plugins/timelines/editorial/flat.html`
- Modify: `src/django_resume/templates/django_resume/plugins/awards/editorial/flat.html`
- Reference: the four homepage override files under `~/gitprojects/homepage/homepage/templates/django_resume/...`

- [ ] **Step 1: resume_cv.html.** Add `{% load handwriting %}` at the top. Replace the three sidebar rail labels with the handwriting versions (from homepage override lines 77/85/92):

```html
<h2 class="cv-rail-label hw-rail">{% handwriting_label "Let's talk about" orientation="vertical" %}</h2>
<h2 class="cv-rail-label hw-rail">{% handwriting_label "Education" orientation="vertical" %}</h2>
<h2 class="cv-rail-label hw-rail">{% handwriting_label "Resources" orientation="vertical" %}</h2>
```

Remove any `{% handwriting_static %}` / inline js-hw / handwriting.js lines from the django-resume template — those now live in `base.html` (Task 3). The `screen.css`/`print.css`/line-js stay as base.html already provides them.

- [ ] **Step 2: identity/editorial/content.html.** Add `{% load handwriting %}`; replace the "Contact" rail label with (homepage override line 24):

```html
<h2 class="cv-rail-label hw-rail">{% handwriting_label "Contact" orientation="vertical" %}</h2>
```

- [ ] **Step 3: timelines/editorial/flat.html.** Add `{% load handwriting %}`; replace `<h2>{{ timeline.title }}</h2>` with `<h2>{% handwriting_label timeline.title %}</h2>`.

- [ ] **Step 4: awards/editorial/flat.html.** Add `{% load handwriting %}`; replace `<h2>{{ awards.title }}</h2>` with `<h2>{% handwriting_label awards.title %}</h2>`.

- [ ] **Step 5: Restart the server** (`.venv/bin/python manage.py runserver 0.0.0.0:8003` in homepage; the editable install already points at these files) and confirm the CV still renders `200` with handwriting (the override is still present and wins for now — that is fine; Task 5 removes it).

- [ ] **Step 6: Commit.**

```bash
git add src/django_resume/templates/django_resume/pages/editorial/resume_cv.html \
        src/django_resume/templates/django_resume/plugins/identity/editorial/content.html \
        src/django_resume/templates/django_resume/plugins/timelines/editorial/flat.html \
        src/django_resume/templates/django_resume/plugins/awards/editorial/flat.html
git commit -m "Use the handwriting label in the editorial theme templates"
```

### Task 5: Remove homepage overrides + app; pin django-resume as an editable source

**Files:**
- Delete (homepage): the 4 editorial overrides + the whole `homepage/homepage/handwriting/` app + its `static/handwriting/`.
- Modify (homepage): `pyproject.toml` `[tool.uv.sources]`, `commands.py` dev/git source lists, and `INSTALLED_APPS` (remove `homepage.handwriting`).
- Modify (homepage): `homepage/homepage/handwriting/README.md` reference is gone; update `~/gitprojects/handwriting-anim/README.md` so the `glyph_data.json` copy target is `~/gitprojects/django-resume/src/django_resume/handwriting/glyph_data.json`.

- [ ] **Step 1: Delete the homepage overrides and app.**

```bash
cd ~/gitprojects/homepage
git rm -r homepage/templates/django_resume/pages/editorial/resume_cv.html \
         homepage/templates/django_resume/plugins/identity/editorial/content.html \
         homepage/templates/django_resume/plugins/timelines/editorial/flat.html \
         homepage/templates/django_resume/plugins/awards/editorial/flat.html \
         homepage/handwriting
```

- [ ] **Step 2: Remove the app from settings.** Locate it: `grep -rn "homepage.handwriting" config/ homepage/` and delete the `INSTALLED_APPS` entry.

- [ ] **Step 3: Pin django-resume editable.** In `homepage/pyproject.toml` `[tool.uv.sources]` add (mirroring the cast packages):

```toml
django-resume = { path = "../django-resume", editable = true }
```

Also add it to the dev/git source lists in `commands.py` so `switch-to-dev-environment` / `switch-to-git-sources` manage it: editable `("django-resume", projects_dir / "django-resume")` in `switch_to_dev_environment()`, and a default git source `"django-resume": {"git": "https://github.com/ephes/django-resume", "branch": "editorial-theme"}` in `switch_to_git_sources()`. (The `editorial-theme` branch must be pushed for the git source to resolve in CI/production.)

- [ ] **Step 4: Re-lock and verify `uv run` is now safe.**

```bash
cd ~/gitprojects/homepage
uv lock
uv run python -c "import django_resume, os; print(os.path.realpath(django_resume.__file__))"
```

Expected: prints a path **inside `~/gitprojects/django-resume`** (editable), not site-packages 0.2.0. Now `uv run` no longer clobbers the theme.

- [ ] **Step 5: Restart and smoke-test.** `uv run python manage.py runserver 0.0.0.0:8003`; confirm CV `200` and that handwriting still renders (now served entirely by django-resume, no homepage override).

- [ ] **Step 6: Update the pipeline doc.** In `~/gitprojects/handwriting-anim/README.md`, change the `cp glyph_data.json ...` target to `~/gitprojects/django-resume/src/django_resume/handwriting/glyph_data.json`.

- [ ] **Step 7: Commit (two repos).**

```bash
cd ~/gitprojects/homepage && git add -A && git commit -m "Drop handwriting app + editorial overrides; use django-resume's native handwriting"
cd ~/gitprojects/handwriting-anim && git add README.md && git commit -m "Point glyph_data.json copy target at django-resume"
```

### Task 6: CV parity gate (Phase 1 acceptance)

**Files:**
- Create: `~/gitprojects/django-resume/tests/visual/compare.py`

- [ ] **Step 1: Re-shoot the CV** into `tests/visual/after/` with the same shooter and the same server URL (now serving entirely from django-resume): `~/gitprojects/homepage/.venv/bin/python tests/visual/shoot_cv.py "http://127.0.0.1:8003/resume/katharina/cv/?token=localpreview2026" tests/visual/after`.

- [ ] **Step 2: Write the comparator** `tests/visual/compare.py`:

```python
import sys
import numpy as np
from PIL import Image

a, b = Image.open(sys.argv[1]).convert("RGB"), Image.open(sys.argv[2]).convert("RGB")
w, h = min(a.width, b.width), min(a.height, b.height)
aa = np.asarray(a.crop((0, 0, w, h)), dtype=np.int16)
bb = np.asarray(b.crop((0, 0, w, h)), dtype=np.int16)
diff = np.abs(aa - bb).sum(axis=2)            # per-pixel L1 over RGB
changed = int((diff > 12).sum())              # tolerance for AA/subpixel
print(f"{sys.argv[1]} vs {sys.argv[2]}: {changed} changed px of {w*h} "
      f"({100*changed/(w*h):.3f}%) | size a={a.size} b={b.size}")
```

- [ ] **Step 3: Compare desktop + mobile.**

Run: `cd ~/gitprojects/django-resume && for v in desktop mobile; do ~/gitprojects/homepage/.venv/bin/python tests/visual/compare.py tests/visual/baseline/cv-$v.png tests/visual/after/cv-$v.png; done`
Expected: near-0% changed (allow a tiny AA delta from the animation settling). The full-page sizes must match. **If a real diff appears, it is a defect — fix the migration, do not adjust the tolerance.**

- [ ] **Step 4: Eyeball both PNGs** (read them) to confirm the handwriting labels and hairlines are present and identical. Phase 1 is done when parity holds.

- [ ] **Step 5: Commit the comparator.** `git add tests/visual/compare.py && git commit -m "Add visual comparator; CV parity verified after handwriting migration"`.

---

## Phase 2 — Editorial cover-letter page

Builds on Phase 1 (handwriting now native; `base.html` already loads it). Reference: the cover-letter PDF (`/Users/katha/Documents/CV_Anschreiben/050326_Anschreiben_Katharina_Wersdoerfer.pdf`).

### Task 7: Extend the `cover` plugin (closing + signature)

**Files:**
- Modify: `src/django_resume/plugins/cover.py`
- Test: `tests/plugins/test_cover.py` (follow the existing cover/plugin test pattern in `tests/`)

**Interfaces:**
- Produces: `cover` flat context gains `closing` (str), `signature_name` (str, may be ""), `signature_img` / `signature_img_url` (str URL or ""). Template applies precedence: image if set, else `signature_name|default:identity.name` via handwriting.

- [ ] **Step 1: Write failing tests** in `tests/plugins/test_cover.py`:

```python
def test_cover_flat_form_has_closing_and_signature_fields():
    from django_resume.plugins.cover import CoverFlatForm
    f = CoverFlatForm()
    assert "closing" in f.fields
    assert "signature_name" in f.fields
    assert "signature_img" in f.fields
    assert "clear_signature" in f.fields


def test_cover_flat_set_context_exposes_signature_and_closing():
    from django_resume.plugins.cover import CoverFlatForm
    ctx = {"edit_flat_url": "/x"}
    CoverFlatForm.set_context(
        {"closing": "Mit freundlichen Grüßen", "signature_name": "Katharina Wersdörfer",
         "signature_img": "", "subject": "Bewerbung"},
        ctx,
    )
    assert ctx["cover"]["closing"] == "Mit freundlichen Grüßen"
    assert ctx["cover"]["signature_name"] == "Katharina Wersdörfer"
    assert ctx["cover"]["signature_img_url"] == ""   # no image -> empty, template falls back to name
```

- [ ] **Step 2: Run, expect FAIL.** `uv run pytest tests/plugins/test_cover.py -q -k "closing or signature"` → FAIL (KeyError / missing fields).

- [ ] **Step 3: Implement in `CoverFlatForm`.** Add fields after `salutation` (cover.py:89-91) and extend `image_fields` + `set_context`:

```python
    closing = forms.CharField(
        widget=forms.TextInput(), required=False, max_length=200,
        initial="Mit freundlichen Grüßen",
    )
    signature_name = forms.CharField(
        label="Signature name (defaults to the resume name)",
        widget=forms.TextInput(), required=False, max_length=100,
    )
    signature_img = forms.FileField(
        label="Signature image (optional PNG)", max_length=100, required=False,
    )
    clear_signature = forms.BooleanField(
        widget=forms.CheckboxInput, initial=False, required=False,
    )
    image_fields = [("avatar_img", "clear_avatar"), ("signature_img", "clear_signature")]

    @property
    def signature_img_url(self) -> str:
        return self.get_image_url_for_field(self.initial.get("signature_img", ""))
```

And inside `set_context` add to the `context["cover"]` dict:

```python
            "closing": item.get("closing", ""),
            "signature_name": item.get("signature_name", ""),
            "signature_img": ImageFormMixin.get_image_url_for_field(item.get("signature_img", "")),
            "signature_img_url": ImageFormMixin.get_image_url_for_field(item.get("signature_img", "")),
```

- [ ] **Step 4: Run, expect PASS.** `uv run pytest tests/plugins/test_cover.py -q` → PASS. Also run `just check` and fix any mypy/lint issues (the repo uses `just check` as the gate).

- [ ] **Step 5: Commit.** `git add src/django_resume/plugins/cover.py tests/plugins/test_cover.py && git commit -m "Add closing + image-or-name signature fields to the cover plugin"`.

### Task 8: Rebuild `resume_detail.html` onto the editorial shell

Replace the minimal `<body class="center">` detail page with the editorial layout: dark `editorial-page` body, the `editorial-sheet`, the **identity header without the photo**, then the cover content. This is where the recognizable header becomes identical to the CV.

**Files:**
- Modify: `src/django_resume/templates/django_resume/pages/editorial/resume_detail.html`
- Modify: `src/django_resume/templates/django_resume/plugins/identity/editorial/content.html` (add an optional `no_photo`/header-only switch, or factor the header so the letter can include it without the CV photo block)

- [ ] **Step 1: Decide the photo-suppression mechanism.** The CV photo lives in `resume_cv.html` (the `.cv-photo` block, cv.html:60-74), **not** in the identity template — identity renders name/role/contact rail only. Confirm by reading `identity/editorial/content.html`. Therefore the letter can `{% include identity.templates.main %}` to get the exact header (name + role + handwritten "Contact" rail + icons) with **no photo to suppress**. If any photo markup is in identity, gate it behind an `{% if not header_only %}` the letter sets.

- [ ] **Step 2: Rewrite `resume_detail.html`** to the editorial shell (mirrors resume_cv.html structure, letter body instead of CV body):

```html
{% extends "./base.html" %}
{% load static %}

{% block title %}Anschreiben — {{ identity.name }}{% endblock title %}
{% block meta %}
  {{ block.super }}
  <meta name="author" content="{{ identity.name }}">
{% endblock meta %}

{% block body %}
  {% if show_edit_button %}
    <body class="editorial-page" hx-headers='{"X-CSRFToken": "{{ csrf_token }}"}'>
  {% else %}
    <body class="editorial-page">
  {% endif %}
  <div class="cv-root">
    <div class="cv-stage">
      <div class="editorial-sheet stack">
        {% if is_editable %}{% include "./edit_panel.html" %}{% endif %}
        {# identical recognizable header: name, role, handwritten "Contact" rail, icons #}
        {% include identity.templates.main %}
        {% if show_edit_button %}{% include theme.templates.main %}{% endif %}
        {# the letter itself #}
        {% include cover.templates.main %}
      </div>
    </div>
  </div>
  {% if show_edit_button %}
    <script src="{% static "django_resume/js/edit.js" %}"></script>
  {% endif %}
  </body>
{% endblock body %}
```

(handwriting.css/js + line js + screen/print css all come from `base.html`; no per-page asset wiring needed.)

- [ ] **Step 3: Restart + smoke test** the detail page: `curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8003/resume/katharina/?token=localpreview2026"` → `200`, and a Playwright screenshot shows the editorial header (creme sheet, name typography, handwritten "Contact").

- [ ] **Step 4: Commit.** `git add -A && git commit -m "Render the editorial cover letter on the CV layout shell with the shared header"`.

### Task 9: Style the cover content templates to match the PDF

**Files:**
- Modify: `src/django_resume/templates/django_resume/plugins/cover/editorial/content.html`
- Modify: `src/django_resume/templates/django_resume/plugins/cover/editorial/flat.html`
- Modify: `src/django_resume/templates/django_resume/plugins/cover/editorial/item.html`
- Modify: `src/django_resume/static/django_resume/css/editorial/screen.css`

**Layout target (from the PDF):** rounded card under the header containing — `place_date` (top-right), `recipient` (multiline, left), a short divider rule, `subject` (bold), `salutation`, the markdown `items[]` paragraphs, `closing`, then the **signature** (image if set, else the name as self-writing handwriting).

- [ ] **Step 1: content.html** — render the flat header fields + items in order. Use the editorial tokens/primitives (`stack`, the modular-scale spacing, `--editorial-rule` for the divider) so it matches the CV's rhythm. Structure:

```html
{% load handwriting %}
<article class="cover-letter stack">
  <header class="cover-letter-head">
    <p class="cover-place-date">{{ cover.place_date }}</p>
    <div class="cover-recipient">{{ cover.recipient|linebreaksbr }}</div>
    <hr class="cover-rule">
    {% if cover.subject %}<p class="cover-subject"><b>{{ cover.subject }}</b></p>{% endif %}
  </header>
  {% if cover.salutation %}<p class="cover-salutation">{{ cover.salutation }}</p>{% endif %}
  <div class="cover-body stack">
    {% for item in items %}{% include cover.templates.item %}{% endfor %}
  </div>
  <footer class="cover-sign stack-small">
    {% if cover.closing %}<p class="cover-closing">{{ cover.closing }}</p>{% endif %}
    {% if cover.signature_img_url %}
      <img class="cover-signature-img" src="{{ cover.signature_img_url }}" alt="{{ identity.name }}">
    {% else %}
      <div class="cover-signature-hw">{% handwriting_label cover.signature_name|default:identity.name %}</div>
    {% endif %}
  </footer>
</article>
```

(Adjust to the plugin's actual item-iteration variable — confirm whether items come via `items` or a per-item include, matching the existing `content.html`.)

- [ ] **Step 2: screen.css** — add a `.cover-letter` block scoped to the editorial sheet: the rounded card, the right-aligned date, the recipient block, the short `.cover-rule` hairline (use `var(--editorial-rule) solid var(--editorial-line)`, short width like the PDF), bold subject, paragraph rhythm, signature sizing (image max-height ~ the handwriting cap height for visual parity). Reuse existing variables; no new colour/though tokens unless justified.

- [ ] **Step 3: Iterate against the PDF in-browser.** Shoot the letter (desktop + mobile) with a Playwright script modelled on `shoot_cv.py` (URL `…/resume/katharina/?token=…`), read the PNG, compare element-by-element to the PDF (header parity, date position, recipient, divider, subject bold, body, closing, signature). Adjust CSS and re-shoot until it matches. Verify **both** signature paths: with `signature_img` set (upload a test PNG via the edit UI or seed plugin data) and without (handwriting fallback writes the name).

- [ ] **Step 4: Confirm the line animation reaches the letter.** With JS on, the `editorial-sheet` edges + any letter rules should draw in (Global Constraint). If the `.cover-rule` should animate like the CV hairlines, add it to the `editorial-lines.js` target selectors (or give it a class the script already targets) and verify; otherwise leave it static intentionally and note why.

- [ ] **Step 5: Commit.** `git add -A && git commit -m "Style the editorial cover letter to the reference layout"`.

### Task 10: Print (A4)

**Files:**
- Modify: `src/django_resume/static/django_resume/css/editorial/print.css`

- [ ] **Step 1: Add letter print rules.** Under the print stylesheet, ensure: handwriting shows its final written state (it already does without JS / the `js-hw` reduced-motion path; verify in print emulation), the `editorial-sheet` prints edge-to-edge on A4 with sensible `@page` margins, the recipient/subject/body sit at letter-typical positions, and the signature (image or handwriting) prints crisply. Keep the existing CV print rules intact.

- [ ] **Step 2: Verify with print emulation.**

```python
# tests/visual/shoot_print.py (Playwright)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto("http://127.0.0.1:8003/resume/katharina/?token=localpreview2026", wait_until="networkidle")
    pg.emulate_media(media="print")
    pg.pdf(path="tests/visual/after/cover-print.pdf", format="A4", print_background=True)
    b.close()
```

Run it, open the PDF, confirm a clean one-page A4 application letter (handwriting final-state, correct margins, no screen chrome).

- [ ] **Step 3: Commit.** `git add -A && git commit -m "Print the editorial cover letter cleanly on A4"`.

### Task 11: Cover-letter verification + docs

- [ ] **Step 1: Full suite + check.** `cd ~/gitprojects/django-resume && just check` → green (lint, mypy, tests, incl. moved handwriting tests + new cover tests).
- [ ] **Step 2: Visual sign-off.** Read the desktop + mobile letter PNGs and the print PDF; confirm recognizable header parity with the CV and layout parity with the source PDF, both signature paths working.
- [ ] **Step 3: Changelog.** Add an "Unreleased / Features" entry in `docs/changelog.txt` for the editorial cover letter (mirroring the hairline-animation entry style).
- [ ] **Step 4: Commit.** `git add -A && git commit -m "Document the editorial cover letter; verification complete"`.

---

## Self-review notes (coverage)

- Spec "handwriting migration" → Tasks 2–5; "self-contained theme" + "no homepage app" → Task 5; "CV pixel-identical" → Tasks 1 & 6.
- Spec "hairline animation coexistence" → Task 3 (js-hw beside js-lines) + Task 9 step 4 (letter lines).
- Spec "cover fields: closing, signature image + name default identity.name" → Task 7 + Task 9 step 1 precedence.
- Spec "identical recognizable header, no photo" → Task 8.
- Spec "layout per PDF" → Task 9; "Print A4" → Task 10.
- Spec "dev-env editable pin so uv run is safe" → Task 5 steps 3–4.
- Spec "pipeline copy target moves" → Task 5 step 6.

## Known in-browser-iteration tasks (not placeholders)

Tasks 9–10 require visual iteration against the PDF; their *gate* is the Playwright shoot-and-compare loop (same method used to verify the linecap fix), not a fixed pixel spec. The structure, class names, fields, and precedence are fully specified; the spacing/sizing values are tuned in-browser and committed once they match.
