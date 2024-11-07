from django.urls import path, reverse
from django.views.generic import RedirectView

from . import views


class CvRedirectView(RedirectView):
    permanent = True

    def get_redirect_url(self, *args, **kwargs) -> str:
        slug = kwargs["slug"]
        return reverse("django_resume:cv", kwargs={"slug": slug})


app_name = "django_resume"
urlpatterns = [
    path("", views.resume_list, name="list"),
    path("<slug:slug>/delete/", views.resume_delete, name="delete"),
    path("<slug:slug>/", views.resume_detail, name="detail"),
    path("<slug:slug>/cv/", views.resume_cv, name="cv"),
    path("cv/<slug:slug>/", CvRedirectView.as_view(), name="cv-redirect"),
    path("<slug:slug>/403/", views.cv_403, name="403"),
]
