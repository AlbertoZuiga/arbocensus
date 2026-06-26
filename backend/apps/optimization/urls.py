from rest_framework.routers import DefaultRouter

from .views import OptimizationJobViewSet, RoutingSolutionViewSet

router = DefaultRouter()
router.register(
    "optimization/jobs", OptimizationJobViewSet, basename="optimization-job"
)
router.register(
    "optimization/solutions",
    RoutingSolutionViewSet,
    basename="optimization-solution",
)

urlpatterns = router.urls
