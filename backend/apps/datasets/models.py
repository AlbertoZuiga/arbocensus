import uuid

from django.contrib.gis.db import models as gis_models
from django.db import models


class Dataset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    imported_at = models.DateTimeField(auto_now_add=True)
    total_trees = models.IntegerField(default=0)

    class Meta:
        ordering = ["-imported_at"]

    def __str__(self):
        return f"Dataset {self.name} ({self.total_trees} trees)"


class Tree(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    location = gis_models.PointField(srid=4326)
    is_active = models.BooleanField(default=True)
    species = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=20, blank=True)
    external_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["dataset"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["dataset", "source", "external_id"],
                condition=models.Q(external_id__isnull=False),
                name="unique_source_external_id_per_dataset",
            ),
        ]

    def __str__(self):
        return f"Tree {str(self.id)[:8]} in {self.dataset.name}"


class DistanceMatrix(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.OneToOneField(Dataset, on_delete=models.CASCADE)
    source_hash = models.CharField(max_length=64)
    matrix_data = models.JSONField()
    dimension = models.IntegerField()
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-computed_at"]

    def __str__(self):
        return f"DistanceMatrix {self.dataset.name} ({self.dimension}x{self.dimension})"
