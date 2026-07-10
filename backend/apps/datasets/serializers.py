from rest_framework import serializers

from .legacy import SOURCES
from .models import Dataset


class LegacyTreeRefSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=list(SOURCES))
    external_id = serializers.IntegerField()


class LegacySelectionSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    trees = LegacyTreeRefSerializer(many=True, allow_empty=False)


class DatasetSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Dataset
        fields = ["id", "name", "description", "imported_at", "total_trees", "file"]
        read_only_fields = ["id", "imported_at", "total_trees"]
