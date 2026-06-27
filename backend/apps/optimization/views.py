from typing import Any

from apps.accounts.permissions import IsAdminRole
from django.contrib.auth import get_user_model
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import OptimizationJob, RoutingSolution
from .serializers import (
    OptimizationJobSerializer,
    RoutingConfigSerializer,
    RoutingSolutionSerializer,
)
from .tasks import run_optimization

CustomUser = get_user_model()


class OptimizationJobViewSet(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = OptimizationJob.objects.all()
    permission_classes = [IsAdminRole]

    def get_serializer_class(self) -> Any:
        if self.action == "create":
            return RoutingConfigSerializer
        return OptimizationJobSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        job = OptimizationJob.objects.create(config=config)
        try:
            run_optimization.delay(str(job.id))
        except Exception as exc:
            job.set_error(f"Failed to enqueue optimization task: {exc}")
            raise
        return Response(
            OptimizationJobSerializer(job).data, status=status.HTTP_201_CREATED
        )


class RoutingSolutionViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = RoutingSolutionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self) -> Any:
        user = self.request.user
        if user.role == CustomUser.Role.ADMIN:
            return RoutingSolution.objects.all()
        return RoutingSolution.objects.filter(routes__surveyor=user).distinct()
