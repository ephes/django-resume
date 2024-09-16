# from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


# def cv(request: HttpRequest, slug: str) -> HttpResponse:
#     form = CVTokenForm(request.GET)
#     if not form.is_valid():
#         # If the form is not valid, return the form with a 403 status code
#         return render(request, "resume/cv_token.html", {"form": form}, status=403)
#     logger.info("CV token form is valid for %s", form.cleaned_data["token"].receiver)
#     person = get_object_or_404(Person, slug=slug)
#     timelines = person.timelines.all().order_by("position")
#     projects = person.projects.all().order_by("position")
#     context = {
#         "person": person,
#         "timelines": timelines,
#         "projects": projects,
#     }
#     return render(request, "resume/cv_plain.html", context=context)


def index(request):
    return render(request, "django_resume/index.html")
