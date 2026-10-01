from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("mvp", "0001_initial")]

    operations = [
        migrations.AddField(
            model_name="pilotparticipant",
            name="deactivated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pilotparticipant",
            name="status",
            field=models.CharField(choices=[("active", "Active"), ("inactive", "Inactive")], default="active", max_length=16),
        ),
    ]
