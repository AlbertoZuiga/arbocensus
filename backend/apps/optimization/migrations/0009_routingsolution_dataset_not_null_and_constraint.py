import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("optimization", "0008_populate_routingsolution_dataset"),
    ]

    operations = [
        migrations.AlterField(
            model_name="routingsolution",
            name="dataset",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="solutions",
                to="datasets.dataset",
            ),
        ),
        migrations.AddConstraint(
            model_name="routingsolution",
            constraint=models.UniqueConstraint(
                condition=models.Q(("published_at__isnull", False)),
                fields=("dataset",),
                name="one_published_solution_per_dataset",
            ),
        ),
    ]
