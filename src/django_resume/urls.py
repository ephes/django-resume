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
    path("<slug:slug>/json-resume/", views.export_json_resume, name="json-resume"),
    path(
        "<slug:slug>/json-resume/themes/",
        views.json_resume_theme_selector,
        name="json-resume-themes",
    ),
    path(
        "<slug:slug>/json-resume/themes/install/",
        views.install_json_resume_theme,
        name="json-resume-theme-install",
    ),
    path(
        "<slug:slug>/json-resume/themes/<slug:key>/preview/",
        views.preview_json_resume_catalog_theme,
        name="json-resume-theme-preview",
    ),
    path(
        "<slug:slug>/json-resume/themes/<slug:key>/use/",
        views.use_json_resume_catalog_theme,
        name="json-resume-theme-use",
    ),
    path(
        "<slug:slug>/json-resume/rendered/",
        views.render_json_resume_theme,
        name="json-resume-rendered",
    ),
    path("cv/<slug:slug>/", CvRedirectView.as_view(), name="cv-redirect"),
    # cover, cv and 403 pages (generated; bare "<slug:slug>/" catch-all is last)
    *page_registry.get_urls(),
]
