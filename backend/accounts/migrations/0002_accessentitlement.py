from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AccessEntitlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origin", models.CharField(choices=[("free", "Free"), ("plus", "Plus"), ("enterprise_access", "Enterprise access")], default="free", max_length=32)),
                ("capabilities", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="access_entitlement", to="accounts.user")),
            ],
            options={
                "constraints": [models.CheckConstraint(condition=models.Q(("origin__in", ("free", "plus", "enterprise_access"))), name="access_entitlement_origin_valid")],
            },
        ),
    ]
