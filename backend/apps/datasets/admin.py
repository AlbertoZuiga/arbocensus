from django.contrib import admin, messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import path

from .importers import import_file
from .models import Dataset, DistanceMatrix, Tree


@admin.register(Dataset)
class DatasetAdmin(admin.ModelAdmin):
    list_display = ["name", "total_trees", "imported_at"]
    list_filter = ["imported_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["imported_at", "total_trees"]
    change_list_template = "admin/datasets/dataset_changelist.html"

    def get_urls(self):
        return [
            path(
                "import/",
                self.admin_site.admin_view(self.import_view),
                name="datasets_dataset_import",
            ),
        ] + super().get_urls()

    def import_view(self, request):
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "errors": [],
            "form_data": {},
        }

        if request.method == "POST":
            name = request.POST.get("name", "").strip()
            description = request.POST.get("description", "").strip()
            upload = request.FILES.get("dataset_file")

            errors = []
            if not name:
                errors.append("Name is required.")
            if not upload:
                errors.append("File is required.")

            if not errors:
                try:
                    with transaction.atomic():
                        dataset = Dataset.objects.create(
                            name=name, description=description
                        )
                        count = import_file(upload, dataset, upload.name)
                    messages.success(
                        request, f"Imported {count} trees into dataset '{name}'."
                    )
                    return redirect("..")
                except Exception as exc:
                    errors.append(str(exc))

            context["errors"] = errors
            context["form_data"] = request.POST

        return render(request, "admin/datasets/import_dataset.html", context)


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
