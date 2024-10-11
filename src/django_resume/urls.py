from django.urls import path

from . import views


app_name = "django_resume"
urlpatterns = [
    path("", views.index, name="index"),
    path("<slug:slug>/", views.detail, name="detail"),
    path("cv/<slug:slug>/", views.cv, name="cv"),
]
