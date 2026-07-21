from django.contrib import admin

from .models import Route, RouteStop, TreeObservation


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["route_number", "solution", "total_trees", "surveyor"]
    list_filter = ["solution", "surveyor"]
    search_fields = ["route_number", "surveyor__username"]
    readonly_fields = [
        "id",
        "solution",
        "route_number",
        "total_trees",
        "travel_time_sec",
        "total_estimated_time_sec",
    ]

    def has_add_permission(self, request):
        return False


@admin.register(TreeObservation)
class TreeObservationAdmin(admin.ModelAdmin):
    list_display = ["tree", "status", "created_by", "observed_at"]
    list_filter = ["status", "created_by"]
    search_fields = ["tree__id"]
    readonly_fields = ["id", "tree", "route_stop", "created_by"]


@admin.register(RouteStop)
class RouteStopAdmin(admin.ModelAdmin):
    list_display = ["sequence", "route", "tree", "status", "visited_at"]
    list_filter = ["route", "status"]
    search_fields = ["tree__id", "route__route_number"]
    readonly_fields = [
        "id",
        "sequence",
        "route",
        "tree",
    ]

    def has_add_permission(self, request):
        return False
