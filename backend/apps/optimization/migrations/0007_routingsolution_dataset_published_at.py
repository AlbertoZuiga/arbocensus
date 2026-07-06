import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("datasets", "0001_initial"),
        ("optimization", "0006_routingsolution_interleave_per_route_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="routingsolution",
            name="dataset",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="solutions",
                to="datasets.dataset",
            ),
        ),
        migrations.AddField(
            model_name="routingsolution",
            name="published_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
