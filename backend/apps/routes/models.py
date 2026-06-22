import uuid

from apps.datasets.models import Tree
from apps.optimization.models import RoutingSolution
from django.conf import settings
from django.db import models


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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="stops")
    tree = models.ForeignKey(Tree, on_delete=models.CASCADE)
    sequence = models.IntegerField()
    visited = models.BooleanField(default=False)
    visited_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["sequence"]
        unique_together = ("route", "tree")

    def __str__(self):
        return f"Stop {self.sequence} - Tree {str(self.tree.id)[:8]}"
