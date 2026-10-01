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
