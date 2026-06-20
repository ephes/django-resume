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


def render_cv_403(request: HttpRequest, resume: Resume, *, status: int) -> HttpResponse:
    """Single renderer for cv_403.html, shared by the CV denial path and the
    standalone permission-denied editor, so the two cannot drift."""
    base_context = build_base_context(request, resume)
    context = build_section_context(
        request, resume, base_context, ["permission_denied"]
    )
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

    def check_access(self, request: HttpRequest, resume: Resume) -> HttpResponse | None:
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

    def check_access(self, request: HttpRequest, resume: Resume) -> HttpResponse | None:
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
    page_registry.register_page_list([CoverLetterPage, CvPage, PermissionDeniedPage])
