from __future__ import annotations

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import render
from django.utils.cache import patch_cache_control
from django.utils.translation import gettext

from ..models import Resume
from ..plugins.tokens import TokenPlugin
from .base import (
    ResumePage,
    _is_resume_owner,
    build_base_context,
    build_section_context,
    page_template_name,
    resolve_page_theme,
)
from .registry import page_registry


def render_cv_403(request: HttpRequest, resume: Resume, *, status: int) -> HttpResponse:
    """Render the shared denial template when its section is available."""
    # Resolve the theme once (with fallback to plain) and use it for both the
    # section context and the template, matching ResumePage.serve.
    theme = resolve_page_theme(resume, "cv_403.html")
    base_context = build_base_context(request, resume)
    context = build_section_context(
        request, resume, base_context, ["permission_denied"], theme=theme
    )
    if "permission_denied" not in context:
        if status == 403:
            return HttpResponseForbidden(
                gettext("Access denied"), content_type="text/plain; charset=utf-8"
            )
        return HttpResponse(status=404)
    return render(
        request,
        page_template_name(theme, "cv_403.html"),
        context,
        status=status,
    )


class CoverLetterPage(ResumePage):
    url_name = "detail"
    path = ""
    template_name = "resume_detail.html"
    section_names = ["about", "identity", "cover", "theme"]
    nav_title = "Cover"
    nav_order = 10
    nav_group = "Resume"


class CvPage(ResumePage):
    url_name = "cv"
    path = "cv/"
    template_name = "resume_cv.html"
    section_names = "__all__"
    nav_title = "CV"
    nav_order = 20
    nav_group = "Resume"

    def check_access(self, request: HttpRequest, resume: Resume) -> HttpResponse | None:
        try:
            TokenPlugin.check_permissions(
                request, resume.plugin_data.get(TokenPlugin.name, {}), resume
            )
        except PermissionDenied:
            return render_cv_403(request, resume, status=403)
        return None

    def finalize_response(
        self, response: HttpResponse, request: HttpRequest, resume: Resume
    ) -> HttpResponse:
        if resume.token_is_required:
            # A token-gated CV must not leak via Referer, shared caches or
            # search engines.
            response["Referrer-Policy"] = "no-referrer"
            patch_cache_control(response, private=True, no_store=True)
            response["X-Robots-Tag"] = "noindex"
        return response


class PermissionDeniedPage(ResumePage):
    url_name = "403"
    path = "403/"
    template_name = "cv_403.html"
    nav_title = "403"
    nav_order = 30
    nav_group = "Owner tools"
    # No section_names: serve() renders via render_cv_403 and bypasses get_context.

    def is_visible(self, resume: Resume) -> bool:
        # The 403 editor is only meaningful when the resume gates its CV behind
        # an access token; otherwise no one can ever see the 403 page.
        return resume.token_is_required

    def is_visible_for_request(
        self, resume: Resume, request: HttpRequest | None
    ) -> bool:
        return _is_resume_owner(request, resume) and self.is_visible(resume)

    def check_access(self, request: HttpRequest, resume: Resume) -> HttpResponse | None:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not _is_resume_owner(request, resume):
            return HttpResponse(status=403)
        return None

    def serve(
        self, request: HttpRequest, resume: Resume, base_context: dict
    ) -> HttpResponse:
        return render_cv_403(request, resume, status=200)


def register_builtin_pages() -> None:
    page_registry.register_page_list([CoverLetterPage, CvPage, PermissionDeniedPage])
