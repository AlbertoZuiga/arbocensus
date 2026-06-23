from typing import Any

from rest_framework.generics import RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from .serializers import CustomUserSerializer


class MeView(RetrieveAPIView):
    serializer_class = CustomUserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self) -> Any:
        return self.request.user
