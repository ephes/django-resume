from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404

from .models import Person
from .plugins import plugin_registry


def cv(request: HttpRequest, slug: str) -> HttpResponse:
    person = get_object_or_404(Person, slug=slug)
    edit = bool(request.GET.get("edit", False))
    context = {
        "show_edit_button": True if request.user.is_authenticated and edit else False,
        "person": person,
        "timelines": [],
        "projects": [],
    }
    for plugin in plugin_registry.get_all_plugins():
        context[plugin.name] = plugin.get_context(
            plugin.get_data(person), person.pk, context=context
        )
    is_authenticated = request.user.is_authenticated
    print("is_authenticated: ", is_authenticated)
    return render(request, "django_resume/plain/cv.html", context=context)


def index(request):
    return render(request, "django_resume/index.html")
