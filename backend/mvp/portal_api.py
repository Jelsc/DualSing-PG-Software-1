import csv

from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone
from ninja import Router
from ninja.errors import HttpError
from ninja.security import django_auth

from accounts.models import AuditRecord, User, Membership
from accounts.policies import can_manage_pilots, can_view_institution
from accounts.security import require_csrf
from vocabulary.models import ReviewStatus, SignPlan, Sign

from .api import pilot_report
from .models import PilotCohort, PilotParticipant, PracticeActivity, PracticeAttempt
from .schemas import PortalAssignmentIn, PortalAssignmentOut, PortalEnrollmentIn, PortalMemberOut, PortalParticipantOut, PortalProgressOut, PilotCohortDetailOut, PilotCohortIn, PilotCohortPatch, PilotCohortOut
from .services import has_consent, percentile
from .schemas import PortalActivityIn

portal = Router(auth=django_auth)


def require_portal_institution(request, institution_id):
    institution = can_view_institution(request.auth, institution_id)
    if institution is None:
        raise HttpError(404, "Institution not found")
    return institution


def require_pilot_manager(request, institution_id):
    institution = require_portal_institution(request, institution_id)
    if not can_manage_pilots(request.auth, institution_id):
        raise HttpError(403, "Institution administrator required")
    return institution


def require_progress_viewer(request, institution_id):
    institution = require_portal_institution(request, institution_id)
    if request.auth.is_superuser and request.auth.is_staff:
        return institution
    if not Membership.objects.filter(
        user=request.auth,
        institution_id=institution_id,
        is_active=True,
        role__in=(Membership.Role.INSTITUTION_ADMIN, Membership.Role.VOCABULARY_REVIEWER),
        institution__is_active=True,
    ).exists():
        raise HttpError(403, "Institution administrator or vocabulary reviewer required")
    return institution


@portal.post("/{institution_id}/activities", response={201: dict})
@transaction.atomic
def create_portal_activity(request, institution_id: int, payload: PortalActivityIn):
    require_pilot_manager(request, institution_id)
    require_csrf(request)
    plan = SignPlan.objects.select_for_update().filter(
        pk=payload.plan_id, institution_id=institution_id,
        concept__institution_id=institution_id, status=ReviewStatus.VALIDATED,
    ).first()
    sign = Sign.objects.select_for_update().filter(
        pk=payload.sign_id, institution_id=institution_id,
        concept__institution_id=institution_id, status=ReviewStatus.VALIDATED,
    ).first()
    if plan is None or sign is None:
        raise HttpError(422, "Select a validated plan and sign from this institution")
    activity = PracticeActivity.objects.create(institution_id=institution_id, plan=plan, sign=sign)
    AuditRecord.objects.create(
        actor=request.auth, institution_id=institution_id,
        event_type="mvp.practice_activity_created", subject_type="practice_activity",
        subject_id=str(activity.id), metadata={"plan_id": plan.id, "sign_id": sign.id},
    )
    return 201, {"id": activity.id, "prompt": sign.gloss, "plan_id": plan.id}


def validate_selection(institution_id, plan_ids, activity_ids):
    if len(set(plan_ids)) != len(plan_ids) or len(set(activity_ids)) != len(activity_ids):
        raise HttpError(422, "Selected plan and activity IDs must be unique")
    plans = SignPlan.objects.filter(
        institution_id=institution_id,
        pk__in=plan_ids,
        concept__institution_id=institution_id,
        status=ReviewStatus.VALIDATED,
    )
    if plans.count() != len(plan_ids):
        raise HttpError(422, "Every selected plan must belong to this institution and be validated")
    activities = PracticeActivity.objects.filter(
        institution_id=institution_id,
        pk__in=activity_ids,
        plan__institution_id=institution_id,
        plan__concept__institution_id=institution_id,
        sign__institution_id=institution_id,
        sign__concept__institution_id=institution_id,
        plan__status=ReviewStatus.VALIDATED,
        sign__status=ReviewStatus.VALIDATED,
    )
    if activities.count() != len(activity_ids):
        raise HttpError(422, "Every selected activity must belong to this institution and use validated vocabulary")


def validate_fields(name, start_date, end_date, status):
    if not name.strip() or len(name.strip()) > 120:
        raise HttpError(422, "Cohort name must contain 1 to 120 characters")
    if end_date and end_date < start_date:
        raise HttpError(422, "End date cannot be before start date")
    if status not in PilotCohort.Status.values:
        raise HttpError(422, "Status must be planned, active, or closed")


def cohort_detail(cohort):
    return {
        "id": cohort.id,
        "name": cohort.name,
        "start_date": cohort.start_date,
        "end_date": cohort.end_date,
        "status": cohort.status,
        "consent_required": cohort.consent_required,
        "selected_plan_ids": cohort.selected_plan_ids,
        "selected_activity_ids": cohort.selected_activity_ids,
        "enrolled_count": cohort.participants.filter(status=PilotParticipant.Status.ACTIVE).count(),
        "report": None,
    }


def assignment_options(cohort):
    plans = list(SignPlan.objects.filter(
        institution_id=cohort.institution_id,
        concept__institution_id=cohort.institution_id,
        status=ReviewStatus.VALIDATED,
    ).select_related("concept").order_by("code", "id"))
    activities = list(PracticeActivity.objects.filter(
        institution_id=cohort.institution_id,
        plan__institution_id=cohort.institution_id,
        plan__concept__institution_id=cohort.institution_id,
        sign__institution_id=cohort.institution_id,
        sign__concept__institution_id=cohort.institution_id,
        plan__status=ReviewStatus.VALIDATED,
        sign__status=ReviewStatus.VALIDATED,
    ).select_related("plan", "sign").order_by("order", "id"))
    return {
        "selected_plan_ids": cohort.selected_plan_ids,
        "selected_activity_ids": cohort.selected_activity_ids,
        "plans": [{"id": plan.id, "code": plan.code, "label": plan.concept.label} for plan in plans],
        "activities": [{"id": activity.id, "prompt": activity.sign.gloss, "plan_id": activity.plan_id, "plan_code": activity.plan.code} for activity in activities],
    }


@portal.get("/{institution_id}/cohorts", response=list[PilotCohortOut])
def list_portal_cohorts(request, institution_id: int):
    require_portal_institution(request, institution_id)
    return [
        {
            "id": cohort.id,
            "name": cohort.name,
            "start_date": cohort.start_date,
            "end_date": cohort.end_date,
            "status": cohort.status,
            "consent_required": cohort.consent_required,
            "enrolled": False,
        }
        for cohort in PilotCohort.objects.filter(institution_id=institution_id).order_by("-created_at", "id")
    ]


@portal.get("/{institution_id}/cohorts/{cohort_id}", response=PilotCohortDetailOut)
def portal_cohort_detail(request, institution_id: int, cohort_id: int):
    require_portal_institution(request, institution_id)
    cohort = PilotCohort.objects.filter(pk=cohort_id, institution_id=institution_id).first()
    if cohort is None:
        raise HttpError(404, "Pilot cohort not found")
    detail = cohort_detail(cohort)
    detail["report"] = pilot_report(request, institution_id, cohort_id) if _can_view_progress(request, institution_id) else None
    return detail


def _can_view_progress(request, institution_id):
    if request.auth.is_superuser and request.auth.is_staff:
        return True
    return Membership.objects.filter(
        user=request.auth,
        institution_id=institution_id,
        is_active=True,
        role__in=(Membership.Role.INSTITUTION_ADMIN, Membership.Role.VOCABULARY_REVIEWER),
        institution__is_active=True,
    ).exists()


def portal_progress_data(institution_id, cohort):
    participants = list(cohort.participants.select_related("user").order_by("status", "joined_at", "id"))
    active_ids = [participant.user_id for participant in participants if participant.status == PilotParticipant.Status.ACTIVE and participant.user.is_active and Membership.objects.filter(user=participant.user, institution_id=institution_id, is_active=True, institution__is_active=True).exists()]
    activity_ids = list(PracticeActivity.objects.filter(
        pk__in=cohort.selected_activity_ids,
        institution_id=institution_id,
        plan__institution_id=institution_id,
        plan__concept__institution_id=institution_id,
        sign__institution_id=institution_id,
        sign__concept__institution_id=institution_id,
        plan__status=ReviewStatus.VALIDATED,
        sign__status=ReviewStatus.VALIDATED,
    ).values_list("id", flat=True))
    attempts = PracticeAttempt.objects.filter(user_id__in=[participant.user_id for participant in participants], activity_id__in=activity_ids, created_at__date__gte=cohort.start_date)
    if cohort.end_date:
        attempts = attempts.filter(created_at__date__lte=cohort.end_date)
    attempt_rows = list(attempts.values("user_id", "activity_id", "result", "latency_ms"))
    rows_by_user = {}
    for row in attempt_rows:
        summary = rows_by_user.setdefault(row["user_id"], {"attempts": 0, "correct": 0, "incorrect": 0, "unknown": 0, "latencies": [], "activities": set()})
        summary["attempts"] += 1
        summary[row["result"]] += 1
        summary["activities"].add(row["activity_id"])
        if row["latency_ms"] is not None:
            summary["latencies"].append(row["latency_ms"])
    participant_rows = []
    for participant in participants:
        summary = rows_by_user.get(participant.user_id, {"attempts": 0, "correct": 0, "incorrect": 0, "unknown": 0, "latencies": [], "activities": set()})
        participant_rows.append({"user_id": participant.user_id, "identifier": participant.user.email, "enrollment_status": participant.status, "attempts": summary["attempts"], "completed": participant.user_id in active_ids and bool(activity_ids) and len(summary["activities"]) == len(activity_ids), "correct": summary["correct"], "incorrect": summary["incorrect"], "unknown": summary["unknown"], "average_latency_ms": round(sum(summary["latencies"]) / len(summary["latencies"])) if summary["latencies"] else None})
    active_rows = [row for row in participant_rows if row["user_id"] in active_ids]
    result_rows = [row for row in attempt_rows if row["user_id"] in active_ids]
    total = len(result_rows)
    latencies = [row["latency_ms"] for row in result_rows if row["latency_ms"] is not None]
    return {
        "institution_id": institution_id,
        "cohort_id": cohort.id,
        "assigned_activity_count": len(activity_ids),
        "summary": {"enrolled_count": len(participants), "active_count": len(active_rows), "completed_count": sum(row["completed"] for row in active_rows), "participants_with_attempts": sum(row["attempts"] > 0 for row in active_rows), "attempts": {"total": total, "correct": sum(row["result"] == PracticeAttempt.Result.CORRECT for row in result_rows), "incorrect": sum(row["result"] == PracticeAttempt.Result.INCORRECT for row in result_rows), "unknown": sum(row["result"] == PracticeAttempt.Result.UNKNOWN for row in result_rows), "unknown_rate": sum(row["result"] == PracticeAttempt.Result.UNKNOWN for row in result_rows) / total if total else 0.0}, "completion_rate": sum(row["completed"] for row in active_rows) / len(active_rows) if active_rows else 0.0, "latency_ms": {"p50": percentile(latencies, 50), "p95": percentile(latencies, 95)}},
        "participants": participant_rows,
    }


@portal.get("/{institution_id}/cohorts/{cohort_id}/assignment", response=PortalAssignmentOut)
def portal_cohort_assignment(request, institution_id: int, cohort_id: int):
    require_progress_viewer(request, institution_id)
    cohort = PilotCohort.objects.filter(pk=cohort_id, institution_id=institution_id).first()
    if cohort is None:
        raise HttpError(404, "Pilot cohort not found")
    return assignment_options(cohort)


@portal.put("/{institution_id}/cohorts/{cohort_id}/assignment", response=PortalAssignmentOut)
def update_portal_cohort_assignment(request, institution_id: int, cohort_id: int, payload: PortalAssignmentIn):
    cohort = require_portal_cohort(request, institution_id, cohort_id)
    require_csrf(request)
    if cohort.status == PilotCohort.Status.CLOSED:
        raise HttpError(409, "Closed cohorts cannot change assignments")
    validate_selection(institution_id, payload.selected_plan_ids, payload.selected_activity_ids)
    cohort.selected_plan_ids = payload.selected_plan_ids
    cohort.selected_activity_ids = payload.selected_activity_ids
    cohort.save(update_fields=("selected_plan_ids", "selected_activity_ids"))
    AuditRecord.objects.create(actor=request.auth, institution_id=institution_id, event_type="mvp.pilot_cohort_assignment_updated", subject_type="pilot_cohort", subject_id=str(cohort.id), metadata={"plan_count": len(payload.selected_plan_ids), "activity_count": len(payload.selected_activity_ids)})
    return assignment_options(cohort)


@portal.get("/{institution_id}/cohorts/{cohort_id}/progress", response=PortalProgressOut)
def portal_cohort_progress(request, institution_id: int, cohort_id: int):
    require_progress_viewer(request, institution_id)
    cohort = PilotCohort.objects.filter(pk=cohort_id, institution_id=institution_id).first()
    if cohort is None:
        raise HttpError(404, "Pilot cohort not found")
    return portal_progress_data(institution_id, cohort)


EXPORT_COLUMNS = ("institution_id", "institution_name", "cohort_id", "cohort_name", "cohort_status", "start_date", "end_date", "assigned_activity_count", "enrolled_count", "active_count", "completed_count", "participants_with_attempts", "completion_rate", "attempts_total", "attempts_correct", "attempts_incorrect", "attempts_unknown", "unknown_rate", "latency_p50_ms", "latency_p95_ms", "participant_identifier", "enrollment_status", "participant_attempts", "participant_completed", "participant_correct", "participant_incorrect", "participant_unknown", "participant_average_latency_ms")


def csv_safe(value):
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


@portal.get("/{institution_id}/cohorts/{cohort_id}/progress/export")
def portal_cohort_progress_export(request, institution_id: int, cohort_id: int):
    institution = require_progress_viewer(request, institution_id)
    cohort = PilotCohort.objects.filter(pk=cohort_id, institution_id=institution_id).first()
    if cohort is None:
        raise HttpError(404, "Pilot cohort not found")
    progress = portal_progress_data(institution_id, cohort)
    summary = progress["summary"]
    attempts = summary["attempts"]
    base = {"institution_id": institution.id, "institution_name": institution.name, "cohort_id": cohort.id, "cohort_name": cohort.name, "cohort_status": cohort.status, "start_date": cohort.start_date, "end_date": cohort.end_date, "assigned_activity_count": progress["assigned_activity_count"], "enrolled_count": summary["enrolled_count"], "active_count": summary["active_count"], "completed_count": summary["completed_count"], "participants_with_attempts": summary["participants_with_attempts"], "completion_rate": summary["completion_rate"], "attempts_total": attempts["total"], "attempts_correct": attempts["correct"], "attempts_incorrect": attempts["incorrect"], "attempts_unknown": attempts["unknown"], "unknown_rate": attempts["unknown_rate"], "latency_p50_ms": summary["latency_ms"]["p50"], "latency_p95_ms": summary["latency_ms"]["p95"]}
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="cohort-{cohort.id}-progress.csv"'
    writer = csv.DictWriter(response, fieldnames=EXPORT_COLUMNS, lineterminator="\r\n")
    writer.writeheader()
    rows = progress["participants"] or [{}]
    for participant in rows:
        row = {**base, "participant_identifier": participant.get("identifier"), "enrollment_status": participant.get("enrollment_status"), "participant_attempts": participant.get("attempts"), "participant_completed": participant.get("completed"), "participant_correct": participant.get("correct"), "participant_incorrect": participant.get("incorrect"), "participant_unknown": participant.get("unknown"), "participant_average_latency_ms": participant.get("average_latency_ms")}
        writer.writerow({column: csv_safe(row.get(column)) for column in EXPORT_COLUMNS})
    return response


def require_portal_cohort(request, institution_id, cohort_id):
    require_pilot_manager(request, institution_id)
    cohort = PilotCohort.objects.filter(pk=cohort_id, institution_id=institution_id).first()
    if cohort is None:
        raise HttpError(404, "Pilot cohort not found")
    return cohort


def participant_row(participant):
    return {
        "participant_id": participant.id,
        "user_id": participant.user_id,
        "identifier": participant.user.email,
        "enrollment_status": participant.status,
        "enrolled_at": participant.joined_at,
        "consent_status": "granted" if has_consent(participant.user) else "not_granted",
    }


@portal.get("/{institution_id}/members", response=list[PortalMemberOut])
def list_portal_members(request, institution_id: int):
    require_pilot_manager(request, institution_id)
    return [
        {"user_id": user.id, "identifier": user.email}
        for user in User.objects.filter(
            is_active=True,
            memberships__institution_id=institution_id,
            memberships__is_active=True,
            memberships__institution__is_active=True,
        ).distinct().order_by("email")
    ]


@portal.get("/{institution_id}/cohorts/{cohort_id}/participants", response=list[PortalParticipantOut])
def list_portal_participants(request, institution_id: int, cohort_id: int):
    cohort = require_portal_cohort(request, institution_id, cohort_id)
    return [participant_row(participant) for participant in cohort.participants.select_related("user").order_by("status", "joined_at", "id")]


@portal.post("/{institution_id}/cohorts/{cohort_id}/participants", response={200: PortalParticipantOut, 201: PortalParticipantOut})
def enroll_portal_participant(request, institution_id: int, cohort_id: int, payload: PortalEnrollmentIn):
    cohort = require_portal_cohort(request, institution_id, cohort_id)
    require_csrf(request)
    if cohort.status == PilotCohort.Status.CLOSED:
        raise HttpError(409, "Closed cohorts cannot change enrollment")
    user = User.objects.filter(
        pk=payload.user_id,
        is_active=True,
        memberships__institution_id=institution_id,
        memberships__is_active=True,
        memberships__institution__is_active=True,
    ).first()
    if user is None:
        raise HttpError(404, "Active institution member not found")
    with transaction.atomic():
        participant, created = PilotParticipant.objects.select_for_update().get_or_create(cohort=cohort, user=user)
        if not created and participant.status == PilotParticipant.Status.ACTIVE:
            return 200, participant_row(participant)
        participant.status = PilotParticipant.Status.ACTIVE
        participant.deactivated_at = None
        participant.save(update_fields=("status", "deactivated_at"))
        AuditRecord.objects.create(actor=request.auth, institution=cohort.institution, event_type="mvp.pilot_participant_enrolled", subject_type="pilot_participant", subject_id=str(participant.id), metadata={"status": participant.status})
    return (201 if created else 200), participant_row(participant)


@portal.post("/{institution_id}/cohorts/{cohort_id}/participants/{user_id}/deactivate", response=PortalParticipantOut)
def deactivate_portal_participant(request, institution_id: int, cohort_id: int, user_id: int):
    cohort = require_portal_cohort(request, institution_id, cohort_id)
    require_csrf(request)
    if cohort.status == PilotCohort.Status.CLOSED:
        raise HttpError(409, "Closed cohorts cannot change enrollment")
    participant = cohort.participants.select_related("user").filter(user_id=user_id).first()
    if participant is None:
        raise HttpError(404, "Pilot participant not found")
    if participant.status == PilotParticipant.Status.ACTIVE:
        participant.status = PilotParticipant.Status.INACTIVE
        participant.deactivated_at = timezone.now()
        participant.save(update_fields=("status", "deactivated_at"))
        AuditRecord.objects.create(actor=request.auth, institution=cohort.institution, event_type="mvp.pilot_participant_deactivated", subject_type="pilot_participant", subject_id=str(participant.id), metadata={"status": participant.status})
    return participant_row(participant)


@portal.post("/{institution_id}/cohorts", response={201: PilotCohortDetailOut})
def create_portal_cohort(request, institution_id: int, payload: PilotCohortIn):
    require_pilot_manager(request, institution_id)
    require_csrf(request)
    validate_fields(payload.name, payload.start_date, payload.end_date, payload.status)
    if payload.status == PilotCohort.Status.CLOSED:
        raise HttpError(422, "A new cohort must be planned or active")
    validate_selection(institution_id, payload.selected_plan_ids, payload.selected_activity_ids)
    with transaction.atomic():
        cohort = PilotCohort.objects.create(institution_id=institution_id, **payload.dict())
        AuditRecord.objects.create(actor=request.auth, institution_id=institution_id, event_type="mvp.pilot_cohort_created", subject_type="pilot_cohort", subject_id=str(cohort.id))
    return 201, cohort_detail(cohort)


@portal.patch("/{institution_id}/cohorts/{cohort_id}", response=PilotCohortDetailOut)
def update_portal_cohort(request, institution_id: int, cohort_id: int, payload: PilotCohortPatch):
    require_pilot_manager(request, institution_id)
    require_csrf(request)
    cohort = PilotCohort.objects.filter(pk=cohort_id, institution_id=institution_id).first()
    if cohort is None:
        raise HttpError(404, "Pilot cohort not found")
    values = payload.dict(exclude_unset=True)
    start_date = values.get("start_date", cohort.start_date)
    end_date = values.get("end_date", cohort.end_date)
    status = values.get("status", cohort.status)
    validate_fields(values.get("name", cohort.name), start_date, end_date, status)
    valid_transitions = {
        PilotCohort.Status.PLANNED: {PilotCohort.Status.PLANNED, PilotCohort.Status.ACTIVE},
        PilotCohort.Status.ACTIVE: {PilotCohort.Status.ACTIVE, PilotCohort.Status.CLOSED},
        PilotCohort.Status.CLOSED: {PilotCohort.Status.CLOSED},
    }
    if status not in valid_transitions[cohort.status]:
        raise HttpError(409, f"Cannot transition cohort from {cohort.status} to {status}")
    validate_selection(institution_id, values.get("selected_plan_ids", cohort.selected_plan_ids), values.get("selected_activity_ids", cohort.selected_activity_ids))
    for field, value in values.items():
        setattr(cohort, field, value.strip() if field == "name" else value)
    cohort.save(update_fields=tuple(values))
    AuditRecord.objects.create(actor=request.auth, institution_id=institution_id, event_type="mvp.pilot_cohort_updated", subject_type="pilot_cohort", subject_id=str(cohort.id), metadata={"status": cohort.status})
    return cohort_detail(cohort)
