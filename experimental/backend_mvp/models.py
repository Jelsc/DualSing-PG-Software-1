from django.conf import settings
from django.db import models


class CommunicationSession(models.Model):
    institution = models.ForeignKey("accounts.Institution", on_delete=models.PROTECT, related_name="communication_sessions")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="communication_sessions")
    input_text = models.CharField(max_length=200)
    status = models.CharField(max_length=32)
    resolved_plan = models.ForeignKey("vocabulary.SignPlan", blank=True, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class CommunicationMessage(models.Model):
    session = models.ForeignKey(CommunicationSession, on_delete=models.CASCADE, related_name="messages")
    plan = models.ForeignKey("vocabulary.SignPlan", on_delete=models.PROTECT)
    status = models.CharField(max_length=32)
    steps = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)


class PracticeActivity(models.Model):
    institution = models.ForeignKey("accounts.Institution", on_delete=models.PROTECT, related_name="practice_activities")
    plan = models.ForeignKey("vocabulary.SignPlan", on_delete=models.PROTECT, related_name="practice_activities")
    sign = models.ForeignKey("vocabulary.Sign", on_delete=models.PROTECT, related_name="practice_activities")
    order = models.PositiveIntegerField(default=0)
    difficulty = models.CharField(max_length=32, default="standard")
    requires_consent = models.BooleanField(default=True)
    model_version = models.CharField(max_length=80, default="synthetic-gru-v1")
    schema_version = models.CharField(max_length=80, default="dualsign-landmarks-v1")
    created_at = models.DateTimeField(auto_now_add=True)


class PracticeAttempt(models.Model):
    class Result(models.TextChoices):
        CORRECT = "correct", "Correct"
        INCORRECT = "incorrect", "Incorrect"
        UNKNOWN = "unknown", "Unknown"

    activity = models.ForeignKey(PracticeActivity, on_delete=models.PROTECT, related_name="attempts")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="practice_attempts")
    result = models.CharField(max_length=16, choices=Result.choices)
    latency_ms = models.PositiveIntegerField(blank=True, null=True)
    evaluation_mode = models.CharField(max_length=32, default="synthetic_scaffold")
    inference_source = models.CharField(max_length=32, default="controlled_client")
    consent_status = models.CharField(max_length=32, default="not_required")
    created_at = models.DateTimeField(auto_now_add=True)


class PilotCohort(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        CLOSED = "closed", "Closed"

    institution = models.ForeignKey("accounts.Institution", on_delete=models.PROTECT, related_name="pilot_cohorts")
    name = models.CharField(max_length=120)
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    selected_plan_ids = models.JSONField(default=list)
    selected_activity_ids = models.JSONField(default=list)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PLANNED)
    consent_required = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PilotParticipant(models.Model):
    cohort = models.ForeignKey(PilotCohort, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="pilot_participations")
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("cohort", "user"), name="mvp_pilot_participant_unique")
        ]
