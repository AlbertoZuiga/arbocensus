"""URL configuration for the api app."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.api, name="api"),
    path("health/", views.health, name="health"),
]
