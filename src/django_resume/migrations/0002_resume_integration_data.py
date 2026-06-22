from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_resume", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="resume",
            name="integration_data",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
