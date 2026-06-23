from rest_framework import serializers

from .models import Dataset


class DatasetSerializer(serializers.ModelSerializer):
    file = serializers.FileField(write_only=True)

    class Meta:
        model = Dataset
        fields = ["id", "name", "description", "imported_at", "total_trees", "file"]
        read_only_fields = ["id", "imported_at", "total_trees"]
