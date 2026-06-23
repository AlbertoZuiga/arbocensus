from django.contrib import admin

from .models import Route, RouteStop


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


@admin.register(RouteStop)
class RouteStopAdmin(admin.ModelAdmin):
    list_display = ["sequence", "route", "tree", "visited", "visited_at"]
    list_filter = ["route", "visited"]
    search_fields = ["tree__id", "route__route_number"]
    readonly_fields = [
        "id",
        "sequence",
        "route",
        "tree",
    ]

    def has_add_permission(self, request):
        return False
