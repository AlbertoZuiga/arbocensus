from typing import Any

from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.viewsets import ModelViewSet

from .models import CustomUser
from .permissions import IsAdminRole
from .serializers import (
    CustomUserSerializer,
    SurveyorSerializer,
    UserAdminSerializer,
)


class MeView(RetrieveAPIView):
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> Any:
        return self.request.user


class SurveyorListView(ListAPIView):
    serializer_class = SurveyorSerializer
    permission_classes = [IsAdminRole]
    queryset = CustomUser.objects.filter(role=CustomUser.Role.SURVEYOR).order_by(
        "-date_joined"
    )


class CustomUserViewSet(ModelViewSet):
    permission_classes = [IsAdminRole]
    serializer_class = UserAdminSerializer
    queryset = CustomUser.objects.all().order_by("-date_joined")

    def perform_update(self, serializer):
        serializer.instance.assert_can_change(
            self.request.user,
            role=serializer.validated_data.get("role"),
            is_active=serializer.validated_data.get("is_active"),
        )
        serializer.save()

    def perform_destroy(self, instance):
        instance.assert_can_change(self.request.user, is_active=False)
        instance.is_active = False
        instance.save(update_fields=["is_active"])
