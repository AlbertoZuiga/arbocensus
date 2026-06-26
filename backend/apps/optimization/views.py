from apps.accounts.permissions import IsAdminRole
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


class OptimizationJobViewSet(
    mixins.CreateModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    queryset = OptimizationJob.objects.all()
    permission_classes = [IsAdminRole]

    def get_serializer_class(self):
        if self.action == "create":
            return RoutingConfigSerializer
        return OptimizationJobSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        job = OptimizationJob.objects.create(config=config)
        run_optimization.delay(str(job.id))
        return Response(
            OptimizationJobSerializer(job).data, status=status.HTTP_201_CREATED
        )


class RoutingSolutionViewSet(mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = RoutingSolution.objects.all()
    serializer_class = RoutingSolutionSerializer
    permission_classes = [IsAuthenticated]
