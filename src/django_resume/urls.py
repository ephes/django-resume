from django.urls import path

from . import views


app_name = "django_resume"
urlpatterns = [
    path("", views.index, name="index"),
    path("cv/<slug:slug>/", views.cv, name="cv"),
]
