from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import RouteStopVisitView, RouteViewSet

router = DefaultRouter()
router.register("routes", RouteViewSet, basename="route")

urlpatterns = router.urls + [
    path(
        "routes/stops/<uuid:stop_id>/visit/",
        RouteStopVisitView.as_view(),
        name="routestop_visit",
    ),
]
