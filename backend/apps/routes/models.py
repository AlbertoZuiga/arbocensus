import uuid

from apps.datasets.models import Tree
from apps.optimization.models import RoutingSolution
from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.db import models
from django.utils import timezone


class Route(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    solution = models.ForeignKey(
        RoutingSolution, on_delete=models.CASCADE, related_name="routes"
    )
    route_number = models.IntegerField()
    total_trees = models.IntegerField()
    travel_time_sec = models.IntegerField(default=0)
    total_estimated_time_sec = models.IntegerField(default=0)
    surveyor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="routes",
    )

    class Meta:
        ordering = ["route_number"]
        unique_together = ("solution", "route_number")

    def __str__(self):
        return f"Route {self.route_number} ({self.total_trees} trees)"


class RouteStop(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        VISITED = "visited", "Visited"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    tree = models.ForeignKey(Tree, on_delete=models.CASCADE)
    sequence = models.IntegerField()
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )
    visited = models.BooleanField(default=False)
    visited_at = models.DateTimeField(null=True, blank=True)
    visit_location = gis_models.PointField(srid=4326, null=True, blank=True)
    skip_reason = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence"]
        unique_together = ("route", "tree")

    def __str__(self):
        return f"Stop {self.sequence} - Tree {str(self.tree.id)[:8]}"

    def has_pending_predecessor(self):
        return RouteStop.objects.filter(
            route=self.route, sequence__lt=self.sequence, status=self.Status.PENDING
        ).exists()

    def mark_visited(self, location=None, notes=None):
        self.status = self.Status.VISITED
        self.visited = True
        self.visited_at = timezone.now()
        if location is not None:
            self.visit_location = location
        if notes is not None:
            self.notes = notes
        self.save(
            update_fields=[
                "status",
                "visited",
                "visited_at",
                "visit_location",
                "notes",
            ]
        )

    def mark_skipped(self, reason):
        self.status = self.Status.SKIPPED
        self.skip_reason = reason
        self.save(update_fields=["status", "skip_reason"])


class TreeObservation(models.Model):
    class Status(models.TextChoices):
        ALIVE = "alive", "Alive"
        REMOVED = "removed", "Removed"
        NOT_FOUND = "not_found", "Not found"
        OTHER = "other", "Other"
        UNKNOWN = "unknown", "Unknown"

    NOT_FOUND_SKIP_REASON = "Árbol inexistente"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tree = models.ForeignKey(
        Tree, on_delete=models.CASCADE, related_name="observations"
    )
    route_stop = models.ForeignKey(
        RouteStop,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="observations",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.UNKNOWN
    )
    photo = models.ImageField(upload_to="observations/", null=True, blank=True)
    photo_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tree_observations",
    )
    observed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-observed_at"]

    def __str__(self):
        return f"Observation {self.status} - Tree {str(self.tree_id)[:8]}"

    @classmethod
    def status_for_skip(cls, reason):
        if reason == cls.NOT_FOUND_SKIP_REASON:
            return cls.Status.NOT_FOUND
        return cls.Status.UNKNOWN
