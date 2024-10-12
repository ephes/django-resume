from typing import Any

from django.contrib.auth.decorators import login_required
from django import forms
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_http_methods

from .models import Resume
from .plugins import plugin_registry


def get_edit_and_show_urls(request: HttpRequest) -> tuple[str, str]:
    query_params = request.GET.copy()
    if "edit" in query_params:
        query_params.pop("edit")

    show_url = f"{request.path}?{query_params.urlencode()}"
    query_params["edit"] = "true"
    edit_url = f"{request.path}?{query_params.urlencode()}"
    return edit_url, show_url


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
        # needed to include edit styles in the base template
        "show_edit_button": show_edit_button,
        "is_editable": is_editable,
        "edit_url": edit_url,
        "show_url": show_url,
    }
    for plugin in plugin_registry.get_all_plugins():
        context[plugin.name] = plugin.get_context(
            request,
            plugin.get_data(resume),
            resume.pk,
            context={},
            edit=show_edit_button,
        )
    return render(request, "django_resume/plain/resume_cv.html", context=context)


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
    plugin_names = ["about", "identity", "cover"]
    for name in plugin_names:
        plugin = plugin_registry.get_plugin(name)
        context[plugin.name] = plugin.get_context(
            request,
            plugin.get_data(resume),
            resume.pk,
            context={},
            edit=show_edit_button,
        )
    return render(request, "django_resume/plain/resume_detail.html", context=context)


class ResumeForm(forms.ModelForm):
    class Meta:
        model = Resume
        fields = ["name", "slug"]


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
            request, "django_resume/plain/resume_list_main.html", context=context
        )
    else:
        # just render the complete template on GET
        return render(request, "django_resume/plain/resume_list.html", context=context)


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
