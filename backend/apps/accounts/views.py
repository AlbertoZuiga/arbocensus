from typing import Any

from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from .models import CustomUser
from .permissions import IsAdminRole
from .serializers import CustomUserSerializer, SurveyorSerializer


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
