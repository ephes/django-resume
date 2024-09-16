from django.http import HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404

from .models import Person


def cv(request: HttpRequest, slug: str) -> HttpResponse:
    person = get_object_or_404(Person, slug=slug)
    timelines = []
    projects = []
    # timelines = person.timelines.all().order_by("position")
    # projects = person.projects.all().order_by("position")
    context = {
        "person": person,
        "timelines": timelines,
        "projects": projects,
    }
    return render(request, "django_resume/plain/cv.html", context=context)


def index(request):
    return render(request, "django_resume/index.html")
