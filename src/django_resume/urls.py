from django.urls import path, reverse
from django.views.generic import RedirectView

from . import views
from .pages import page_registry


class CvRedirectView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs) -> str:
        slug = kwargs["slug"]
        return reverse("django_resume:cv", kwargs={"slug": slug})


app_name = "django_resume"
urlpatterns = [
    # resumes (non-page routes)
    path("", views.resume_list, name="list"),
    path("<slug:slug>/delete/", views.resume_delete, name="delete"),
    path("cv/<slug:slug>/", CvRedirectView.as_view(), name="cv-redirect"),
    # cover, cv and 403 pages (generated; bare "<slug:slug>/" catch-all is last)
    *page_registry.get_urls(),
]
