export type Membership = {
  institution_id: number;
  institution_name: string;
  role: string;
};

export type User = { id: number; email: string };
export type BillingStatus = { origin: "free" | "plus" | "enterprise_access"; subscription_status: string | null; current_period_end: string | null; cancel_at_period_end: boolean };
export type Concept = {
  id: number;
  code: string;
  label: string;
  description: string;
};
export type Alias = { id: number; concept_id: number; alias: string };
export type Sign = {
  id: number;
  sign_id: string;
  concept_id: number;
  gloss: string;
  language: string;
  status: Status;
};
export type Variant = {
  id: number;
  sign_id: number;
  variant_code: string;
  label: string;
  hamnosys: string;
};
export type PlanItem = {
  position: number;
  sign_id: number;
  stable_sign_id: string;
  gloss: string;
  variant_id: number | null;
};
export type Marker = {
  kind: string;
  value: string;
  start_position: number;
  end_position: number;
};
export type Plan = {
  id: number;
  code: string;
  concept_id: number;
  language: string;
  variant: string;
  non_manual_markers: Marker[];
  status: Status;
  items: PlanItem[];
};
export type Status = "draft" | "in_review" | "validated" | "rejected";
export type Catalog = {
  concepts: Concept[];
  aliases: Alias[];
  signs: Sign[];
  plans: Plan[];
};
export type CohortStatus = "planned" | "active" | "closed";
export type Cohort = {
  id: number;
  name: string;
  start_date: string;
  end_date: string | null;
  status: CohortStatus;
  consent_required: boolean;
  enrolled: boolean;
};
export type CohortReport = {
  participation: { enrolled: number; eligible: number; participants_with_attempts: number };
  attempts: { total: number; correct: number; incorrect: number; unknown: number; unknown_rate: number };
  latency_ms: { p50: number | null; p95: number | null };
};
export type CohortDetail = Cohort & {
  selected_plan_ids: number[];
  selected_activity_ids: number[];
  enrolled_count: number;
  report: CohortReport | null;
};
export type PortalMember = { user_id: number; identifier: string };
export type PortalParticipant = {
  participant_id: number;
  user_id: number;
  identifier: string;
  enrollment_status: "active" | "inactive";
  enrolled_at: string;
  consent_status: "granted" | "not_granted";
};
export type AssignmentPlan = { id: number; code: string; label: string };
export type AssignmentActivity = { id: number; prompt: string; plan_id: number; plan_code: string };
export type CohortAssignment = { selected_plan_ids: number[]; selected_activity_ids: number[]; plans: AssignmentPlan[]; activities: AssignmentActivity[] };
export type ProgressParticipant = { user_id: number; identifier: string; enrollment_status: "active" | "inactive"; attempts: number; completed: boolean; correct: number; incorrect: number; unknown: number; average_latency_ms: number | null };
export type CohortProgress = { institution_id: number; cohort_id: number; assigned_activity_count: number; summary: { enrolled_count: number; active_count: number; completed_count: number; participants_with_attempts: number; completion_rate: number; attempts: CohortReport["attempts"]; latency_ms: CohortReport["latency_ms"] }; participants: ProgressParticipant[] };

let csrfToken = "";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function refreshCsrf() {
  const response = await fetch("/api/web/csrf", { credentials: "include" });
  const body = await readBody(response);
  csrfToken = body.csrf_token;
}

async function readBody(response: Response) {
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = body.detail ?? body.message;
    const message =
      typeof detail === "string"
        ? detail
        : detail !== undefined
          ? JSON.stringify(detail)
          : `Request failed (${response.status})`;
    throw new ApiError(message, response.status);
  }
  return body;
}

export async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method ?? "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (method !== "GET" && method !== "HEAD") {
    if (!csrfToken) await refreshCsrf();
    headers.set("X-CSRFToken", csrfToken);
  }
  const response = await fetch(`/api${path}`, {
    ...options,
    method,
    headers,
    credentials: "include",
  });
  return readBody(response) as Promise<T>;
}

export async function loadCatalog(institutionId: number): Promise<Catalog> {
  const root = `/vocabulary/${institutionId}`;
  const [concepts, aliases, signs, plans] = await Promise.all([
    request<Concept[]>(`${root}/concepts`),
    request<Alias[]>(`${root}/aliases`),
    request<Sign[]>(`${root}/signs`),
    request<Plan[]>(`${root}/plans`),
  ]);
  return { concepts, aliases, signs, plans };
}

export function billingLabel(origin: BillingStatus["origin"]) {
  return origin === "plus" ? "Plus" : origin === "enterprise_access" ? "Enterprise" : "Free";
}

export function statusLabel(status: Status) {
  return {
    draft: "Draft",
    in_review: "In review",
    validated: "Validated",
    rejected: "Rejected",
  }[status];
}
