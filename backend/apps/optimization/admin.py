from django.contrib import admin

from .models import OptimizationJob, RoutingConfig, RoutingSolution


@admin.register(RoutingConfig)
class RoutingConfigAdmin(admin.ModelAdmin):
    list_display = ["dataset", "min_route_time_sec", "max_route_time_sec", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["dataset__name"]
    readonly_fields = ["id", "created_at"]


@admin.register(OptimizationJob)
class OptimizationJobAdmin(admin.ModelAdmin):
    list_display = ["id", "config", "status", "created_at", "completed_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["id", "config__dataset__name"]
    readonly_fields = ["id", "created_at", "started_at", "completed_at"]


@admin.register(RoutingSolution)
class RoutingSolutionAdmin(admin.ModelAdmin):
    list_display = ["job", "total_routes", "total_travel_time_sec", "generated_at"]
    list_filter = ["generated_at"]
    search_fields = ["job__id"]
    readonly_fields = ["id", "generated_at"]
