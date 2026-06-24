import json
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .formats.json_resume.export import export_resume
from .formats.json_resume.themes import (
    JsonResumeThemeError,
    UnknownThemeCatalogKey,
    catalog_theme,
    dynamic_theme_install_allowed,
    install_catalog_theme,
    install_theme,
    render_catalog_theme,
    render_selected_theme,
    search_themes,
    selected_catalog_theme_key,
    selected_theme_name,
    set_selected_catalog_theme,
    set_selected_theme,
    theme_catalog,
)
from .interchange.coordinator import PathConflictError
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


@login_required
@require_http_methods(["GET"])
def export_json_resume(request: HttpRequest, slug: str) -> HttpResponse:
    """Download one owned resume as a JSON Resume document."""
    resume = get_object_or_404(Resume, slug=slug)
    if resume.owner != request.user:
        return HttpResponse(status=404)
    try:
        result = export_resume(resume)
    except PathConflictError:
        return HttpResponse(
            "Adapter configuration error",
            content_type="text/plain; charset=utf-8",
            status=500,
        )
    if not result.report.valid:
        return HttpResponse(
            "\n".join(result.report.validation_errors),
            content_type="text/plain; charset=utf-8",
            status=422,
        )
    payload = json.dumps(result.document, indent=2, ensure_ascii=False) + "\n"
    response = HttpResponse(payload, content_type="application/json; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{resume.slug}.json"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@require_http_methods(["GET"])
def json_resume_theme_selector(request: HttpRequest, slug: str) -> HttpResponse:
    """Browse JSON Resume catalog themes for one owned resume."""
    resume = get_object_or_404(Resume, slug=slug)
    if resume.owner != request.user:
        return HttpResponse(status=404)
    query = request.GET.get("q", "")
    results = []
    error = ""
    allow_dynamic_install = dynamic_theme_install_allowed()
    if allow_dynamic_install:
        try:
            results = search_themes(query)
        except JsonResumeThemeError as exc:
            error = str(exc)
    return render(
        request,
        "django_resume/json_resume/theme_selector.html",
        {
            "resume": resume,
            "catalog": theme_catalog(),
            "query": query,
            "results": results,
            "selected_theme": selected_theme_name(resume),
            "selected_catalog_key": selected_catalog_theme_key(resume),
            "allow_dynamic_install": allow_dynamic_install,
            "error": error,
            "is_editable": True,
        },
    )


@login_required
@require_http_methods(["POST"])
def install_json_resume_theme(request: HttpRequest, slug: str) -> HttpResponse:
    """Install a dynamic JSON Resume npm theme when explicitly enabled."""
    resume = get_object_or_404(Resume, slug=slug)
    if resume.owner != request.user:
        return HttpResponse(status=404)
    if not dynamic_theme_install_allowed():
        return HttpResponse(status=404)
    package_name = request.POST.get("package", "")
    query = request.POST.get("q", "")
    try:
        install_theme(package_name)
        set_selected_theme(resume, package_name)
    except JsonResumeThemeError as exc:
        results = []
        try:
            results = search_themes(query)
        except JsonResumeThemeError:
            pass
        return render(
            request,
            "django_resume/json_resume/theme_selector.html",
            {
                "resume": resume,
                "catalog": theme_catalog(),
                "query": query,
                "results": results,
                "selected_theme": selected_theme_name(resume),
                "selected_catalog_key": selected_catalog_theme_key(resume),
                "allow_dynamic_install": True,
                "error": str(exc),
                "is_editable": True,
            },
            status=400,
        )
    url = reverse("django_resume:json-resume-themes", kwargs={"slug": resume.slug})
    if query:
        url = f"{url}?{urlencode({'q': query})}"
    return redirect(url)


@login_required
@require_http_methods(["POST"])
def preview_json_resume_catalog_theme(
    request: HttpRequest, slug: str, key: str
) -> HttpResponse:
    """Render a catalog theme without changing the selected theme."""
    resume = get_object_or_404(Resume, slug=slug)
    if resume.owner != request.user:
        return HttpResponse(status=404)
    try:
        entry = catalog_theme(key)
        install_catalog_theme(entry.key)
        rendered = render_catalog_theme(resume, entry.key)
    except UnknownThemeCatalogKey as exc:
        raise Http404 from exc
    except JsonResumeThemeError as exc:
        return HttpResponse(
            str(exc),
            content_type="text/plain; charset=utf-8",
            status=422,
        )
    return _theme_html_response(rendered.html)


@login_required
@require_http_methods(["POST"])
def use_json_resume_catalog_theme(
    request: HttpRequest, slug: str, key: str
) -> HttpResponse:
    """Install a pinned catalog theme and persist it as selected."""
    resume = get_object_or_404(Resume, slug=slug)
    if resume.owner != request.user:
        return HttpResponse(status=404)
    try:
        entry = catalog_theme(key)
        install_catalog_theme(entry.key)
        set_selected_catalog_theme(resume, entry.key)
    except UnknownThemeCatalogKey as exc:
        raise Http404 from exc
    except JsonResumeThemeError as exc:
        return render(
            request,
            "django_resume/json_resume/theme_selector.html",
            {
                "resume": resume,
                "catalog": theme_catalog(),
                "query": "",
                "results": [],
                "selected_theme": selected_theme_name(resume),
                "selected_catalog_key": selected_catalog_theme_key(resume),
                "allow_dynamic_install": dynamic_theme_install_allowed(),
                "error": str(exc),
                "is_editable": True,
            },
            status=400,
        )
    return redirect("django_resume:json-resume-themes", slug=resume.slug)


@login_required
@require_http_methods(["GET"])
def render_json_resume_theme(request: HttpRequest, slug: str) -> HttpResponse:
    """Render the selected JSON Resume theme as private HTML."""
    resume = get_object_or_404(Resume, slug=slug)
    if resume.owner != request.user:
        return HttpResponse(status=404)
    try:
        rendered = render_selected_theme(resume)
    except JsonResumeThemeError as exc:
        return HttpResponse(
            str(exc),
            content_type="text/plain; charset=utf-8",
            status=422,
        )
    return _theme_html_response(rendered.html)


def _theme_html_response(html: str) -> HttpResponse:
    response = HttpResponse(html, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "private, no-store"
    response["Content-Security-Policy"] = _theme_content_security_policy()
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response


def _theme_content_security_policy() -> str:
    style_src = "style-src 'unsafe-inline'"
    script_src = ""
    if getattr(settings, "DJANGO_RESUME_JSON_RESUME_ALLOW_THEME_SCRIPTS", False):
        style_src = "style-src 'unsafe-inline' https://fonts.googleapis.com"
        script_src = " script-src 'unsafe-inline';"
    return (
        "default-src 'none'; img-src 'self' data: https:; "
        f"{style_src};{script_src} font-src data: https:; "
        "base-uri 'none'; form-action 'none'"
    )
