from apps.accounts.permissions import IsAdminRole
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .importers import import_file
from .models import Dataset
from .serializers import DatasetSerializer


class DatasetViewSet(viewsets.ModelViewSet):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    parser_classes = [MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
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
