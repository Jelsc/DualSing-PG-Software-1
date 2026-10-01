from django.db import models
from django.utils import timezone


class Subscription(models.Model):
    class Plan(models.TextChoices):
        PLUS = "plus", "Plus"
        ENTERPRISE = "enterprise", "Enterprise"

    class Status(models.TextChoices):
        INCOMPLETE = "incomplete", "Incomplete"
        ACTIVE = "active", "Active"
        PAST_DUE = "past_due", "Past due"
        CANCELED = "canceled", "Canceled"
        UNPAID = "unpaid", "Unpaid"

    user = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.PROTECT, related_name="subscriptions")
    institution = models.ForeignKey("accounts.Institution", null=True, blank=True, on_delete=models.PROTECT, related_name="subscriptions")
    plan = models.CharField(max_length=20, choices=Plan.choices)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INCOMPLETE)
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=(models.Q(user__isnull=False, institution__isnull=True) | models.Q(user__isnull=True, institution__isnull=False)), name="subscription_one_owner"),
        ]


class ProcessedStripeEvent(models.Model):
    event_id = models.CharField(max_length=255, unique=True)
    event_type = models.CharField(max_length=255)
    processed_at = models.DateTimeField(default=timezone.now)
