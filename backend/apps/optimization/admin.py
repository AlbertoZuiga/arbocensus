from django.contrib import admin, messages

from .models import OptimizationJob, RoutingConfig, RoutingSolution


@admin.register(RoutingConfig)
class RoutingConfigAdmin(admin.ModelAdmin):
    list_display = [
        "dataset",
        "min_route_time_sec",
        "max_route_time_sec",
        "created_at",
    ]
    list_filter = ["created_at"]
    search_fields = ["dataset__name"]
    readonly_fields = ["id", "created_at"]


@admin.register(OptimizationJob)
class OptimizationJobAdmin(admin.ModelAdmin):
    list_display = ["id", "config", "status", "created_at", "completed_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["id", "config__dataset__name"]
    readonly_fields = [
        "id",
        "status",
        "celery_task_id",
        "metrics",
        "error_message",
        "created_at",
        "started_at",
        "completed_at",
    ]
    actions = ["run_jobs"]

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return [*self.readonly_fields, "config"]
        return self.readonly_fields

    @admin.action(description="Run optimization (Celery)")
    def run_jobs(self, request, queryset):
        from config.celery import app

        for job in queryset:
            result = app.send_task(
                "apps.optimization.tasks.run_optimization", args=[str(job.id)]
            )
            job.celery_task_id = result.id
            job.set_status(OptimizationJob.Status.QUEUED)
            job.save(update_fields=["celery_task_id"])
            self.message_user(
                request,
                f"Queued optimization for job {job.id} (task {result.id}).",
                level=messages.SUCCESS,
            )


@admin.register(RoutingSolution)
class RoutingSolutionAdmin(admin.ModelAdmin):
    list_display = [
        "job",
        "strategy",
        "total_routes",
        "total_travel_time_sec",
        "generated_at",
    ]
    list_filter = ["strategy", "generated_at"]
    search_fields = ["job__id"]
    readonly_fields = [
        "id",
        "job",
        "strategy",
        "total_routes",
        "total_travel_time_sec",
        "balance_score",
        "generated_at",
    ]

    def has_add_permission(self, request):
        return False
