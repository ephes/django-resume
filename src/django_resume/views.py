from typing import Any

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.urls import NoReverseMatch
from django.views.decorators.http import require_http_methods

from .forms import ResumeForm, PluginForm
from .models import Resume, Plugin
from .plugin_generator import generate_simple_plugin
from .plugins import plugin_registry, SimplePlugin
from .plugins.base import ContextDict


def get_edit_and_show_urls(request: HttpRequest) -> tuple[str, str]:
    query_params = request.GET.copy()
    if "edit" in query_params:
        query_params.pop("edit")

    show_url = f"{request.path}?{query_params.urlencode()}"
    query_params["edit"] = "true"
    edit_url = f"{request.path}?{query_params.urlencode()}"
    return edit_url, show_url


def get_context_from_plugins(
    request: HttpRequest, resume: Resume, context: ContextDict
) -> ContextDict:
    show_edit_button = context.get("show_edit_button", False)
    for plugin in plugin_registry.get_all_plugins():
        context[plugin.name] = plugin.get_context(
            request,
            plugin.get_data(resume),
            resume.pk,
            context={},
            edit=show_edit_button,
            theme=resume.current_theme,
        )
    return context


def resume_cv(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Show a CV view of the resume.

    By default, you need a token to be able to see the CV.
    """
    resume = get_object_or_404(Resume.objects.select_related("owner"), slug=slug)

    edit = bool(dict(request.GET).get("edit", False))
    is_editable = request.user.is_authenticated and resume.owner == request.user
    show_edit_button = True if is_editable and edit else False

    edit_url, show_url = get_edit_and_show_urls(request)
    context = {
        "resume": resume,
        "timelines": [],
        "projects": [],
        "db_plugins": plugin_registry.get_all_db_plugins(),
        # needed to include edit styles in the base template
        "show_edit_button": show_edit_button,
        "is_editable": is_editable,
        "edit_url": edit_url,
        "show_url": show_url,
    }
    try:
        context = get_context_from_plugins(request, resume, context)
    except PermissionDenied:
        # invalid or missing token for example
        return render(
            request,
            f"django_resume/pages/{resume.current_theme}/cv_403.html",
            context=context,
            status=403,
        )
    return render(
        request,
        f"django_resume/pages/{resume.current_theme}/resume_cv.html",
        context=context,
    )


@require_http_methods(["GET"])
def resume_detail(request: HttpRequest, slug: str) -> HttpResponse:
    """
    The main resume detail view.

    At the moment, it is used for the cover letter.
    """
    resume = get_object_or_404(Resume.objects.select_related("owner"), slug=slug)

    edit = bool(dict(request.GET).get("edit", False))
    is_editable = request.user.is_authenticated and resume.owner == request.user
    show_edit_button = True if is_editable and edit else False

    edit_url, show_url = get_edit_and_show_urls(request)
    context = {
        "resume": resume,
        # needed to include edit styles in the base template
        "show_edit_button": show_edit_button,
        "is_editable": is_editable,
        "edit_url": edit_url,
        "show_url": show_url,
    }
    plugin_names = ["about", "identity", "cover", "theme"]
    for name in plugin_names:
        plugin = plugin_registry.get_plugin(name)
        if plugin is None:
            continue
        context[plugin.name] = plugin.get_context(
            request,
            plugin.get_data(resume),
            resume.pk,
            context={},
            edit=show_edit_button,
            theme=resume.current_theme,
        )
    return render(
        request,
        f"django_resume/pages/{resume.current_theme}/resume_detail.html",
        context=context,
    )


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
def cv_403(request: HttpRequest, slug: str) -> HttpResponse:
    """
    Inline edit view for the 403 page.

    Only the owner of the resume can see this view.
    """
    resume = get_object_or_404(Resume, slug=slug)
    if resume.owner != request.user:
        return HttpResponse(status=403)

    edit = bool(dict(request.GET).get("edit", False))
    edit_url, show_url = get_edit_and_show_urls(request)
    context = {
        "resume": resume,
        "is_editable": True,
        "show_edit_button": edit,
        "edit_url": edit_url,
        "show_url": show_url,
    }
    permission_denied_plugin = plugin_registry.get_plugin("permission_denied")
    if permission_denied_plugin is None:
        return HttpResponse(status=404)
    context["permission_denied"] = permission_denied_plugin.get_context(
        request,
        permission_denied_plugin.get_data(resume),
        resume.pk,
        context={},
        edit=edit,
    )
    return render(
        request,
        f"django_resume/pages/{resume.current_theme}/cv_403.html",
        context=context,
    )


@login_required
@require_http_methods(["GET", "POST"])
def plugin_list(request: HttpRequest) -> HttpResponse:
    """
    The main db plugin list view. Only authenticated users can see it.

    You can add and delete plugins from this view.
    """
    assert request.user.is_authenticated  # type guard just to make mypy happy
    my_plugins = Plugin.objects.all()
    context: dict[str, Any] = {
        "is_editable": True,  # needed to include edit styles in the base
        "plugins": my_plugins,
    }
    if request.method == "POST":
        form = PluginForm(request.POST)
        context["form"] = form
        if form.is_valid():
            plugin = form.save()
            context["new_plugin"] = plugin
        else:
            print("form not valid: ", form.errors)
        return render(
            request, "django_resume/pages/plain/plugin_list_main.html", context=context
        )
    else:
        return render(
            request, "django_resume/pages/plain/plugin_list.html", context=context
        )


@login_required
@require_http_methods(["DELETE"])
def plugin_delete(request: HttpRequest, name: str) -> HttpResponse:
    """Delete a plugin."""
    plugin = get_object_or_404(Plugin, name=name)
    plugin.delete()
    return HttpResponse(status=200)  # 200 instead of 204 for htmx compatibility


@require_http_methods(["GET", "POST"])
def plugin_detail(request: HttpRequest, name: str) -> HttpResponse:
    """
    The main plugin detail view.

    View the details and maybe edit the plugin data / prompt.
    """
    plugin = get_object_or_404(Plugin.objects, name=name)

    def get_preview_plugin(plugin_instance: Plugin) -> SimplePlugin:
        plugin_class = plugin.to_plugin()
        my_plugin = plugin_class()

        from .urls import urlpatterns

        urlpatterns.extend(my_plugin.get_inline_urls())

        def get_resume_or_error_stub(request: HttpRequest, resume_id: int):
            return plugin

        my_plugin.inline.get_resume_or_error = get_resume_or_error_stub
        return my_plugin

    try:
        my_plugin = get_preview_plugin(plugin)
        my_plugin_context = my_plugin.get_context(
            request,
            my_plugin.get_data(plugin),  # type: ignore
            plugin.pk,
            context={},
            edit=True,
        )
    except (ValueError, NoReverseMatch, ImportError):
        my_plugin = None
        my_plugin_context = {}

    # print("my plugin: ", my_plugin.templates.string_templates.main)
    context: dict[str, Any] = {
        "plugin": plugin,
        "my_plugin": my_plugin,
        "is_editable": True,  # needed to include htmx
        "show_edit_button": True,  # to be able to edit the preview
        plugin.name: my_plugin_context,
    }

    def generate_simple_plugin_from_prompt(existing_plugin: Plugin) -> Plugin:
        generated_plugin = generate_simple_plugin(
            existing_plugin.prompt, model_name=existing_plugin.model
        )
        existing_plugin.module = generated_plugin.module
        existing_plugin.content_template = generated_plugin.content_template
        existing_plugin.form_template = generated_plugin.form_template
        return existing_plugin

    if request.method == "POST":
        form = PluginForm(request.POST, instance=plugin)
        context["form"] = form
        if form.is_valid():
            if form.cleaned_data.get("llm", False):
                # generate code, content and form templates from prompt
                plugin = generate_simple_plugin_from_prompt(plugin)
            plugin = form.save()
            # re-register the plugin (this does not really work atm, just restart the dev server)
            plugin_registry.register_db_plugin(plugin.to_plugin())
            context["new_plugin"] = plugin
        return render(
            request,
            "django_resume/pages/plain/plugin_detail_main.html",
            context=context,
        )
    else:
        return render(
            request,
            "django_resume/pages/plain/plugin_detail.html",
            context=context,
        )
