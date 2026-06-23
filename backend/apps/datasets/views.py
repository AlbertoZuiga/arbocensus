from apps.accounts.permissions import IsAdminRole
from rest_framework import viewsets
from rest_framework.decorators import action
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

    def perform_create(self, serializer):
        upload = serializer.validated_data.pop("file")
        dataset = serializer.save()
        import_file(upload, dataset, upload.name)

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
