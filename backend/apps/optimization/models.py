import uuid

from apps.datasets.models import Dataset
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class RoutingConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    dataset = models.ForeignKey(Dataset, on_delete=models.CASCADE)
    min_route_time_sec = models.IntegerField(
        default=7200, validators=[MinValueValidator(1)]
    )
    max_route_time_sec = models.IntegerField(
        default=10800, validators=[MinValueValidator(1)]
    )
    service_time_sec = models.IntegerField(
        default=300, validators=[MinValueValidator(1)]
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=Q(min_route_time_sec__gte=1),
                name="routingconfig_min_route_time_positive",
            ),
            models.CheckConstraint(
                condition=Q(max_route_time_sec__gte=1),
                name="routingconfig_max_route_time_positive",
            ),
            models.CheckConstraint(
                condition=Q(service_time_sec__gte=1),
                name="routingconfig_service_time_positive",
            ),
            models.CheckConstraint(
                condition=Q(max_route_time_sec__gte=F("min_route_time_sec")),
                name="routingconfig_max_route_time_gte_min",
            ),
        ]

    def __str__(self):
        return f"RoutingConfig {self.dataset.name}"


class OptimizationJob(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued"
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    config = models.ForeignKey(RoutingConfig, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED
    )
    celery_task_id = models.CharField(max_length=255, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metrics = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"OptimizationJob {self.id} ({self.status})"

    def set_status(self, status):
        self.status = status
        if status == "running":
            self.started_at = timezone.now()
        self.save(update_fields=["status", "started_at"])

    def set_completed(self, metrics=None):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.metrics = metrics or {}
        self.save(update_fields=["status", "completed_at", "metrics"])

    def set_error(self, error_message):
        self.status = self.Status.FAILED
        self.error_message = error_message
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "error_message", "completed_at"])


class RoutingSolution(models.Model):
    class Strategy(models.TextChoices):
        GLOBAL = "global"
        SPATIAL_TERM = "spatial_term"
        CLUSTER_FIRST = "cluster_first"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey(
        OptimizationJob, on_delete=models.CASCADE, related_name="solutions"
    )
    strategy = models.CharField(max_length=20, choices=Strategy.choices)
    total_routes = models.IntegerField()
    total_travel_time_sec = models.FloatField(default=0)
    balance_score = models.FloatField(default=0)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]
        unique_together = (("job", "strategy"),)

    def __str__(self):
        return f"RoutingSolution {self.id} ({self.total_routes} routes)"
