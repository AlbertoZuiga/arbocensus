from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CustomUserViewSet, MeView, SurveyorListView

router = DefaultRouter()
router.register(r"users", CustomUserViewSet, basename="user")

urlpatterns = [
    path("me/", MeView.as_view(), name="auth_me"),
    path("surveyors/", SurveyorListView.as_view(), name="surveyor_list"),
    path("", include(router.urls)),
]
