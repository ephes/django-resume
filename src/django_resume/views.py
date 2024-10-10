from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404

from .models import Person
from .plugins import plugin_registry


def cv(request: HttpRequest, slug: str) -> HttpResponse:
    person = get_object_or_404(Person, slug=slug)
    edit = bool(request.GET.get("edit", False))
    show_edit_button = True if request.user.is_authenticated and edit else False
    context = {
        "person": person,
        "timelines": [],
        "projects": [],
        # needed to include edit styles in the base template
        "show_edit_button": show_edit_button,
    }
    for plugin in plugin_registry.get_all_plugins():
        context[plugin.name] = plugin.get_context(
            request,
            plugin.get_data(person),
            person.pk,
            context={},
            edit=show_edit_button,
        )
    is_authenticated = request.user.is_authenticated
    print("is_authenticated: ", is_authenticated)
    return render(request, "django_resume/plain/cv.html", context=context)


def index(request):
    return render(request, "django_resume/index.html")
