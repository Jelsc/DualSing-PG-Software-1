from datetime import date, datetime

from ninja import Schema


class ResolveIn(Schema):
    input: str


class CommunicationStepOut(Schema):
    position: int
    stable_sign_id: str
    clip_key: str
    asset_available: bool
    gloss: str


class CommunicationOut(Schema):
    session_id: int
    status: str
    plan_id: int | None
    steps: list[CommunicationStepOut]
    reason: str | None


class PracticeActivityOut(Schema):
    id: int
    prompt: str
    sign_id: str
    model_version: str
    evaluation_mode: str


class PracticeAttemptIn(Schema):
    result: str = "unknown"
    latency_ms: int | None = None


class PracticeAttemptOut(Schema):
    result: str
    latency_ms: int | None
    evaluation_mode: str
    inference_source: str
    consent_status: str


class PilotEnrollmentOut(Schema):
    cohort_id: int
    user_id: int
    enrolled: bool


class PortalMemberOut(Schema):
    user_id: int
    identifier: str


class PortalParticipantOut(Schema):
    participant_id: int
    user_id: int
    identifier: str
    enrollment_status: str
    enrolled_at: datetime
    consent_status: str


class PortalAssignmentPlanOut(Schema):
    id: int
    code: str
    label: str


class PortalAssignmentActivityOut(Schema):
    id: int
    prompt: str
    plan_id: int
    plan_code: str


class PortalAssignmentOut(Schema):
    selected_plan_ids: list[int]
    selected_activity_ids: list[int]
    plans: list[PortalAssignmentPlanOut]
    activities: list[PortalAssignmentActivityOut]


class PortalAssignmentIn(Schema):
    selected_plan_ids: list[int] = []
    selected_activity_ids: list[int] = []


class PortalProgressParticipantOut(Schema):
    user_id: int
    identifier: str
    enrollment_status: str
    attempts: int
    completed: bool
    correct: int
    incorrect: int
    unknown: int
    average_latency_ms: int | None


class PortalEnrollmentIn(Schema):
    user_id: int


class PilotCohortOut(Schema):
    id: int
    name: str
    start_date: date
    end_date: date | None
    status: str
    consent_required: bool
    enrolled: bool


class PilotCohortIn(Schema):
    name: str
    start_date: date
    end_date: date | None = None
    status: str = "planned"
    consent_required: bool = True
    selected_plan_ids: list[int] = []
    selected_activity_ids: list[int] = []


class PilotCohortPatch(Schema):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None
    consent_required: bool | None = None
    selected_plan_ids: list[int] | None = None
    selected_activity_ids: list[int] | None = None


class PilotPeriodOut(Schema):
    start: date
    end: date | None


class PilotParticipationOut(Schema):
    enrolled: int
    eligible: int
    participants_with_attempts: int


class PilotAttemptsOut(Schema):
    total: int
    correct: int
    incorrect: int
    unknown: int
    unknown_rate: float


class PilotLatencyOut(Schema):
    p50: int | None
    p95: int | None


class PortalProgressSummaryOut(Schema):
    enrolled_count: int
    active_count: int
    completed_count: int
    participants_with_attempts: int
    attempts: PilotAttemptsOut
    completion_rate: float
    latency_ms: PilotLatencyOut


class PortalProgressOut(Schema):
    institution_id: int
    cohort_id: int
    assigned_activity_count: int
    summary: PortalProgressSummaryOut
    participants: list[PortalProgressParticipantOut]


class PilotPlaybackOut(Schema):
    error_count: int


class PilotReportOut(Schema):
    cohort_id: int
    period: PilotPeriodOut
    participation: PilotParticipationOut
    attempts: PilotAttemptsOut
    latency_ms: PilotLatencyOut
    playback: PilotPlaybackOut
    catalog_version: str
    model_versions: list[str]


class PilotCohortDetailOut(Schema):
    id: int
    name: str
    start_date: date
    end_date: date | None
    status: str
    consent_required: bool
    selected_plan_ids: list[int]
    selected_activity_ids: list[int]
    enrolled_count: int
    report: PilotReportOut | None
