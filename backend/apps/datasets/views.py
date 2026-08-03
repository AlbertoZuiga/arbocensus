from apps.accounts.permissions import IsAdminRole
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import legacy, partition
from .importers import import_file
from .legacy import LegacyDatabaseNotConfiguredError
from .models import Dataset
from .serializers import (
    DatasetSerializer,
    DeactivateTreesSerializer,
    LegacyPartitionSerializer,
)


class DatasetViewSet(viewsets.ModelViewSet):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_permissions(self):
        if self.action in (
            "create",
            "update",
            "partial_update",
            "destroy",
            "legacy_areas",
            "legacy_trees",
            "legacy_tree_observations",
            "import_legacy",
            "partition_legacy_selection",
            "deactivate_trees",
        ):
            return [IsAdminRole()]
        return [IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data.pop("file")
        try:
            with transaction.atomic():
                dataset = serializer.save()
                _, skipped_rows = import_file(upload, dataset, upload.name)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        headers = self.get_success_headers(serializer.data)
        data = {**serializer.data, "skipped_rows": skipped_rows}
        return Response(data, status=status.HTTP_201_CREATED, headers=headers)

    @action(detail=False, methods=["get"], url_path="legacy/areas")
    def legacy_areas(self, request):
        try:
            return Response(legacy.list_areas())
        except LegacyDatabaseNotConfiguredError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

    @action(detail=False, methods=["get"], url_path="legacy/trees")
    def legacy_trees(self, request):
        try:
            return Response(legacy.list_trees())
        except LegacyDatabaseNotConfiguredError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

    @action(
        detail=False,
        methods=["get"],
        url_path=r"legacy/trees/(?P<source>[^/]+)/(?P<external_id>\d+)/observations",
    )
    def legacy_tree_observations(self, request, source=None, external_id=None):
        try:
            return Response(legacy.tree_observations(source, int(external_id)))
        except LegacyDatabaseNotConfiguredError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

    @action(detail=False, methods=["post"], url_path="partition-legacy-selection")
    def partition_legacy_selection(self, request):
        serializer = LegacyPartitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        selection = list(
            dict.fromkeys(
                (tree["source"], tree["external_id"]) for tree in data["trees"]
            )
        )
        try:
            rows = legacy.load_selection(selection)
        except LegacyDatabaseNotConfiguredError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except ValueError as exc:
            raise ValidationError({"trees": str(exc)}) from exc
        try:
            partitions = partition.by_kmeans(data["name"], rows, data["k"])
        except ValueError as exc:
            raise ValidationError({"k": str(exc)}) from exc
        datasets = legacy.create_datasets(partitions)
        return Response(
            self.get_serializer(datasets, many=True).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="import-legacy")
    def import_legacy(self, request):
        area_id = request.data.get("area_id")
        if area_id is None:
            raise ValidationError({"area_id": "This field is required."})
        try:
            if area_id == "all":
                imports = legacy.import_all()
            else:
                imports = [legacy.import_area(int(area_id))]
        except LegacyDatabaseNotConfiguredError as exc:
            return Response(
                {"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        except (ValueError, TypeError) as exc:
            raise ValidationError({"area_id": str(exc)}) from exc
        datasets = legacy.create_datasets(imports)
        serializer = self.get_serializer(datasets, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="trees/deactivate")
    def deactivate_trees(self, request, pk=None):
        dataset = self.get_object()
        serializer = DeactivateTreesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tree_ids = serializer.validated_data["tree_ids"]
        with transaction.atomic():
            dataset.tree_set.filter(id__in=tree_ids).update(is_active=False)
            dataset.total_trees = dataset.tree_set.filter(is_active=True).count()
            dataset.save(update_fields=["total_trees"])
        return Response({"total_trees": dataset.total_trees})

    @action(detail=True, methods=["get"])
    def trees(self, request, pk=None):
        dataset = self.get_object()
        features = [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [tree.location.x, tree.location.y],
                },
                "properties": {"id": str(tree.id), "is_active": tree.is_active},
            }
            for tree in dataset.tree_set.filter(is_active=True)
        ]
        return Response({"type": "FeatureCollection", "features": features})
