from django.contrib import admin

from .models import Route, RouteStop


@admin.register(Route)
class RouteAdmin(admin.ModelAdmin):
    list_display = ["route_number", "solution", "total_trees", "surveyor"]
    list_filter = ["solution", "surveyor"]
    search_fields = ["route_number", "surveyor__username"]
    readonly_fields = ["id"]


@admin.register(RouteStop)
class RouteStopAdmin(admin.ModelAdmin):
    list_display = ["sequence", "route", "tree", "visited", "visited_at"]
    list_filter = ["route", "visited"]
    search_fields = ["tree__id", "route__route_number"]
    readonly_fields = ["id"]
