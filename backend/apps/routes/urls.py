from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    RouteStopSkipView,
    RouteStopVisitView,
    RouteViewSet,
    TreeObservationListView,
)

router = DefaultRouter()
router.include_format_suffixes = False
router.register("routes", RouteViewSet, basename="route")

urlpatterns = router.urls + [
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
]
