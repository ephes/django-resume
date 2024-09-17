from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path("admin/", admin.site.urls),
    # Resume
    path("resume/", include("django_resume.urls", namespace="resume")),
]
