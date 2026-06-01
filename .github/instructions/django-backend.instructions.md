---
applyTo: "backend/**"
---

# Django Backend Conventions

## Models

Every model must have:
```python
import uuid
import models

class MyModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # ... fields

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.__class__.__name__} {self.id}"
```

Geographic fields always use SRID 4326:
```python
from django.contrib.gis.db import models
location = models.PointField(srid=4326)
```

`Point(lon, lat)` — longitude first. `tree.location.x` = lon, `tree.location.y` = lat.

No business logic in model methods except for simple computed properties and status transitions (`set_status`, `set_completed`, `set_error`).

## Serializers

Never use `fields = "__all__"`. Always explicit:
```python
class DatasetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dataset
        fields = ["id", "name", "description", "imported_at", "total_trees"]
        read_only_fields = ["id", "imported_at", "total_trees"]
```

Write-only fields (passwords, file uploads) use `write_only=True`. Never expose them in read responses.

## Views

Views orchestrate; they do not contain logic:
```python
class DatasetViewSet(viewsets.ModelViewSet):
    queryset = Dataset.objects.all()
    serializer_class = DatasetSerializer
    permission_classes = [IsAdminRole]

    def perform_create(self, serializer):
        dataset = serializer.save()
        importer = DatasetImporter()
        tree_count = importer.import_from_file(self.request.FILES["file"], dataset)
        dataset.total_trees = tree_count
        dataset.save(update_fields=["total_trees"])
```

Complex operations belong in `pipeline.py`, `importers.py`, or model methods — not in views.

## Permissions

Never use DRF's `IsAdminUser` (checks `is_staff`, not our `role` field). Use project-specific:
```python
# apps/accounts/permissions.py
class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "admin"
```

## Celery tasks

```python
# optimization/tasks.py
from celery import shared_task

@shared_task(bind=True, max_retries=1)
def run_optimization(self, job_id: str):
    from apps.optimization.models import OptimizationJob  # import INSIDE task
    from apps.optimization.pipeline import OptimizationPipeline

    job = OptimizationJob.objects.get(id=job_id)
    try:
        job.set_status("running")
        pipeline = OptimizationPipeline(job)
        result = pipeline.run()
        job.set_completed(result)
    except Exception as exc:
        job.set_error(str(exc))
        raise self.retry(exc=exc, countdown=5)
```

Models imported at module top-level in tasks cause `AppRegistryNotReady` on worker startup.

## Tests

Use `pytest-django` with factories, not fixtures:
```python
# tests/factories.py
import factory
from apps.datasets.models import Dataset, Tree
from django.contrib.gis.geos import Point

class DatasetFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Dataset
    name = factory.Sequence(lambda n: f"Dataset {n}")

class TreeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tree
    dataset = factory.SubFactory(DatasetFactory)
    location = factory.LazyFunction(lambda: Point(-70.65, -33.45))  # lon, lat
```

API tests use `force_authenticate`, never real credentials:
```python
def test_create_dataset(self, api_client, admin_user):
    api_client.force_authenticate(user=admin_user)
    response = api_client.post("/api/datasets/", {...})
    assert response.status_code == 201
```

## GeoJSON responses

Return FeatureCollection format for geographic endpoints:
```python
{
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},  # lon first
            "properties": {"id": str(tree.id), "sequence": stop.sequence}
        }
    ]
}
```
