from django.db import migrations


def populate_dataset(apps, schema_editor):
    RoutingSolution = apps.get_model("optimization", "RoutingSolution")
    for solution in RoutingSolution.objects.filter(dataset__isnull=True).select_related(
        "job__config"
    ):
        solution.dataset_id = solution.job.config.dataset_id
        solution.save(update_fields=["dataset"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("optimization", "0007_routingsolution_dataset_published_at"),
    ]

    operations = [
        migrations.RunPython(populate_dataset, noop),
    ]
