from django.conf import settings
from django.contrib import admin
from django.contrib.auth.views import redirect_to_login
from django.http import HttpRequest, HttpResponse
from django.urls import path, include, reverse
from django.conf.urls.static import static
from django.shortcuts import redirect


def root_redirect(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("resume:list")
    return redirect_to_login(reverse("resume:list"), settings.LOGIN_URL)


urlpatterns = [
    path("", root_redirect),
    path("admin/", admin.site.urls),
    # Resume
    path("resume/", include("django_resume.urls", namespace="resume")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
