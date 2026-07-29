from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("optimization", "0015_optimizationjob_config_preset_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="routingsolution",
            name="participants",
            field=models.ManyToManyField(
                blank=True,
                related_name="solution_participations",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
