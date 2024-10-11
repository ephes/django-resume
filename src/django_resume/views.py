from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404

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


def cv(request: HttpRequest, slug: str) -> HttpResponse:
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
    return render(request, "django_resume/plain/cv.html", context=context)


def index(request):
    return render(request, "django_resume/index.html")
