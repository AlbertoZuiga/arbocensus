from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    RouteStopSkipView,
    RouteStopVisitView,
    RouteViewSet,
    SuggestAssignmentView,
    TreeObservationListView,
    WorkloadView,
)

router = DefaultRouter()
router.include_format_suffixes = False
router.register("routes", RouteViewSet, basename="route")

urlpatterns = [
    path("routes/workload/", WorkloadView.as_view(), name="route_workload"),
    path(
        "routes/suggest-assignment/",
        SuggestAssignmentView.as_view(),
        name="route_suggest_assignment",
    ),
    path(
        "routes/stops/<uuid:stop_id>/visit/",
        RouteStopVisitView.as_view(),
        name="routestop_visit",
    ),
    path(
        "routes/stops/<uuid:stop_id>/skip/",
        RouteStopSkipView.as_view(),
        name="routestop_skip",
    ),
    path(
        "datasets/trees/<uuid:tree_id>/observations/",
        TreeObservationListView.as_view(),
        name="tree_observations",
    ),
] + router.urls
