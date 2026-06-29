import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("optimization", "0002_alter_routingconfig_max_route_time_sec_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="routingsolution",
            name="job",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="solutions",
                to="optimization.optimizationjob",
            ),
        ),
        migrations.AddField(
            model_name="routingsolution",
            name="strategy",
            field=models.CharField(
                choices=[
                    ("global", "Global"),
                    ("spatial_term", "Spatial Term"),
                    ("cluster_first", "Cluster First"),
                ],
                max_length=20,
                default="global",
            ),
            preserve_default=False,
        ),
    ]
