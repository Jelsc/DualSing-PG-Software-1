from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True
    dependencies = [("accounts", "0002_accessentitlement")]
    operations = [
        migrations.CreateModel(name="ProcessedStripeEvent", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("event_id", models.CharField(max_length=255, unique=True)), ("event_type", models.CharField(max_length=255)), ("processed_at", models.DateTimeField(default=django.utils.timezone.now))]),
        migrations.CreateModel(name="Subscription", fields=[("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("plan", models.CharField(choices=[("plus", "Plus"), ("enterprise", "Enterprise")], max_length=20)), ("stripe_customer_id", models.CharField(blank=True, max_length=255)), ("stripe_subscription_id", models.CharField(max_length=255, unique=True)), ("status", models.CharField(choices=[("incomplete", "Incomplete"), ("active", "Active"), ("past_due", "Past due"), ("canceled", "Canceled"), ("unpaid", "Unpaid")], default="incomplete", max_length=20)), ("current_period_start", models.DateTimeField(blank=True, null=True)), ("current_period_end", models.DateTimeField(blank=True, null=True)), ("cancel_at_period_end", models.BooleanField(default=False)), ("created_at", models.DateTimeField(auto_now_add=True)), ("updated_at", models.DateTimeField(auto_now=True)), ("institution", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="accounts.institution")), ("user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="subscriptions", to="accounts.user"))]),
        migrations.AddConstraint(model_name="subscription", constraint=models.CheckConstraint(condition=models.Q(("institution__isnull", True), ("user__isnull", False), _connector="AND") | models.Q(("institution__isnull", False), ("user__isnull", True)), name="subscription_one_owner")),
    ]
