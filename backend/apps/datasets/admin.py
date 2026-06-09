from django.contrib import admin

from .models import Dataset, DistanceMatrix, Tree


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ["name", "total_trees", "imported_at"]
    list_filter = ["imported_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["imported_at", "total_trees"]


@admin.register(Tree)
class TreeAdmin(admin.ModelAdmin):
    list_display = ["id", "dataset", "is_active", "location"]
    list_filter = ["dataset", "is_active"]
    search_fields = ["id", "dataset__name"]
    readonly_fields = ["id"]


@admin.register(DistanceMatrix)
class DistanceMatrixAdmin(admin.ModelAdmin):
    list_display = ["dataset", "dimension", "computed_at"]
    list_filter = ["computed_at"]
    search_fields = ["dataset__name"]
    readonly_fields = ["id", "computed_at"]
