import uuid
from typing import Any

from apps.accounts.permissions import IsAdminRole
from apps.datasets.models import Dataset
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .config_presets import CONFIG_PRESETS
from .models import OptimizationJob, RoutingConfig, RoutingSolution
from .pipeline import estimate_fleet_from_cache
from .recommendation import (
    order_by_criterion,
    pick_recommended,
    pick_recommended_bulk,
)
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
        queryset = OptimizationJob.objects.prefetch_related(
            "solutions", "solutions__dropped"
        )
        dataset = self.request.query_params.get("dataset")
        if dataset:
            queryset = queryset.filter(config__dataset=dataset)
        return queryset

    def create(self, request, *args, **kwargs):
        # One submit fans out into one job per preset (all running the full
        # strategy comparison) so the admin gets a ranked sweep instead of
        # having to relaunch by hand for each preset.
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        config = serializer.save()
        jobs = [
            OptimizationJob.objects.create(
                config=config,
                strategy=OptimizationJob.Strategy.COMPARE,
                config_preset=preset,
            )
            for preset in CONFIG_PRESETS
        ]
        for job in jobs:
            try:
                run_optimization.delay(str(job.id))
            except Exception as exc:
                job.set_error(f"Failed to enqueue optimization task: {exc}")
                raise
        return Response(
            OptimizationJobSerializer(jobs, many=True).data,
            status=status.HTTP_201_CREATED,
        )


class SolutionPagination(PageNumberPagination):
    # Each submit produces one solution per preset x strategy, and the panel lists
    # every past sweep of a dataset in one response. The global PAGE_SIZE of 20
    # would drop whole sweeps off the first page after the second run.
    page_size = 200


class RoutingSolutionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    serializer_class = RoutingSolutionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = SolutionPagination

    def get_permissions(self) -> Any:
        if self.action in ("publish", "unpublish"):
            return [IsAdminRole()]
        return [IsAuthenticated()]

    def get_queryset(self) -> Any:
        user = self.request.user
        base = RoutingSolution.objects.select_related("job__config").prefetch_related(
            "routes", "dropped"
        )
        if user.role == CustomUser.Role.ADMIN:
            queryset = base
        else:
            queryset = base.filter(routes__surveyor=user).distinct()
        dataset = self.request.query_params.get("dataset")
        if dataset:
            queryset = queryset.filter(dataset=dataset)
        return order_by_criterion(queryset)

    def get_serializer_context(self) -> Any:
        context = super().get_serializer_context()
        dataset = self.request.query_params.get("dataset")
        if dataset:
            context["recommended_solution_id"] = pick_recommended(dataset)
        elif self.action == "list":
            # order_by() strips the criterion ordering: with values_list Django
            # would carry those columns into the SELECT and defeat the distinct.
            context["recommended_by_dataset"] = pick_recommended_bulk(
                self.get_queryset()
                .order_by()
                .values_list("dataset_id", flat=True)
                .distinct()
            )
        return context

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


@api_view(["GET"])
@permission_classes([IsAdminRole])
def fleet_estimate(request):
    dataset_id = request.query_params.get("dataset")
    if not dataset_id:
        return Response(
            {"detail": "dataset query param is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        uuid.UUID(dataset_id)
    except ValueError:
        return Response(
            {"detail": "dataset must be a valid UUID"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        min_route_time_sec = int(
            request.query_params.get(
                "min_route_time_sec", RoutingConfig.DEFAULT_MIN_ROUTE_TIME_SEC
            )
        )
        service_time_sec = int(
            request.query_params.get(
                "service_time_sec", RoutingConfig.DEFAULT_SERVICE_TIME_SEC
            )
        )
    except ValueError:
        return Response(
            {"detail": "min_route_time_sec and service_time_sec must be integers"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if min_route_time_sec < 1 or service_time_sec < 1:
        return Response(
            {"detail": "min_route_time_sec and service_time_sec must be positive"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    dataset = get_object_or_404(Dataset, pk=dataset_id)
    return Response(
        {
            "n_estimated": estimate_fleet_from_cache(
                dataset, min_route_time_sec, service_time_sec
            )
        }
    )
