from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    # Resume
    path("resume/", include("django_resume.urls", namespace="resume")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
