# Page-Plugins Registry (Internal First Slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the hard-coded `detail`, `cv`, and `403` pages into registered `ResumePage` classes behind identical URLs, so pages become a first-class extension point without new migrations.

**Architecture:** A new `django_resume.pages` package adds a `PageRegistry` singleton (mirroring `plugin_registry`) holding plain-Python `ResumePage` classes. A generic dispatch resolves a `Resume`, runs `check_access` (may short-circuit), builds section context, renders a themed template, and applies `finalize_response`. Built-in pages (`CoverLetterPage`, `CvPage`, `PermissionDeniedPage`) are registered in `AppConfig.ready()`. `urls.py` keeps `list`/`delete`/`cv-redirect` hand-written and generates the page routes from `page_registry.get_urls()`, which emits the bare `<slug:slug>/` catch-all last by construction.

**Tech Stack:** Python 3.10+, Django >=4.2, pytest + pytest-django, mypy. Existing `tests/views_test.py` is the regression net; behavior (URL names, statuses, headers, context keys) must stay identical.

**Reference spec:** `docs/dev/page_plugins.txt`.

**Key constraints discovered during design (do not regress):**
- Test URL namespace is `resume:` (e.g. `reverse("resume:cv", kwargs={"slug": ...})`).
- `TokenPlugin.check_permissions` is a `@staticmethod` taking `(request, plugin_data)`; `TokenPlugin.get_context` returns `{}` (permission side-effect only).
- The CV 403 path must keep `r.context["permission_denied"]` populated and set `Referrer-Policy: no-referrer` (`tests/views_test.py::test_get_cv_view`, `::test_cv_permission_denied_message_renders_sanitized_markdown`).
- A public CV (`token_required=False`) must NOT set `Referrer-Policy` (`::test_public_cv_response_does_not_set_token_referrer_policy`).
- With `TokenPlugin` unregistered, the CV must be accessible (`::test_cv_editable_only_for_authenticated_users`) — so permission enforcement must gate on the token plugin being registered.
- `cv_403.html` (both themes) needs only `permission_denied` + edit flags + `resume`; no other section context.
- `pages.register_builtin_pages()` MUST run before `register_plugins()` in `ready()`, because the first plugin registration imports `django_resume.urls` (side-effect), which calls `page_registry.get_urls()`.

---

## File Structure

- Create `src/django_resume/pages/__init__.py` — re-exports `page_registry`, `ResumePage`, `register_builtin_pages`.
- Create `src/django_resume/pages/registry.py` — `PageRegistry`, `page_registry`, `get_urls()`.
- Create `src/django_resume/pages/base.py` — `ResumePage`, `dispatch_page`, `build_base_context`, `build_section_context`, `page_template_path`, `get_edit_and_show_urls`.
- Create `src/django_resume/pages/builtins.py` — `CoverLetterPage`, `CvPage`, `PermissionDeniedPage`, `render_cv_403`, `register_builtin_pages`.
- Modify `src/django_resume/apps.py` — register built-in pages in `ready()`.
- Modify `src/django_resume/urls.py` — generate page routes from the registry.
- Modify `src/django_resume/views.py` — remove the three page views and helpers moved to `pages`.
- Create `tests/pages/__init__.py`, `tests/pages/registry_test.py`, `tests/pages/base_test.py`, `tests/pages/builtins_test.py`.

---

## Task 1: PageRegistry and singleton

**Files:**
- Create: `src/django_resume/pages/__init__.py`
- Create: `src/django_resume/pages/registry.py`
- Create: `src/django_resume/pages/base.py` (minimal stub for typing import)
- Test: `tests/pages/__init__.py`, `tests/pages/registry_test.py`

- [ ] **Step 1: Create the test package init**

Create `tests/pages/__init__.py` as an empty file.

- [ ] **Step 2: Write the failing registry test**

Create `tests/pages/registry_test.py`:

```python
from django_resume.pages.base import ResumePage
from django_resume.pages.registry import PageRegistry


class DummyPage(ResumePage):
    url_name = "dummy"
    path = "dummy/"
    template_name = "dummy.html"
    section_names: list[str] = []


def test_register_and_get_page():
    registry = PageRegistry()
    registry.register(DummyPage)

    page = registry.get_page("dummy")
    assert isinstance(page, DummyPage)
    assert registry.get_page("missing") is None
    assert [type(p) for p in registry.get_all_pages()] == [DummyPage]


def test_register_page_list_and_unregister():
    registry = PageRegistry()
    registry.register_page_list([DummyPage])
    assert registry.get_page("dummy") is not None

    registry.unregister(DummyPage)
    assert registry.get_page("dummy") is None
    assert registry.get_all_pages() == []
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest tests/pages/registry_test.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'django_resume.pages'`.

- [ ] **Step 4: Create the minimal base stub**

Create `src/django_resume/pages/base.py`:

```python
from __future__ import annotations


class ResumePage:
    """Base class for a registered resume page. Expanded in Task 2."""

    url_name: str = ""
    path: str = ""
    template_name: str = ""
    section_names: list[str] | str = []
```

- [ ] **Step 5: Create the registry**

Create `src/django_resume/pages/registry.py`:

```python
from __future__ import annotations

from .base import ResumePage


class PageRegistry:
    """Registry of resume page classes, mirroring the plugin registry."""

    def __init__(self) -> None:
        self.pages: dict[str, ResumePage] = {}

    def register(self, page_class: type[ResumePage]) -> None:
        self.pages[page_class.url_name] = page_class()

    def register_page_list(self, page_classes: list[type[ResumePage]]) -> None:
        for page_class in page_classes:
            self.register(page_class)

    def unregister(self, page_class: type[ResumePage]) -> None:
        self.pages.pop(page_class.url_name, None)

    def get_page(self, url_name: str) -> ResumePage | None:
        return self.pages.get(url_name)

    def get_all_pages(self) -> list[ResumePage]:
        return list(self.pages.values())


# Module-level singleton (shared across the application).
page_registry = PageRegistry()
```

- [ ] **Step 6: Create the package init**

Create `src/django_resume/pages/__init__.py`:

```python
from .base import ResumePage
from .registry import PageRegistry, page_registry

__all__ = ["ResumePage", "PageRegistry", "page_registry"]
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `uv run pytest tests/pages/registry_test.py -v`
Expected: PASS (2 passed).

- [ ] **Step 8: Commit**

```bash
git add src/django_resume/pages tests/pages
git commit -m "Add page registry skeleton"
```

---

## Task 2: ResumePage base, section selection, and context helpers

**Files:**
- Modify: `src/django_resume/pages/base.py`
- Test: `tests/pages/base_test.py`

- [ ] **Step 1: Write the failing base test**

Create `tests/pages/base_test.py`:

```python
import pytest
from django.test import RequestFactory

from django_resume.pages.base import (
    ResumePage,
    build_base_context,
    build_section_context,
    page_template_path,
)
from django_resume.plugins import plugin_registry


@pytest.mark.django_db
def test_build_section_context_explicit_list(resume):
    resume.owner.save()
    resume.save()
    request = RequestFactory().get("/john-doe/")
    request.user = resume.owner

    context = build_section_context(request, resume, {}, ["identity", "about"])

    assert "identity" in context
    assert "about" in context
    assert "skills" not in context


@pytest.mark.django_db
def test_build_section_context_all(resume):
    resume.owner.save()
    resume.save()
    request = RequestFactory().get("/john-doe/")
    request.user = resume.owner

    context = build_section_context(request, resume, {}, "__all__")

    registered = {p.name for p in plugin_registry.get_all_plugins()}
    assert registered.issubset(set(context))


@pytest.mark.django_db
def test_build_base_context_owner_vs_anonymous(resume, django_user_model):
    from django.contrib.auth.models import AnonymousUser

    resume.owner.save()
    resume.save()

    owner_request = RequestFactory().get("/john-doe/?edit=true")
    owner_request.user = resume.owner
    owner_context = build_base_context(owner_request, resume)
    assert owner_context["is_editable"] is True
    assert owner_context["show_edit_button"] is True

    anon_request = RequestFactory().get("/john-doe/?edit=true")
    anon_request.user = AnonymousUser()
    anon_context = build_base_context(anon_request, resume)
    assert anon_context["is_editable"] is False
    assert anon_context["show_edit_button"] is False


def test_page_template_path_uses_theme(resume):
    assert (
        page_template_path(resume, "resume_cv.html")
        == "django_resume/pages/plain/resume_cv.html"
    )


def test_default_page_hooks():
    page = ResumePage()
    rf = RequestFactory().get("/")
    assert page.check_access(rf, None) is None
    sentinel = object()
    assert page.finalize_response(sentinel, rf, None) is sentinel
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/pages/base_test.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_base_context'`.

- [ ] **Step 3: Implement the base module**

Replace the entire contents of `src/django_resume/pages/base.py`:

```python
from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from ..models import Resume
from ..plugins import plugin_registry


def get_edit_and_show_urls(request: HttpRequest) -> tuple[str, str]:
    query_params = request.GET.copy()
    if "edit" in query_params:
        query_params.pop("edit")

    show_url = f"{request.path}?{query_params.urlencode()}"
    query_params["edit"] = "true"
    edit_url = f"{request.path}?{query_params.urlencode()}"
    return edit_url, show_url


def build_base_context(request: HttpRequest, resume: Resume) -> dict:
    edit = bool(dict(request.GET).get("edit", False))
    is_editable = request.user.is_authenticated and resume.owner == request.user
    show_edit_button = bool(is_editable and edit)
    edit_url, show_url = get_edit_and_show_urls(request)
    return {
        "resume": resume,
        "is_editable": is_editable,
        "show_edit_button": show_edit_button,
        "edit_url": edit_url,
        "show_url": show_url,
    }


def build_section_context(
    request: HttpRequest,
    resume: Resume,
    base_context: dict,
    section_names: list[str] | str,
) -> dict:
    show_edit_button = base_context.get("show_edit_button", False)
    theme = resume.current_theme
    if section_names == "__all__":
        plugins = plugin_registry.get_all_plugins()
    else:
        plugins = [
            plugin
            for plugin in (plugin_registry.get_plugin(name) for name in section_names)
            if plugin is not None
        ]
    # Each plugin receives a fresh empty per-plugin context (context={}),
    # exactly as the current resume_detail / resume_cv views do. Page-level
    # data lives in base_context; plugins are not meant to see each other's
    # context. Do NOT pass base_context here — that would change behavior.
    for plugin in plugins:
        base_context[plugin.name] = plugin.get_context(
            request,
            plugin.get_data(resume),
            resume.pk,
            context={},
            edit=show_edit_button,
            theme=theme,
        )
    return base_context


def page_template_path(resume: Resume, template_name: str) -> str:
    return f"django_resume/pages/{resume.current_theme}/{template_name}"


class ResumePage:
    """Base class for a registered resume page."""

    url_name: str = ""
    path: str = ""
    template_name: str = ""
    section_names: list[str] | str = []

    def check_access(
        self, request: HttpRequest, resume: Resume
    ) -> HttpResponse | None:
        """Return None to proceed, or a response to short-circuit."""
        return None

    def get_context(
        self, request: HttpRequest, resume: Resume, *, base_context: dict
    ) -> dict:
        return build_section_context(request, resume, base_context, self.section_names)

    def serve(
        self, request: HttpRequest, resume: Resume, base_context: dict
    ) -> HttpResponse:
        """Build the page response. Override to take full control of rendering."""
        context = self.get_context(request, resume, base_context=base_context)
        return render(
            request, page_template_path(resume, self.template_name), context
        )

    def finalize_response(
        self, response: HttpResponse, request: HttpRequest, resume: Resume
    ) -> HttpResponse:
        """Post-process every returned response (e.g. headers)."""
        return response


def dispatch_page(request: HttpRequest, slug: str, page: ResumePage) -> HttpResponse:
    resume = get_object_or_404(Resume.objects.select_related("owner"), slug=slug)
    denied = page.check_access(request, resume)
    if denied is not None:
        return page.finalize_response(denied, request, resume)
    base_context = build_base_context(request, resume)
    response = page.serve(request, resume, base_context)
    return page.finalize_response(response, request, resume)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/pages/base_test.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/django_resume/pages/base.py tests/pages/base_test.py
git commit -m "Add ResumePage base and page context helpers"
```

---

## Task 3: get_urls() with catch-all-last ordering

**Files:**
- Modify: `src/django_resume/pages/registry.py`
- Test: `tests/pages/registry_test.py`

- [ ] **Step 1: Write the failing ordering test**

Append to `tests/pages/registry_test.py`:

```python
class RootPage(ResumePage):
    url_name = "root"
    path = ""
    template_name = "root.html"
    section_names: list[str] = []


class CvLikePage(ResumePage):
    url_name = "cv-like"
    path = "cv/"
    template_name = "cv.html"
    section_names: list[str] = []


def test_get_urls_emits_bare_catch_all_last():
    registry = PageRegistry()
    # Register root first to prove ordering is structural, not registration order.
    registry.register_page_list([RootPage, CvLikePage])

    patterns = registry.get_urls()
    routes = [str(p.pattern) for p in patterns]
    names = [p.name for p in patterns]

    assert routes[-1] == "<slug:slug>/"
    assert names[-1] == "root"
    assert "<slug:slug>/cv/" in routes
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/pages/registry_test.py::test_get_urls_emits_bare_catch_all_last -v`
Expected: FAIL with `AttributeError: 'PageRegistry' object has no attribute 'get_urls'`.

- [ ] **Step 3: Implement get_urls**

Add this import at the top of `src/django_resume/pages/registry.py` (below the existing `from .base import ResumePage`):

```python
from django.urls import URLPattern, path
from django.views.decorators.http import require_http_methods

from .base import dispatch_page
```

Add this method to `PageRegistry` (after `get_all_pages`):

```python
    def get_urls(self) -> list[URLPattern]:
        def make_view(page: ResumePage):
            @require_http_methods(["GET"])
            def view(request, slug):
                return dispatch_page(request, slug, page)

            return view

        # Sort so the bare "<slug:slug>/" catch-all (path == "") is emitted last.
        pages = sorted(self.get_all_pages(), key=lambda p: (p.path == "", p.path))
        return [
            path(f"<slug:slug>/{page.path}", make_view(page), name=page.url_name)
            for page in pages
        ]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/pages/registry_test.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/django_resume/pages/registry.py tests/pages/registry_test.py
git commit -m "Generate page routes with catch-all emitted last"
```

---

## Task 4: Built-in pages and the shared 403 renderer

**Files:**
- Create: `src/django_resume/pages/builtins.py`
- Modify: `src/django_resume/pages/__init__.py`
- Test: `tests/pages/builtins_test.py`

- [ ] **Step 1: Write the failing builtins test**

Create `tests/pages/builtins_test.py`:

```python
import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from django_resume.pages.builtins import CvPage, render_cv_403
from django_resume.plugins import plugin_registry, TokenPlugin


@pytest.mark.django_db
def test_cv_check_access_allows_when_token_unregistered(resume):
    resume.owner.save()
    resume.save()
    plugin_registry.unregister(TokenPlugin)

    request = RequestFactory().get("/john-doe/cv/")
    request.user = AnonymousUser()

    assert CvPage().check_access(request, resume) is None


@pytest.mark.django_db
def test_cv_check_access_denies_without_token(resume):
    resume.owner.save()
    resume.save()
    plugin_registry.register(TokenPlugin)

    request = RequestFactory().get("/john-doe/cv/")
    request.user = AnonymousUser()

    response = CvPage().check_access(request, resume)
    assert response is not None
    assert response.status_code == 403


@pytest.mark.django_db
def test_render_cv_403_includes_permission_denied_context(resume):
    resume.owner.save()
    resume.plugin_data["permission_denied"] = {
        "title": "Access Token Needed for CV",
        "email": "tokensupport@example.com",
        "text": "hello",
    }
    resume.save()

    request = RequestFactory().get("/john-doe/cv/")
    request.user = AnonymousUser()

    response = render_cv_403(request, resume, status=403)
    assert response.status_code == 403
    assert b"Access Token Needed for CV" in response.content
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/pages/builtins_test.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'django_resume.pages.builtins'`.

- [ ] **Step 3: Implement the built-in pages**

Create `src/django_resume/pages/builtins.py`:

```python
from __future__ import annotations

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from ..models import Resume
from ..plugins import plugin_registry
from ..plugins.tokens import TokenPlugin
from .base import (
    ResumePage,
    build_base_context,
    build_section_context,
    page_template_path,
)
from .registry import page_registry


def render_cv_403(
    request: HttpRequest, resume: Resume, *, status: int
) -> HttpResponse:
    """Single renderer for cv_403.html, shared by the CV denial path and the
    standalone permission-denied editor, so the two cannot drift."""
    base_context = build_base_context(request, resume)
    context = build_section_context(request, resume, base_context, ["permission_denied"])
    if "permission_denied" not in context:
        return HttpResponse(status=404)
    return render(
        request, page_template_path(resume, "cv_403.html"), context, status=status
    )


class CoverLetterPage(ResumePage):
    url_name = "detail"
    path = ""
    template_name = "resume_detail.html"
    section_names = ["about", "identity", "cover", "theme"]


class CvPage(ResumePage):
    url_name = "cv"
    path = "cv/"
    template_name = "resume_cv.html"
    section_names = "__all__"

    def check_access(
        self, request: HttpRequest, resume: Resume
    ) -> HttpResponse | None:
        token_plugin = plugin_registry.get_plugin(TokenPlugin.name)
        if token_plugin is None:
            return None
        try:
            TokenPlugin.check_permissions(
                request, resume.plugin_data.get(TokenPlugin.name, {})
            )
        except PermissionDenied:
            return render_cv_403(request, resume, status=403)
        return None

    def finalize_response(
        self, response: HttpResponse, request: HttpRequest, resume: Resume
    ) -> HttpResponse:
        if resume.token_is_required:
            response["Referrer-Policy"] = "no-referrer"
        return response


class PermissionDeniedPage(ResumePage):
    url_name = "403"
    path = "403/"
    template_name = "cv_403.html"

    def check_access(
        self, request: HttpRequest, resume: Resume
    ) -> HttpResponse | None:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if resume.owner != request.user:
            return HttpResponse(status=403)
        return None

    def serve(
        self, request: HttpRequest, resume: Resume, base_context: dict
    ) -> HttpResponse:
        # Render through the shared cv_403 renderer (status 200 for the editor)
        # so the standalone 403 page cannot drift from the CV denial path and
        # keeps render_cv_403's missing-permission_denied 404 behavior.
        return render_cv_403(request, resume, status=200)


def register_builtin_pages() -> None:
    page_registry.register_page_list(
        [CoverLetterPage, CvPage, PermissionDeniedPage]
    )
```

- [ ] **Step 4: Export the registration helper**

Replace the contents of `src/django_resume/pages/__init__.py`:

```python
from .base import ResumePage
from .builtins import register_builtin_pages
from .registry import PageRegistry, page_registry

__all__ = [
    "ResumePage",
    "PageRegistry",
    "page_registry",
    "register_builtin_pages",
]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `uv run pytest tests/pages/builtins_test.py -v`
Expected: PASS (3 passed).

> Note: these tests mutate the global `plugin_registry` (register/unregister `TokenPlugin`), matching the pattern in `tests/views_test.py`. Run the new page tests together to confirm no cross-test ordering issue:
> Run: `uv run pytest tests/pages -v` → Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add src/django_resume/pages/builtins.py src/django_resume/pages/__init__.py tests/pages/builtins_test.py
git commit -m "Add built-in resume pages and shared 403 renderer"
```

---

## Task 5: Register built-in pages in AppConfig.ready()

**Files:**
- Modify: `src/django_resume/apps.py`

- [ ] **Step 1: Add page registration before plugin registration**

Replace the contents of `src/django_resume/apps.py`:

```python
from django.apps import AppConfig


class ResumeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_resume"

    @staticmethod
    def register_pages() -> None:
        from .pages import register_builtin_pages

        register_builtin_pages()

    @staticmethod
    def register_plugins() -> None:
        from . import plugins

        plugins.plugin_registry.register_plugin_list(
            [
                plugins.FreelanceTimelinePlugin,
                plugins.EmployedTimelinePlugin,
                plugins.EducationPlugin,
                plugins.PermissionDeniedPlugin,
                plugins.ProjectsPlugin,
                plugins.AboutPlugin,
                plugins.SkillsPlugin,
                plugins.ThemePlugin,
                plugins.TokenPlugin,
                plugins.IdentityPlugin,
                plugins.CoverPlugin,
            ]
        )

    def ready(self) -> None:
        # Pages must be registered before plugins: the first plugin
        # registration imports django_resume.urls, which calls
        # page_registry.get_urls(). If pages were not yet registered, the
        # generated page routes would be empty.
        self.register_pages()
        self.register_plugins()
```

- [ ] **Step 2: Run the full suite to confirm pages are dormant but harmless**

Run: `uv run pytest -q`
Expected: PASS (same count as before this task; pages are registered but `urls.py` still uses the old views).

- [ ] **Step 3: Commit**

```bash
git add src/django_resume/apps.py
git commit -m "Register built-in pages on app ready"
```

---

## Task 6: Cut over urls.py and slim views.py

**Files:**
- Modify: `src/django_resume/urls.py`
- Modify: `src/django_resume/views.py`

- [ ] **Step 1: Confirm the old view callables are referenced only by urls.py**

Run: `git grep -nE "views\.(resume_detail|resume_cv|cv_403)"`
Expected: matches only in `src/django_resume/urls.py`.

Run: `git grep -nE "import[^\n]*\b(resume_detail|resume_cv|cv_403)\b"`
Expected: no matches (no module does `from ... import resume_detail/resume_cv/cv_403`).

Note: do NOT grep for the moved helpers (`get_edit_and_show_urls`, `set_cv_referrer_policy`, `get_context_from_plugins`, `render_cv_403`) here — they intentionally exist in both `views.py` and the new `pages/` package during this dormant phase and are removed from `views.py` in Step 3. If either grep above finds a module importing the view callables directly, update it to use the page registry / `reverse` before continuing.

- [ ] **Step 2: Rewrite urls.py**

Replace the contents of `src/django_resume/urls.py`:

```python
from django.urls import path, reverse
from django.views.generic import RedirectView

from . import views
from .pages import page_registry


class CvRedirectView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs) -> str:
        slug = kwargs["slug"]
        return reverse("django_resume:cv", kwargs={"slug": slug})


app_name = "django_resume"
urlpatterns = [
    # resumes (non-page routes)
    path("", views.resume_list, name="list"),
    path("<slug:slug>/delete/", views.resume_delete, name="delete"),
    path("cv/<slug:slug>/", CvRedirectView.as_view(), name="cv-redirect"),
    # cover, cv and 403 pages (generated; bare "<slug:slug>/" catch-all is last)
    *page_registry.get_urls(),
]
```

- [ ] **Step 3: Slim views.py**

Replace the contents of `src/django_resume/views.py`:

```python
from typing import Any

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods

from .forms import ResumeForm
from .models import Resume


@login_required
@require_http_methods(["GET", "POST"])
def resume_list(request: HttpRequest) -> HttpResponse:
    """
    The main resume list view. Only authenticated users can see it.

    You can add and delete your resumes from this view.
    """
    assert request.user.is_authenticated  # type guard just to make mypy happy
    my_resumes = Resume.objects.filter(owner=request.user)
    context: dict[str, Any] = {
        "is_editable": True,  # needed to include edit styles in the base
        "resumes": my_resumes,
        "form": ResumeForm(),
    }
    if request.method == "POST":
        form = ResumeForm(request.POST)
        context["form"] = form
        if form.is_valid():
            resume = form.save(commit=False)
            resume.owner = request.user
            resume.save()
            context["new_resume"] = resume
        return render(
            request, "django_resume/pages/plain/resume_list_main.html", context=context
        )
    else:
        # just render the complete template on GET
        return render(
            request, "django_resume/pages/plain/resume_list.html", context=context
        )


@login_required
@require_http_methods(["DELETE"])
def resume_delete(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Delete a resume.

    Only the owner of the resume can delete it.
    """
    resume = get_object_or_404(Resume, slug=slug)
    if resume.owner != request.user:
        return HttpResponse(status=403)

    resume.delete()
    return HttpResponse(status=200)  # 200 instead of 204 for htmx compatibility
```

- [ ] **Step 4: Run the full regression suite**

Run: `uv run pytest tests/views_test.py -v`
Expected: PASS — every existing view test (detail public/edit, CV token 403 + Referrer-Policy, public-CV no referrer, permission_denied markdown in 403 context, CV editability, headwind detail) stays green with identical behavior.

- [ ] **Step 5: Run the whole suite**

Run: `uv run pytest -q`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add src/django_resume/urls.py src/django_resume/views.py
git commit -m "Route detail/cv/403 through the page registry"
```

---

## Task 7: Regression tests for the de-coupling improvements

**Files:**
- Test: `tests/pages/builtins_test.py`

- [ ] **Step 1: Write route and access-control regression tests**

First, add `from django.urls import reverse` to the import block at the top of `tests/pages/builtins_test.py` so it reads:

```python
import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory
from django.urls import reverse

from django_resume.pages.builtins import CvPage, render_cv_403
from django_resume.plugins import plugin_registry, TokenPlugin
```

Then append these test functions to the end of the file:

```python
# Order-independence of the 403 context is structural: render_cv_403 fetches the
# permission_denied plugin BY NAME (build_section_context(["permission_denied"]))
# rather than relying on iteration stopping at the token plugin. That by-name
# fetch is covered by test_render_cv_403_includes_permission_denied_context
# (Task 4) and the existing
# test_cv_permission_denied_message_renders_sanitized_markdown, so no fragile
# global-registry-reordering test is needed here.


@pytest.mark.django_db
def test_permission_denied_editor_route_is_owner_only(client, resume, django_user_model):
    resume.owner.save()
    resume.plugin_data["permission_denied"] = {
        "title": "Access Token Needed for CV",
        "email": "tokensupport@example.com",
        "text": "hello",
    }
    resume.save()
    url = reverse("resume:403", kwargs={"slug": resume.slug})

    # Anonymous -> redirected to login
    r = client.get(url)
    assert r.status_code == 302
    assert "login" in r.url

    # Authenticated non-owner -> 403
    other = django_user_model.objects.create_user(username="other", password="pw")
    client.force_login(other)
    assert client.get(url).status_code == 403

    # Owner -> 200 with the permission_denied editor content (via render_cv_403)
    client.force_login(resume.owner)
    r = client.get(url)
    assert r.status_code == 200
    assert "Access Token Needed for CV" in r.content.decode("utf-8")


def test_builtin_pages_registered():
    from django_resume.pages import page_registry

    assert {p.url_name for p in page_registry.get_all_pages()} >= {
        "detail",
        "cv",
        "403",
    }


def test_detail_route_is_the_bare_catch_all():
    from django_resume.pages import page_registry

    patterns = page_registry.get_urls()
    assert str(patterns[-1].pattern) == "<slug:slug>/"
    assert patterns[-1].name == "detail"
```

- [ ] **Step 2: Run the new tests**

Run: `uv run pytest tests/pages/builtins_test.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/pages/builtins_test.py
git commit -m "Test page route ordering and order-independent 403 context"
```

---

## Task 8: Documentation

**Files:**
- Modify: `docs/dev/page_plugins.txt`
- Modify: `docs/dev/backlog.txt`

- [ ] **Step 1: Mark the first slice implemented in the spec**

In `docs/dev/page_plugins.txt`, change the intro sentence that begins "The research questions have been answered" to add, at the end of that paragraph, a sentence:

```
The internal-registry first slice described in `Implementation Sketch`_ has
been implemented in ``django_resume.pages``; ``CvPage`` keeps ``section_names
= "__all__"`` for a faithful first cut, and switching it to an explicit list
is a deliberate follow-up.
```

- [ ] **Step 2: Rescope the backlog item**

In `docs/dev/backlog.txt`, update the "Build pluggable resume pages and site structure." item body to note the internal registry slice is implemented (detail/cv/403 now registered `ResumePage` classes behind identical URLs) and that remaining work is third-party page discovery, navigation metadata, and capability-based section selection.

- [ ] **Step 3: Validate the docs build**

Run: `cd docs && uv run --with-requirements requirements.txt sphinx-build -q -b html -W --keep-going . _build/check && cd ..`
Expected: clean build, no warnings-as-errors.

- [ ] **Step 4: Commit**

```bash
git add docs/dev/page_plugins.txt docs/dev/backlog.txt
git commit -m "Document implemented page-registry first slice"
```

---

## Task 9: Final validation

- [ ] **Step 1: Run the full project check**

Run: `just check`
Expected: lint, `mypy src/`, and the full test suite all pass. If mypy flags the new `pages` module, fix annotations to match (notably `section_names: list[str] | str` and `HttpResponse | None` return types) without loosening to `Any`.

- [ ] **Step 2: Confirm a clean working tree**

Run: `git status --short`
Expected: empty (everything committed; `uv.lock` was already committed on this branch's base and is untouched).

---

## Self-Review

**Spec coverage** (against `docs/dev/page_plugins.txt`):
- Separate `page_registry` mirroring `plugin_registry` → Task 1.
- Plain Python `ResumePage` classes, no model-per-type, no migration → Tasks 2 & 4 (no `models.py` changes).
- Built-ins registered in core via `AppConfig.ready` → Task 5.
- `path` subsegment under `<slug:slug>/`; bare catch-all emitted last by construction → Task 3 (`get_urls` sort) + Task 6 (urls cutover) + Task 7 (assertion).
- `section_names` as inclusion filter; explicit list + `"__all__"` both supported → Task 2 (`build_section_context`), exercised by `CoverLetterPage` (list) and `CvPage` (`"__all__"`).
- `check_access -> HttpResponse | None`; token logic stays in `TokenPlugin.check_permissions` → Task 4 (`CvPage.check_access`).
- `finalize_response` sets Referrer-Policy on success AND 403, applied to every returned response → Task 2 (`dispatch_page` applies it on both paths) + Task 4 (`CvPage.finalize_response`).
- Explicit, order-independent 403 context via one shared renderer → Task 4 (`render_cv_403` reusing `build_section_context`, used by BOTH `CvPage.check_access` denial and `PermissionDeniedPage.serve`) + Task 4 unit test (`test_render_cv_403_includes_permission_denied_context`). Order-independence is structural (by-name fetch), so no global-reorder test is used.
- `cv-redirect` stays a plain redirect, not a page → Task 6 (kept hand-written).
- Themed template resolution `pages/{theme}/{template_name}` → Task 2 (`page_template_path`).

**Placeholder scan:** No TBD/TODO; every code step includes complete code; every run step includes an exact command and expected result.

**Type consistency:** `build_section_context(request, resume, base_context, section_names)`, `build_base_context(request, resume)`, `page_template_path(resume, template_name)`, `render_cv_403(request, resume, *, status)`, `dispatch_page(request, slug, page)`, and `ResumePage.{check_access,get_context,serve,finalize_response}` signatures are used identically across Tasks 2–6 (`dispatch_page` calls `page.serve(...)`; `PermissionDeniedPage` overrides `serve`). `url_name`/`path`/`template_name`/`section_names` attribute names match between `ResumePage`, the registry, and the built-ins.

**Scope:** Single subsystem (page registry + built-in conversion); identical external behavior; no third-party discovery, navigation, or capability tags (correctly deferred per spec).
