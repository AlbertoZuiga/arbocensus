from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("api", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="PipelineRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("bbox_north", models.FloatField()),
                ("bbox_south", models.FloatField()),
                ("bbox_east", models.FloatField()),
                ("bbox_west", models.FloatField()),
                ("expected_duration_min", models.FloatField(default=150.0)),
                ("time_per_tree_min", models.FloatField(default=2.0)),
                ("tree_count", models.IntegerField(blank=True, null=True)),
                ("route_count", models.IntegerField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("routes_geojson", models.JSONField(blank=True, null=True)),
                ("clusters_geojson", models.JSONField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
