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
from .formats.json_resume.import_preview import (
    IMPORT_PREVIEW_MAX_AGE_SECONDS,
    ImportConfirmationError,
    ImportPreviewClaims,
    check_confirmation_inputs,
    check_confirmation_plan,
    import_mode,
    input_digest,
    load_import_preview,
    sign_import_preview,
)
from .formats.json_resume.importer import (
    JsonResumeImport,
    JsonResumeImportError,
    MAX_INPUT_BYTES,
    PreparedJsonResumeImport,
    create_prepared_import,
    load_document_bytes,
    load_document_url,
    import_resume_document,
    prepare_resume_import,
)
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
from .forms import JsonResumeImportForm, ResumeForm
from .models import Resume


def _resume_list_context(request: HttpRequest, **extra: Any) -> dict[str, Any]:
    assert request.user.is_authenticated
    context: dict[str, Any] = {
        "is_editable": True,  # needed to include edit styles in the base
        "resumes": Resume.objects.filter(owner=request.user),
        "form": ResumeForm(),
        "import_form": JsonResumeImportForm(),
    }
    context.update(extra)
    return context


@login_required
@require_http_methods(["GET", "POST"])
def resume_list(request: HttpRequest) -> HttpResponse:
    """
    The main resume list view. Only authenticated users can see it.

    You can add and delete your resumes from this view.
    """
    assert request.user.is_authenticated  # type guard just to make mypy happy
    context = _resume_list_context(request)
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


IMPORT_ACTION_PREVIEW = "preview"
IMPORT_ACTION_CREATE = "create"


def _read_uploaded_import(uploaded_file) -> bytes:
    if uploaded_file.size > MAX_INPUT_BYTES:
        raise JsonResumeImportError(
            f"Input exceeds maximum size of {MAX_INPUT_BYTES} bytes"
        )
    return uploaded_file.read()


def _prepare_uploaded_import(
    request: HttpRequest, form: JsonResumeImportForm, data: bytes
) -> PreparedJsonResumeImport:
    document = load_document_bytes(data, source=form.cleaned_data["file"].name)
    return prepare_resume_import(
        document,
        slug=form.cleaned_data["slug"],
        name=form.cleaned_data["name"] or None,
        owner=request.user,
        restore_django_resume_data=not form.cleaned_data["portable_only"],
    )


def _plugin_outline(plugin_data: dict) -> list[dict[str, Any]]:
    outline = []
    for plugin_name, payload in sorted(plugin_data.items()):
        items = payload.get("items") if isinstance(payload, dict) else None
        if isinstance(items, list):
            flat = payload.get("flat")
            fields = len(flat) if isinstance(flat, dict) else 0
            item_count: int | None = len(items)
        else:
            fields = len(payload) if isinstance(payload, dict) else 0
            item_count = None
        outline.append({"name": plugin_name, "fields": fields, "items": item_count})
    return outline


def _confirmation_options(
    request: HttpRequest, form: JsonResumeImportForm
) -> dict[str, str]:
    assert request.user.is_authenticated
    return {
        "owner": str(request.user.pk),
        "slug": form.cleaned_data["slug"],
        "name": form.cleaned_data["name"] or "",
        "mode": import_mode(portable_only=form.cleaned_data["portable_only"]),
    }


def _add_validation_errors(
    form: JsonResumeImportForm, prepared: PreparedJsonResumeImport, field: str
) -> None:
    for error in prepared.report.validation_errors:
        form.add_error(field, error)


def _preview_uploaded_import(
    request: HttpRequest, form: JsonResumeImportForm, context: dict[str, Any]
) -> None:
    """Render what a file-upload import would create without writing anything."""
    uploaded_file = form.cleaned_data["file"]
    data = _read_uploaded_import(uploaded_file)
    prepared = _prepare_uploaded_import(request, form, data)
    if prepared.plan is None:
        _add_validation_errors(form, prepared, "file")
        return
    plan = prepared.plan
    if Resume.objects.filter(slug=plan.slug).exists():
        raise JsonResumeImportError(
            f"A resume with slug {plan.slug!r} already exists", field="slug"
        )
    options = _confirmation_options(request, form)
    digest = input_digest(data)
    token = sign_import_preview(
        ImportPreviewClaims(
            owner=options["owner"],
            input_digest=digest,
            slug=options["slug"],
            name=options["name"],
            mode=options["mode"],
            plan_digest=plan.digest(prepared.report),
        )
    )
    context["import_preview"] = {
        "plan": plan,
        "report": prepared.report,
        "outline": _plugin_outline(plan.plugin_data),
        "owner_name": request.user.get_username(),
        "file_name": uploaded_file.name,
        "file_size": len(data),
        "input_digest": digest,
        "portable_only": form.cleaned_data["portable_only"],
        "keeps_source_document": "source_document"
        in plan.integration_data.get("json_resume", {}),
        "confirmation": token,
        "max_age_minutes": IMPORT_PREVIEW_MAX_AGE_SECONDS // 60,
    }


def _confirm_uploaded_import(
    request: HttpRequest, form: JsonResumeImportForm
) -> JsonResumeImport | None:
    """Create a previewed file-upload import if file, options and plan still match."""
    claims = load_import_preview(request.POST.get("confirmation", ""))
    data = _read_uploaded_import(form.cleaned_data["file"])
    options = _confirmation_options(request, form)
    check_confirmation_inputs(
        claims,
        owner=options["owner"],
        data_digest=input_digest(data),
        slug=options["slug"],
        name=options["name"],
        mode=options["mode"],
    )
    prepared = _prepare_uploaded_import(request, form, data)
    if prepared.plan is None:
        _add_validation_errors(form, prepared, "file")
        return None
    check_confirmation_plan(claims, prepared.plan.digest(prepared.report))
    return create_prepared_import(prepared, owner=request.user)


def _import_from_url(
    request: HttpRequest, form: JsonResumeImportForm
) -> JsonResumeImport | None:
    """Fetch and create in one step; URL imports are not part of the preview."""
    document = load_document_url(form.cleaned_data["source_url"])
    result = import_resume_document(
        document,
        owner=request.user,
        slug=form.cleaned_data["slug"],
        name=form.cleaned_data["name"] or None,
        restore_django_resume_data=not form.cleaned_data["portable_only"],
    )
    if not result.report.valid:
        for error in result.report.validation_errors:
            form.add_error("source_url", error)
        return None
    return result


@login_required
@require_http_methods(["POST"])
def import_json_resume(request: HttpRequest) -> HttpResponse:
    """Import a JSON Resume document as a new owned resume.

    Uploaded files are previewed first (``action=preview``) and created only
    by a later ``action=create`` request that re-uploads the same file with the
    signed preview confirmation. URL imports fetch and create in one request.
    """
    assert request.user.is_authenticated
    form = JsonResumeImportForm(request.POST, request.FILES)
    context = _resume_list_context(request, import_form=form)
    action = request.POST.get("action", "")
    if form.is_valid():
        result = None
        try:
            if form.cleaned_data.get("file") is None:
                if action in {IMPORT_ACTION_PREVIEW, IMPORT_ACTION_CREATE}:
                    raise JsonResumeImportError(
                        "Preview is only available for uploaded files. URL "
                        "imports are not previewed; use Import from URL to "
                        "create the resume directly.",
                        field="source_url",
                    )
                result = _import_from_url(request, form)
            elif action == IMPORT_ACTION_PREVIEW:
                _preview_uploaded_import(request, form, context)
            elif action == IMPORT_ACTION_CREATE:
                result = _confirm_uploaded_import(request, form)
            else:
                raise ImportConfirmationError(
                    "Preview the uploaded file before creating the resume. "
                    "Import from URL only imports from a JSON Resume URL.",
                    field="file",
                )
        except JsonResumeImportError as exc:
            form.add_error(exc.field or "file", str(exc))
            context.pop("import_preview", None)
        except ImportConfirmationError as exc:
            form.add_error(exc.field, str(exc))
        if result is not None:
            context = _resume_list_context(
                request,
                imported_resume=result.resume,
                import_report=result.report,
            )
    return render(
        request, "django_resume/pages/plain/resume_list_main.html", context=context
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
