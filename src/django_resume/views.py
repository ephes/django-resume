import json
from typing import Any
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from .formats.json_resume.export import export_resume
from .formats.json_resume.themes import (
    JsonResumeThemeError,
    install_theme,
    render_selected_theme,
    search_themes,
    selected_theme_name,
    set_selected_theme,
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
    """Search and apply JSON Resume npm themes for one owned resume."""
    resume = get_object_or_404(Resume, slug=slug)
    if resume.owner != request.user:
        return HttpResponse(status=404)
    query = request.GET.get("q", "")
    results = []
    error = ""
    try:
        results = search_themes(query)
    except JsonResumeThemeError as exc:
        error = str(exc)
    return render(
        request,
        "django_resume/json_resume/theme_selector.html",
        {
            "resume": resume,
            "query": query,
            "results": results,
            "selected_theme": selected_theme_name(resume),
            "error": error,
            "is_editable": True,
        },
    )


@login_required
@require_http_methods(["POST"])
def install_json_resume_theme(request: HttpRequest, slug: str) -> HttpResponse:
    """Install a JSON Resume npm theme and apply it to one owned resume."""
    resume = get_object_or_404(Resume, slug=slug)
    if resume.owner != request.user:
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
                "query": query,
                "results": results,
                "selected_theme": selected_theme_name(resume),
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
    response = HttpResponse(rendered.html, content_type="text/html; charset=utf-8")
    response["Cache-Control"] = "private, no-store"
    response["Content-Security-Policy"] = (
        "default-src 'none'; img-src 'self' data: https:; style-src 'unsafe-inline'; "
        "font-src data: https:; base-uri 'none'; form-action 'none'"
    )
    response["X-Frame-Options"] = "SAMEORIGIN"
    return response
