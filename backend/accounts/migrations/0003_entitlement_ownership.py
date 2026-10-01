from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("accounts", "0002_accessentitlement")]
    operations = [
        migrations.AlterField(model_name="accessentitlement", name="user", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="access_entitlements", to="accounts.user")),
        migrations.AddField(model_name="accessentitlement", name="institution", field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="access_entitlements", to="accounts.institution")),
        migrations.RemoveConstraint(model_name="accessentitlement", name="access_entitlement_origin_valid"),
        migrations.AddConstraint(model_name="accessentitlement", constraint=models.CheckConstraint(condition=(models.Q(("institution__isnull", True), ("user__isnull", False), _connector="AND") | models.Q(("institution__isnull", False), ("user__isnull", True))), name="access_entitlement_one_owner")),
        migrations.AddConstraint(model_name="accessentitlement", constraint=models.UniqueConstraint(condition=models.Q(("user__isnull", False)), fields=("user",), name="unique_user_access_entitlement")),
        migrations.AddConstraint(model_name="accessentitlement", constraint=models.UniqueConstraint(condition=models.Q(("institution__isnull", False)), fields=("institution",), name="unique_institution_access_entitlement")),
        migrations.AddConstraint(model_name="accessentitlement", constraint=models.CheckConstraint(condition=models.Q(origin__in=("free", "plus", "enterprise_access")), name="access_entitlement_origin_valid")),
    ]
