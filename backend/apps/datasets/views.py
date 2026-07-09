from apps.accounts.permissions import IsAdminRole
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import legacy
from .importers import import_file
from .legacy import LegacyDatabaseNotConfiguredError
from .models import Dataset
from .serializers import DatasetSerializer


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
            "import_legacy",
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
