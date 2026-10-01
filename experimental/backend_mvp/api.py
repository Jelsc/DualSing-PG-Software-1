from django.db import transaction
from ninja import Router
from ninja.errors import HttpError

from accounts.models import AuditRecord
from accounts.policies import can_view_institution
from accounts.authentication import LiveUserJWTAuth
from vocabulary.models import ReviewStatus, SignPlan

from .models import CommunicationMessage, CommunicationSession, PilotCohort, PracticeActivity, PracticeAttempt
from .schemas import (
    CommunicationOut,
    PilotReportOut,
    PracticeActivityOut,
    PracticeAttemptIn,
    PracticeAttemptOut,
    ResolveIn,
)
from .services import find_controlled_concept, has_consent, percentile, playback_steps

mvp = Router(auth=LiveUserJWTAuth())


def require_member(request, institution_id):
    institution = can_view_institution(request.auth, institution_id)
    if institution is None:
        raise HttpError(404, "Institution not found")
    return institution


@mvp.post("/{institution_id}/communication/resolve", response=CommunicationOut)
def resolve_communication(request, institution_id: int, payload: ResolveIn):
    institution = require_member(request, institution_id)
    if not payload.input.strip() or len(payload.input) > 200:
        raise HttpError(422, "Input must be a controlled alias or intent")
    with transaction.atomic():
        session = CommunicationSession.objects.create(
            institution=institution, user=request.auth, input_text=payload.input, status="unsupported_input"
        )
        concept = find_controlled_concept(institution_id, payload.input)
        if concept is None:
            return {"session_id": session.id, "status": "unsupported_input", "plan_id": None, "steps": [], "reason": "Input is not in the controlled institution vocabulary."}
        plan = SignPlan.objects.filter(
            institution_id=institution_id, concept=concept, status=ReviewStatus.VALIDATED
        ).prefetch_related("items__sign").first()
        if plan is None:
            session.status = "unvalidated_vocabulary"
            session.save(update_fields=("status",))
            return {"session_id": session.id, "status": "unvalidated_vocabulary", "plan_id": None, "steps": [], "reason": "The matched vocabulary has no validated sign plan."}
        steps = playback_steps(plan)
        session.status = "missing_clip_mapping"
        session.resolved_plan = plan
        session.save(update_fields=("status", "resolved_plan"))
        CommunicationMessage.objects.create(session=session, plan=plan, status="missing_clip_mapping", steps=steps)
        return {"session_id": session.id, "status": "missing_clip_mapping", "plan_id": plan.id, "steps": steps, "reason": "No real playback assets are included in this scaffold."}


@mvp.get("/{institution_id}/practice/activities", response=list[PracticeActivityOut])
def list_activities(request, institution_id: int):
    require_member(request, institution_id)
    return [
        {"id": activity.id, "prompt": activity.sign.gloss, "sign_id": activity.sign.sign_id, "model_version": activity.model_version, "evaluation_mode": "synthetic_scaffold"}
        for activity in PracticeActivity.objects.filter(
            institution_id=institution_id, plan__status=ReviewStatus.VALIDATED, sign__status=ReviewStatus.VALIDATED
        ).select_related("sign", "plan").order_by("order", "id")
    ]


@mvp.post("/{institution_id}/practice/activities/{activity_id}/attempt", response=PracticeAttemptOut)
def submit_attempt(request, institution_id: int, activity_id: int, payload: PracticeAttemptIn):
    require_member(request, institution_id)
    activity = PracticeActivity.objects.filter(
        pk=activity_id, institution_id=institution_id, plan__status=ReviewStatus.VALIDATED, sign__status=ReviewStatus.VALIDATED
    ).select_related("plan", "sign").first()
    if activity is None:
        raise HttpError(404, "Practice activity not found")
    if payload.result not in PracticeAttempt.Result.values:
        raise HttpError(422, "Result must be correct, incorrect, or unknown")
    if payload.latency_ms is not None and payload.latency_ms < 0:
        raise HttpError(422, "Latency cannot be negative")
    consent_status = "not_required"
    if activity.requires_consent:
        if not has_consent(request.auth):
            raise HttpError(403, "Practice consent is required")
        consent_status = "granted"
    attempt = PracticeAttempt.objects.create(
        activity=activity, user=request.auth, result=payload.result, latency_ms=payload.latency_ms,
        evaluation_mode="synthetic_scaffold", inference_source="controlled_client", consent_status=consent_status,
    )
    return attempt


@mvp.get("/{institution_id}/pilots/{cohort_id}/report", response=PilotReportOut)
def pilot_report(request, institution_id: int, cohort_id: int):
    require_member(request, institution_id)
    cohort = PilotCohort.objects.filter(pk=cohort_id, institution_id=institution_id).first()
    if cohort is None:
        raise HttpError(404, "Pilot cohort not found")
    participant_ids = cohort.participants.values_list("user_id", flat=True)
    attempts = PracticeAttempt.objects.filter(
        user_id__in=participant_ids,
        activity__institution_id=institution_id,
        created_at__date__gte=cohort.start_date,
    )
    # An empty selection means all institution-scoped activities; otherwise the
    # cohort's activity selection is an explicit allowlist.
    if cohort.selected_activity_ids:
        attempts = attempts.filter(activity_id__in=cohort.selected_activity_ids)
    if cohort.end_date:
        attempts = attempts.filter(created_at__date__lte=cohort.end_date)
    rows = list(attempts.values("result", "latency_ms", "activity__model_version", "user_id"))
    total = len(rows)
    unknown = sum(row["result"] == PracticeAttempt.Result.UNKNOWN for row in rows)
    return {
        "cohort_id": cohort.id,
        "period": {"start": cohort.start_date, "end": cohort.end_date},
        "participation": {"enrolled": cohort.participants.count(), "eligible": cohort.participants.count(), "participants_with_attempts": len({row["user_id"] for row in rows})},
        "attempts": {"total": total, "correct": sum(row["result"] == PracticeAttempt.Result.CORRECT for row in rows), "incorrect": sum(row["result"] == PracticeAttempt.Result.INCORRECT for row in rows), "unknown": unknown, "unknown_rate": unknown / total if total else 0.0},
        "latency_ms": {"p50": percentile([row["latency_ms"] for row in rows if row["latency_ms"] is not None], 50), "p95": percentile([row["latency_ms"] for row in rows if row["latency_ms"] is not None], 95)},
        "playback": {"error_count": 0},
        "catalog_version": "validated-vocabulary",
        "model_versions": sorted({row["activity__model_version"] for row in rows}),
    }
