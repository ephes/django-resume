from django.urls import path

from . import views


app_name = "django_resume"
urlpatterns = [
    path("", views.resume_list, name="list"),
    path("<slug:slug>/delete/", views.resume_delete, name="delete"),
    path("<slug:slug>/", views.resume_detail, name="detail"),
    path("cv/<slug:slug>/", views.resume_cv, name="cv"),
]
