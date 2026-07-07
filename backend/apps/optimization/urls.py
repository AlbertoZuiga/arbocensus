from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import OptimizationJobViewSet, RoutingSolutionViewSet, fleet_estimate

router = DefaultRouter()
router.include_format_suffixes = False
router.register(
    "optimization/jobs", OptimizationJobViewSet, basename="optimization-job"
)
router.register(
    "optimization/solutions",
    RoutingSolutionViewSet,
    basename="optimization-solution",
)

urlpatterns = [
    path("optimization/estimate/", fleet_estimate, name="optimization-estimate"),
] + router.urls
