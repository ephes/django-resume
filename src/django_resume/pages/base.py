from __future__ import annotations

from dataclasses import dataclass

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from ..models import Resume
from ..plugins import plugin_registry


@dataclass(frozen=True)
class ByCapability:
    """Select section plugins by capability tag rather than by name.

    Assign it to a page's :attr:`ResumePage.section_names` to include every
    registered plugin whose :attr:`~django_resume.plugins.base.Plugin.capabilities`
    satisfy this selector. ``match="any"`` (the default) includes a plugin that
    carries at least one requested capability; ``match="all"`` requires every
    one. An empty capability set matches nothing.

    Prefer the :func:`by_capability` factory for the ergonomic call site
    ``by_capability("portfolio")`` / ``by_capability("a", "b", match="all")``.
    """

    capabilities: tuple[str, ...]
    match: str = "any"

    def __post_init__(self) -> None:
        if self.match not in ("any", "all"):
            raise ValueError(
                f"ByCapability.match must be 'any' or 'all', got {self.match!r}"
            )

    def matches(self, plugin: object) -> bool:
        wanted = set(self.capabilities)
        if not wanted:
            return False
        have = set(getattr(plugin, "capabilities", ()) or ())
        if self.match == "all":
            return wanted <= have
        return bool(wanted & have)


def by_capability(*capabilities: str, match: str = "any") -> ByCapability:
    """Build a :class:`ByCapability` selector from positional capability tags."""
    return ByCapability(capabilities=capabilities, match=match)


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
    section_names: list[str] | str | ByCapability,
) -> dict:
    show_edit_button = base_context.get("show_edit_button", False)
    theme = resume.current_theme
    if isinstance(section_names, ByCapability):
        plugins = [
            plugin
            for plugin in plugin_registry.get_all_plugins()
            if section_names.matches(plugin)
        ]
    elif section_names == "__all__":
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
    section_names: list[str] | str | ByCapability = []
    # Human-friendly label for navigation menus. Empty means "do not advertise
    # this page in navigation" (e.g. the bare detail page can still set one).
    nav_title: str = ""
    # Explicit navigation ordering. Lower sorts first; equal values fall back to
    # registration order via a stable sort, so nav is deterministic across
    # built-ins and third-party pages without relying on import timing.
    nav_order: int = 0
    # Navigation group label. Links sharing a ``nav_group`` render together; the
    # empty default keeps a page in the implicit ungrouped bucket.
    nav_group: str = ""

    def check_access(self, request: HttpRequest, resume: Resume) -> HttpResponse | None:
        """Return None to proceed, or a response to short-circuit."""
        return None

    def is_visible(self, resume: Resume) -> bool:
        """Whether this page should be advertised in navigation for ``resume``.

        Override for pages that are only relevant in some states (e.g. the 403
        editor, which only matters when the resume requires an access token)."""
        return True

    def nav_url(self, resume: Resume) -> str:
        """The URL of this page for ``resume``.

        Uses the ``django_resume`` application namespace so it resolves
        regardless of the instance namespace an integrator mounts the app under."""
        return reverse(f"django_resume:{self.url_name}", kwargs={"slug": resume.slug})

    def get_context(
        self, request: HttpRequest, resume: Resume, *, base_context: dict
    ) -> dict:
        return build_section_context(request, resume, base_context, self.section_names)

    def serve(
        self, request: HttpRequest, resume: Resume, base_context: dict
    ) -> HttpResponse:
        """Build the page response. Override to take full control of rendering."""
        context = self.get_context(request, resume, base_context=base_context)
        return render(request, page_template_path(resume, self.template_name), context)

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
