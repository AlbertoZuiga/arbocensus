import django.contrib.gis.db.models.fields
from django.db import migrations, models


def set_status_from_visited(apps, schema_editor):
    RouteStop = apps.get_model("routes", "RouteStop")
    RouteStop.objects.filter(visited=True).update(status="visited")


class Migration(migrations.Migration):
    dependencies = [
        ("routes", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="routestop",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("visited", "Visited"),
                    ("skipped", "Skipped"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="routestop",
            name="visit_location",
            field=django.contrib.gis.db.models.fields.PointField(
                blank=True, null=True, srid=4326
            ),
        ),
        migrations.AddField(
            model_name="routestop",
            name="skip_reason",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.RunPython(set_status_from_visited, migrations.RunPython.noop),
    ]
