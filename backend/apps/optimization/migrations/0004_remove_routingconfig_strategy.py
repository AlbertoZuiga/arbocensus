from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("optimization", "0003_routingsolution_strategy"),
    ]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE optimization_routingconfig DROP COLUMN IF EXISTS strategy;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
