from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("accounts", "0002_accessentitlement"),
        ("vocabulary", "0003_signvariant_vocab_variant_code_not_empty"),
    ]
    operations = [
        migrations.CreateModel(
            name="CommunicationSession",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("input_text", models.CharField(max_length=200)),
                ("status", models.CharField(max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("institution", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="communication_sessions", to="accounts.institution")),
                ("resolved_plan", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, to="vocabulary.signplan")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="communication_sessions", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="PilotCohort",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=120)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField(blank=True, null=True)),
                ("selected_plan_ids", models.JSONField(default=list)),
                ("selected_activity_ids", models.JSONField(default=list)),
                ("status", models.CharField(choices=[("planned", "Planned"), ("active", "Active"), ("closed", "Closed")], default="planned", max_length=16)),
                ("consent_required", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("institution", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pilot_cohorts", to="accounts.institution")),
            ],
        ),
        migrations.CreateModel(
            name="PracticeActivity",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("order", models.PositiveIntegerField(default=0)),
                ("difficulty", models.CharField(default="standard", max_length=32)),
                ("requires_consent", models.BooleanField(default=True)),
                ("model_version", models.CharField(default="synthetic-gru-v1", max_length=80)),
                ("schema_version", models.CharField(default="dualsign-landmarks-v1", max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("institution", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="practice_activities", to="accounts.institution")),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="practice_activities", to="vocabulary.signplan")),
                ("sign", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="practice_activities", to="vocabulary.sign")),
            ],
        ),
        migrations.CreateModel(
            name="CommunicationMessage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(max_length=32)),
                ("steps", models.JSONField(default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("plan", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="vocabulary.signplan")),
                ("session", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="messages", to="mvp.communicationsession")),
            ],
        ),
        migrations.CreateModel(
            name="PracticeAttempt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("result", models.CharField(choices=[("correct", "Correct"), ("incorrect", "Incorrect"), ("unknown", "Unknown")], max_length=16)),
                ("latency_ms", models.PositiveIntegerField(blank=True, null=True)),
                ("evaluation_mode", models.CharField(default="synthetic_scaffold", max_length=32)),
                ("inference_source", models.CharField(default="controlled_client", max_length=32)),
                ("consent_status", models.CharField(default="not_required", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("activity", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attempts", to="mvp.practiceactivity")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="practice_attempts", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="PilotParticipant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("cohort", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="participants", to="mvp.pilotcohort")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="pilot_participations", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddConstraint(
            model_name="pilotparticipant",
            constraint=models.UniqueConstraint(fields=("cohort", "user"), name="mvp_pilot_participant_unique"),
        ),
    ]
