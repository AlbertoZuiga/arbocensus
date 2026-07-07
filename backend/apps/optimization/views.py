from typing import Any

from apps.accounts.permissions import IsAdminRole
from django.contrib.auth import get_user_model
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
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
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = OptimizationJob.objects.all()
    permission_classes = [IsAdminRole]

    def get_serializer_class(self) -> Any:
        if self.action == "create":
            return RoutingConfigSerializer
        return OptimizationJobSerializer

    def get_queryset(self) -> Any:
        queryset = OptimizationJob.objects.prefetch_related("solutions")
        dataset = self.request.query_params.get("dataset")
        if dataset:
            queryset = queryset.filter(config__dataset=dataset)
        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        job = OptimizationJob.objects.create(
            config=config, strategy=serializer.validated_data["strategy"]
        )
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

    def get_permissions(self) -> Any:
        if self.action in ("publish", "unpublish"):
            return [IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self) -> Any:
        user = self.request.user
        if user.role == CustomUser.Role.ADMIN:
            return RoutingSolution.objects.all()
        return RoutingSolution.objects.filter(routes__surveyor=user).distinct()

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        solution = self.get_object()
        solution.publish()
        return Response(RoutingSolutionSerializer(solution).data)

    @action(detail=True, methods=["post"])
    def unpublish(self, request, pk=None):
        solution = self.get_object()
        solution.unpublish()
        return Response(RoutingSolutionSerializer(solution).data)
