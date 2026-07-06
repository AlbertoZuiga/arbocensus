from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("optimization", "0009_routingsolution_dataset_not_null_and_constraint"),
    ]

    operations = [
        migrations.AddField(
            model_name="optimizationjob",
            name="strategy",
            field=models.CharField(
                choices=[
                    ("global", "Global"),
                    ("spatial_term", "Spatial Term"),
                    ("cluster_first", "Cluster First"),
                    ("compare", "Compare"),
                ],
                default="global",
                max_length=20,
            ),
        ),
    ]
