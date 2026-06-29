from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("optimization", "0004_remove_routingconfig_strategy"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="routingsolution",
            unique_together={("job", "strategy")},
        ),
    ]
