from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("routes", "0003_treeobservation"),
    ]

    operations = [
        migrations.AddField(
            model_name="treeobservation",
            name="source",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AlterField(
            model_name="treeobservation",
            name="photo_url",
            field=models.URLField(blank=True, max_length=500),
        ),
    ]
