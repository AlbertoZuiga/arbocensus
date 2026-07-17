import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("optimization", "0012_alter_optimizationjob_strategy"),
    ]

    operations = [
        migrations.AlterField(
            model_name="routingconfig",
            name="service_time_sec",
            field=models.IntegerField(
                default=180, validators=[django.core.validators.MinValueValidator(1)]
            ),
        ),
    ]
