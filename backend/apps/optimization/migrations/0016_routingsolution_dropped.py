from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("datasets", "0003_tree_source_and_source_scoped_external_id"),
        ("optimization", "0015_optimizationjob_config_preset_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="routingsolution",
            name="dropped",
            field=models.ManyToManyField(
                blank=True,
                related_name="dropped_in",
                to="datasets.tree",
            ),
        ),
    ]
