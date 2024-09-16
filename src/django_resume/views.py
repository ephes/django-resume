from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404

from .models import Person
from .plugins import plugin_registry


def cv(request: HttpRequest, slug: str) -> HttpResponse:
    person = get_object_or_404(Person, slug=slug)
    context = {
        "person": person,
        "timelines": [],
        "projects": [],
    }
    for plugin in plugin_registry.get_all_plugins():
        context[plugin.name] = plugin.get_data_for_context(person)
    return render(request, "django_resume/plain/cv.html", context=context)


def index(request):
    return render(request, "django_resume/index.html")
