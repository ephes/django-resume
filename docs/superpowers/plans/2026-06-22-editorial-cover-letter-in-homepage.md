# Editorial Cover Letter (in homepage) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reader-usable editorial **cover-letter page** (the django-resume `detail` view) inside the `homepage` project, reusing the CV's editorial design and the existing handwriting — recognizable header identical to the CV, an image-or-handwriting signature, and clean A4 print.

**Architecture:** Develop entirely in `homepage` for a fast edit→refresh loop: the cover-letter templates are `homepage` template overrides of the editorial `detail`/`cover` templates, the layout is an app-local, tightly-scoped `.cover-letter` stylesheet layered after the editorial CSS, and the handwriting is the one already living in `homepage.handwriting`. There are **no** django-resume changes: the new cover fields (`closing`, signature name + image) are added by a homepage `CoverPlugin` subclass re-registered under name `"cover"` (the registry overrides by name). Pulling all of this into the django-resume theme later is explicitly **out of scope** — it is a separate Backlog item ("Theme Extraction").

**Tech Stack:** Django template overrides + the existing `homepage.handwriting` tag, vanilla CSS/JS (CSS-first, JS as progressive enhancement), pytest, Playwright (Python) for visual verification, uv.

**Design spec:** `~/gitprojects/django-resume/docs/superpowers/specs/2026-06-22-editorial-cover-letter-and-handwriting-migration-design.md` (local/untracked).

## Status (as of 2026-06-23 handoff)

**Done & pushed:**
- **Task 1** (homepage `1c57b2c`): django-resume pinned as a **git source** on branch `editorial-theme` in `pyproject.toml` + `commands.py` switches. `uv run` is now safe (serves the editorial theme, not PyPI 0.2.0).
- **Task 2** (homepage `6fe3faa`): cover fields added via the homepage `CoverPlugin` subclass app `homepage/resume_cover/` (`closing`, `signature_name`, `signature_img`, `clear_signature`; `get_context` adds `signature_img_url`), registered in `INSTALLED_APPS` after `django_resume`. Tests pass.
- **Bonus editorial-theme fixes** (django-resume `editorial-theme`, pushed to `64fa0e4`): timeline edit form date-tab fly-off + entry-padding collapse (`4b1cb7d`); all identity fields except `name` made optional (`55a6ac6`). homepage relocked to `64fa0e4` (homepage `3f3e9dc`).

**Current state:** homepage on branch `editorial-resume-theme` @ `3f3e9dc`; django-resume git-sourced at `editorial-theme` @ `64fa0e4` (no editable install — `uv run` is durable). Dev server running at `:8003`. Owner login `katharina` / `Passwort`; edit mode = login + `?edit=true` same-host.

**Next:** **Task 3** onward (resume_detail override → cover templates → cover.css → print → verify). See the handoff prompt / the per-task DONE banners below.

**Known gotchas for the next tasks:** the `ImageFormMixin` second-image bug (`images.py` hardcodes `cleaned_data["avatar_img"]` for dimension calc → signature upload crashes with no avatar — handle in `EditorialCoverFlatForm`); and the cover `flat_form.html` hardcodes its rendered fields (override it in homepage to expose the new signature/closing inputs).

## Global Constraints

- **Develop in homepage.** All presentation (templates, CSS, handwriting usage) lives in `homepage` as overrides/app-local files. Do **not** move anything into the django-resume theme in this plan.
- **Zero django-resume changes.** The new cover fields are added by a **homepage** `CoverPlugin` subclass re-registered under name `"cover"` — the plugin registry overrides by name (`registry.py._register`: it pops the old inline URLs, overwrites `plugins[name]`, re-adds URLs, clears caches). Rendering the fields needs nothing upstream: `ListPlugin.get_context` dumps `plugin_data["flat"]` into the context wholesale (base.py:1223), so any flat key is readable as `{{ cover.<key> }}`. The subclass exists only to (a) make the fields editable in the inline UI and (b) process the signature-image upload + expose its URL.
- **Recognizable elements identical:** the letter's shared elements (name typography, `WERSDÖRFER`, role, rotated handwritten "Contact" label, contact icons, colours, spacing, fonts) must be identical to the CV — reuse the same identity header + editorial CSS, do not re-create.
- **Signature precedence:** if `signature_img` is set, render the image; else render `signature_name` (default `identity.name`) as self-writing handwriting via `{% handwriting_label %}`.
- **Graceful degradation:** no-JS and `prefers-reduced-motion: reduce` show the final written handwriting and static lines, fully readable.
- **CV untouched.** This plan does not modify the CV page; the existing CV must keep working unchanged.
- **Screen + Print (A4).**
- **Dev env:** pin django-resume as an editable source so `uv run` no longer re-syncs to PyPI 0.2.0 and breaks the editorial theme (Task 1). Until then, run with `.venv/bin/python manage.py runserver`.
- **Commit messages:** no self-reference, no "Claude/Anthropic" attribution, no generated-with footer.

---

### Task 1: Pin django-resume editable so the dev loop is stable

**Files (homepage):**
- Modify: `pyproject.toml` `[tool.uv.sources]`
- Modify: `commands.py` (dev + git source lists)

> **DONE** (homepage commit `1c57b2c`). Built as a **git source** (branch
> `editorial-theme`), not a committed editable path: homepage's prek hook blocks
> committing local paths, and the plan makes **no** django-resume changes, so the
> git source is the correct CI/prod-safe default. Editable-via-`switch-to-dev-environment`
> is wired but optional (only needed if you want to hack on django-resume itself).

- [x] **Step 1: Add the git source.** In `pyproject.toml` `[tool.uv.sources]` (alongside the cast packages):

```toml
django-resume = { git = "https://github.com/ephes/django-resume", branch = "editorial-theme" }
```

This also fixes CI/prod, which were silently on PyPI `0.2.0` (no editorial theme at all).

- [x] **Step 2: Wire the dev/git switches.** In `commands.py`:
  - `switch_to_dev_environment()` editable list += `("django-resume", projects_dir / "django-resume")`;
  - `switch_to_git_sources()` defaults += `"django-resume": {"git": "https://github.com/ephes/django-resume", "branch": "editorial-theme"}`.
  (`origin/editorial-theme` carries the editorial theme — verified at commit `6f825f4`.)

- [x] **Step 3: Re-lock + verify `uv run` is safe.** `uv lock` resolved django-resume to `git+…@editorial-theme` (`6f825f4`); `uv sync` replaced the temporary editable install with the git build. `uv run` now serves the editorial theme instead of clobbering to `0.2.0`. (Import path is `.venv/.../site-packages` — the **git build**, not PyPI 0.2.0; the editorial `base.html` resolves, which 0.2.0 lacks.)

- [x] **Step 4: Smoke test.** `uv run python manage.py runserver 0.0.0.0:8003` + `curl … /resume/katharina/cv/?token=localpreview2026` → **200**, handwriting + hairlines render.

- [x] **Step 5: Commit (homepage).** `git add pyproject.toml uv.lock commands.py` → commit `1c57b2c` "Source django-resume from the editorial-theme branch; add to dev/git source switches".

### Task 2: Add the cover fields via a homepage CoverPlugin subclass (zero django-resume changes)

> **DONE** (homepage commit `6fe3faa`). Added app `homepage/resume_cover/`
> (`EditorialCoverFlatForm` + `EditorialCoverPlugin`), registered in `apps.ready()`
> and placed in `LOCAL_APPS` (loads after `django_resume`). Tests pass (registry
> returns the subclass; flat form has `closing`/`signature_name`/`signature_img`/
> `clear_signature` plus the inherited fields). Verified live: registry resolves
> `EditorialCoverPlugin`, CV + detail pages both 200. Zero django-resume changes.

Rendering needs nothing upstream (flat data is dumped into context — base.py:1223). A subclass re-registered under name `"cover"` adds the inline-edit form fields and the signature-image URL, entirely in homepage. TDD.

**Files (homepage):**
- Create: `homepage/resume_cover/__init__.py`, `homepage/resume_cover/apps.py`, `homepage/resume_cover/plugin.py`
- Create: `homepage/resume_cover/tests/__init__.py`, `homepage/resume_cover/tests/test_plugin.py`
- Modify: `config/settings/*.py` `INSTALLED_APPS` (add `"homepage.resume_cover"` **after** `"django_resume"`)

**Interfaces:**
- Produces: the registry's `"cover"` plugin is `EditorialCoverPlugin`; its flat form has `closing`, `signature_name`, `signature_img`, `clear_signature`; its `get_context` adds `signature_img_url`. Template reads `{{ cover.closing }}`, `{{ cover.signature_name }}`, `{{ cover.signature_img_url }}` (the flat dump + the get_context addition, both nested under `cover` by the view).

- [ ] **Step 1: Write failing tests** `homepage/resume_cover/tests/test_plugin.py`:

```python
def test_homepage_overrides_cover_plugin_in_registry():
    from django_resume.plugins import plugin_registry
    from homepage.resume_cover.plugin import EditorialCoverPlugin
    p = plugin_registry.get_plugin("cover")
    assert isinstance(p, EditorialCoverPlugin)


def test_editorial_cover_flat_form_has_new_fields():
    from homepage.resume_cover.plugin import EditorialCoverFlatForm
    f = EditorialCoverFlatForm()
    for name in ("closing", "signature_name", "signature_img", "clear_signature"):
        assert name in f.fields
```

- [ ] **Step 2: Run, expect FAIL.** `cd ~/gitprojects/homepage && uv run pytest homepage/resume_cover/tests/test_plugin.py -q` → FAIL (module/app not present).

- [ ] **Step 3: Create the plugin** `homepage/resume_cover/plugin.py`:

```python
from django import forms
from django.core.files.storage import default_storage

from django_resume.plugins.cover import CoverPlugin, CoverFlatForm, CoverItemForm


class EditorialCoverFlatForm(CoverFlatForm):
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


class EditorialCoverPlugin(CoverPlugin):
    @staticmethod
    def get_form_classes():
        return {"item": CoverItemForm, "flat": EditorialCoverFlatForm}

    def get_context(self, request, plugin_data, resume_pk, *, context, edit=False, theme="plain"):
        context = super().get_context(
            request, plugin_data, resume_pk, context=context, edit=edit, theme=theme
        )
        sig = plugin_data.get("flat", {}).get("signature_img", "")
        context["signature_img_url"] = default_storage.url(sig) if sig else ""
        return context
```

- [ ] **Step 4: Register it** `homepage/resume_cover/apps.py`:

```python
from django.apps import AppConfig


class ResumeCoverConfig(AppConfig):
    name = "homepage.resume_cover"

    def ready(self):
        from django_resume.plugins import plugin_registry
        from .plugin import EditorialCoverPlugin
        plugin_registry.register(EditorialCoverPlugin)   # overrides "cover" by name
```

Add `default_app_config` is unnecessary on modern Django; just add `"homepage.resume_cover"` to `INSTALLED_APPS` **after** `"django_resume"` so its `ready()` runs last and wins the override.

- [ ] **Step 5: Run, expect PASS.** `cd ~/gitprojects/homepage && uv run pytest homepage/resume_cover/tests/test_plugin.py -q` → PASS.

- [ ] **Step 6: Commit (homepage).** `git add homepage/resume_cover config/settings && git commit -m "Override the cover plugin in homepage with closing + signature fields"`.

### Task 3: Override the editorial `detail` page in homepage (editorial shell + header)

Replace the minimal django-resume `detail` page (which uses `<body class="center">`) with an override on the editorial layout shell, reusing the identity header so the recognizable elements are identical to the CV.

**Files (homepage):**
- Create: `homepage/templates/django_resume/pages/editorial/resume_detail.html`

**Reference:** the existing `homepage/templates/django_resume/pages/editorial/resume_cv.html` override (the styles/handwriting wiring + the editorial shell structure).

- [ ] **Step 1: Create the override** mirroring the CV override's head wiring (handwriting css/js, js-hw) and the editorial shell, with the letter body:

```html
{% extends "./base.html" %}
{% load static %}
{% load handwriting %}

{% block title %}Anschreiben — {{ identity.name }}{% endblock title %}
{% block meta %}
  {{ block.super }}
  <meta name="author" content="{{ identity.name }}">
{% endblock meta %}

{% block styles %}
  {{ block.super }}
  <link rel="stylesheet" href="{% handwriting_static "handwriting/handwriting.css" %}">
  <link rel="stylesheet" href="{% handwriting_static "cover-letter/cover.css" %}">
  <script>document.documentElement.classList.add('js-hw');</script>
{% endblock styles %}

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
        {% include cover.templates.main %}
      </div>
    </div>
  </div>
  {% if show_edit_button %}
    <script src="{% static "django_resume/js/edit.js" %}"></script>
  {% endif %}
  <script src="{% handwriting_static "handwriting/handwriting.js" %}" defer></script>
  </body>
{% endblock body %}
```

> The CV's photo lives in `resume_cv.html`, not in the identity template, so including `identity.templates.main` gives the header with **no photo to suppress**. Verify by reading `identity/editorial/content.html`; if any photo markup is there, gate it behind an `{% if not header_only %}` the letter does not set.

- [ ] **Step 2: Smoke test.** Restart the server; `curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:8003/resume/katharina/?token=localpreview2026"` → `200`. A Playwright screenshot shows the editorial header (creme sheet, name typography, handwritten "Contact").

- [ ] **Step 3: Commit (homepage).** `git add homepage/templates/django_resume/pages/editorial/resume_detail.html && git commit -m "Render the editorial cover letter on the CV layout shell with the shared header"`.

### Task 4: Cover-letter content templates (homepage overrides)

**Files (homepage, overriding django-resume's cover editorial templates):**
- Create: `homepage/templates/django_resume/plugins/cover/editorial/content.html`
- Create: `homepage/templates/django_resume/plugins/cover/editorial/item.html`
- Create (if the flat header is used separately): `homepage/templates/django_resume/plugins/cover/editorial/flat.html`

**Layout target (from the reference PDF):** under the header, a card with `place_date` (top-right), `recipient` (multiline, left), a short divider rule, `subject` (bold), `salutation`, the markdown `items[]` paragraphs, `closing`, then the **signature** (image if set, else the name as self-writing handwriting).

- [ ] **Step 1: content.html** (confirm the actual item-iteration variable against django-resume's original cover `content.html` — items may come via `items` or a per-item include):

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

- [ ] **Step 2: item.html** — one markdown paragraph block:

```html
<div class="cover-para">{{ item.text|safe }}</div>
```

(`item.text` is already markdown-rendered HTML by the plugin's `get_context`.)

- [ ] **Step 3: Smoke test.** Restart; the letter page renders the date/recipient/subject/salutation/body/closing and a signature (handwriting fallback, since no image yet).

- [ ] **Step 4: Commit (homepage).** `git add homepage/templates/django_resume/plugins/cover/ && git commit -m "Add editorial cover-letter content templates (date, recipient, body, signature)"`.

### Task 5: Cover-letter stylesheet (homepage, scoped `.cover-letter`)

**Files (homepage):**
- Create: `homepage/static/cover-letter/cover.css`

Keep every rule scoped under `.cover-letter` (or the `editorial-sheet` letter context) so the later theme extraction is a clean copy and never collides with CV rules. Reuse the editorial design tokens already defined on `:root` (modular scale `--s*`, `--editorial-rule`, `--editorial-line`, colours) — do not invent new colours.

- [ ] **Step 1: Lay out the card.** `.cover-letter` as a `stack`; `.cover-place-date` right-aligned; `.cover-recipient` left; `.cover-rule` a short hairline (`border-top: var(--editorial-rule) solid var(--editorial-line)`, narrow `inline-size` like the PDF); `.cover-subject` bold; paragraph rhythm via the modular scale; `.cover-signature-img { max-block-size: <~2.2rem, tuned to the handwriting cap-height>; }` and `.cover-signature-hw` sized like the CV script labels.

- [ ] **Step 2: Iterate against the PDF in-browser.** Shoot the letter (desktop + mobile) with a Playwright script modelled on the CV shooter (URL `…/resume/katharina/?token=…`), read the PNG, and compare element-by-element to the reference PDF (`/Users/katha/Documents/CV_Anschreiben/050326_Anschreiben_Katharina_Wersdoerfer.pdf`): header parity, date position, recipient, divider, bold subject, body, closing, signature. Adjust CSS and re-shoot until it matches.

- [ ] **Step 3: Verify both signature paths.** (a) handwriting fallback writes `identity.name`; (b) with a signature PNG present, the image renders instead. Seed a signature image via the edit UI or by setting `cover.flat.signature_img` in the resume's plugin data, then re-shoot.

- [ ] **Step 4: Confirm the hairline animation reaches the letter.** With JS on, the `editorial-sheet` edges draw in (it is already a `js-lines` target via `base.html`). If `.cover-rule` should animate like the CV hairlines, give it a class `editorial-lines.js` already targets or add it to that script's selectors; otherwise leave it static intentionally and note why.

- [ ] **Step 5: Commit (homepage).** `git add homepage/static/cover-letter/cover.css && git commit -m "Style the editorial cover letter to the reference layout"`.

### Task 6: Print (A4)

**Files (homepage):**
- Create: `homepage/static/cover-letter/cover-print.css`
- Modify: `homepage/templates/django_resume/pages/editorial/resume_detail.html` (link the print sheet)

- [ ] **Step 1: Link a print sheet** in the detail override's `{% block styles %}`:

```html
  <link media="print" rel="stylesheet" href="{% handwriting_static "cover-letter/cover-print.css" %}">
```

- [ ] **Step 2: Write the print rules** so the letter prints as a clean one-page A4: `@page { size: A4; margin: <letter margins>; }`, `.editorial-sheet` edge-to-edge, handwriting in final written state (it already is without JS / via the reduced-motion path — verify), signature crisp, no screen-only chrome. Do not affect the CV print (this sheet only loads on the detail page).

- [ ] **Step 3: Verify with print emulation.**

```python
# /tmp/shoot_print.py
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto("http://127.0.0.1:8003/resume/katharina/?token=localpreview2026", wait_until="networkidle")
    pg.emulate_media(media="print")
    pg.pdf(path="/tmp/cover-print.pdf", format="A4", print_background=True)
    b.close()
```

Run with `~/gitprojects/homepage/.venv/bin/python /tmp/shoot_print.py`; open the PDF; confirm a clean A4 letter.

- [ ] **Step 4: Commit (homepage).** `git add homepage/static/cover-letter/cover-print.css homepage/templates/django_resume/pages/editorial/resume_detail.html && git commit -m "Print the editorial cover letter cleanly on A4"`.

### Task 7: Verification + sign-off

- [ ] **Step 1: django-resume check.** `cd ~/gitprojects/django-resume && just check` → green (the new cover-field tests pass; nothing else in django-resume changed).
- [ ] **Step 2: homepage tests.** `cd ~/gitprojects/homepage && uv run pytest -q` (or the project's test command) → green; the CV page is unchanged.
- [ ] **Step 3: Visual sign-off.** Read the desktop + mobile letter PNGs and the print PDF; confirm header parity with the CV and layout parity with the PDF, both signature paths working, handwriting + hairlines animating with JS and degrading cleanly without it.
- [ ] **Step 4: User review** of the live letter before considering the page final (it stays in homepage; the theme extraction is the separate Backlog item).

---

## Out of scope (tracked in Backlog: "Theme Extraction")

Pulling the finished cover-letter templates + CSS **and** the handwriting into the django-resume editorial theme (self-contained theme, CV/letter parity gates, pipeline repoint, remove homepage overrides/app) is a **separate, later** task. Other homepage work (e.g. the portfolio) lands first. See `docs/dev/backlog.txt` → "Theme Extraction".

## Self-review notes (coverage)

- Spec "cover fields: closing, signature image + name default identity.name" → Task 2 (homepage `CoverPlugin` subclass, zero upstream changes) + Task 4 precedence.
- Spec "identical recognizable header, no photo" → Task 3.
- Spec "layout per PDF" → Tasks 4–5; "Print A4" → Task 6.
- Spec "dev-env stable / uv run safe" → Task 1.
- Spec "handwriting/lines graceful degradation + coexistence" → Task 3 (js-hw) + Task 5 step 4 (lines).
- Spec "self-contained theme / migration / parity gates / pipeline repoint" → deliberately deferred to the Backlog "Theme Extraction" item.

## Known in-browser-iteration steps (not placeholders)

Tasks 5–6 tune spacing/sizing in-browser against the PDF; their gate is the Playwright shoot-and-compare loop (the method used to verify the handwriting linecap fix), not a fixed pixel spec. Structure, class names, fields, and precedence are fully specified; values are committed once they match.
