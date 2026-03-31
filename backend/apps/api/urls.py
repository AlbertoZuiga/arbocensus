"""URL configuration for the api app."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.api_root, name="api-root"),
    path("health/", views.health, name="health"),
    path("runs/", views.runs_list_create, name="runs-list-create"),
    path("runs/<int:run_id>/", views.run_detail, name="run-detail"),
    path(
        "runs/<int:run_id>/routes.geojson",
        views.run_routes_geojson,
        name="run-routes-geojson",
    ),
    path(
        "runs/<int:run_id>/clusters.geojson",
        views.run_clusters_geojson,
        name="run-clusters-geojson",
    ),
]
