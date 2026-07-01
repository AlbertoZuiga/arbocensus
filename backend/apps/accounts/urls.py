from django.urls import path

from .views import MeView, SurveyorListView

urlpatterns = [
    path("me/", MeView.as_view(), name="auth_me"),
    path("surveyors/", SurveyorListView.as_view(), name="surveyor_list"),
]
