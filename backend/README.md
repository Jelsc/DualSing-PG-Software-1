# Backend identity and vocabulary API

Phase 1 supplies identity, institution membership, tenant authorization, consent history, and append-only audit events. Phase 2 adds a bounded LSB vocabulary catalog and an internal SignPlan representation. The active Phase 6/8/9 MVP adds controlled communication, synthetic practice, pilot enrollment, aggregate reporting, and company pilot-cohort management in `/portal`. It does not supply a renderer, language grammar, or translation service.

## Quick path

1. Compose applies migrations when the backend starts. For an already-running stack, run `docker compose exec -T backend python manage.py migrate`.
2. A web vocabulary manager signs in through `/api/web/login`, keeps the session cookie, fetches `/api/web/csrf`, and sends `X-CSRFToken` on every vocabulary write.
3. Vocabulary endpoints live under `/api/vocabulary/{institution_id}`; Flutter read-only endpoints use `/api/mobile/vocabulary/{institution_id}` with a bearer access JWT.

## Mobile authentication

`POST /api/mobile/token` accepts `{ "email", "password" }` and returns `{ "access", "refresh", "token_type": "Bearer" }`. `POST /api/mobile/register` accepts `{ "email", "password", "password_confirmation" }` and returns the same token shape after Django email and password validation. Duplicate email returns `409`; invalid input returns `422`; login failures return `401`. Refresh and revoke remain `/api/mobile/token/refresh` and `/api/mobile/token/revoke`.

Registration creates a personal `User` with a hashed password and an audit event only. It never creates `Membership` or `AccessEntitlement`; institution membership and enterprise access are granted separately by authorized flows. The endpoint is public and does not alter CSRF-protected browser routes. Password reset, SSO, domain validation, and Play Billing are not implemented or implied.

## Catalog and SignPlan

| Record | Purpose | Stable or tenant key |
| --- | --- | --- |
| Concept | A meaning/intent independent of its lexical realization | Unique `code` per institution |
| Sign | A lexical sign linked to a concept; includes gloss and language | Unique `sign_id` per institution |
| Sign variant | A locally named variant of one sign | Unique `variant_code` per sign |
| Concept alias | A normalized text alias mapped to one concept | Unique normalized alias per institution |
| SignPlan | Provisional renderer-independent sequence for a concept | Unique `code` per institution |
| SignPlan item | Ordered reference to a sign and optional variant | Unique position per plan |

`lsb` is the default language label; `variant` is an institution-local label. A SignPlan stores ordered sign references plus structured non-manual markers (`kind`, `value`, `start_position`, `end_position`). It is DualSign's provisional internal DSR contract—not a public LSB standard, a claim that literal sign concatenation is grammatical, or a renderer/animation contract. Marker semantics and plan validation remain human-controlled. Optional HamNoSys is opaque notation only; SiGML is not implemented. No signs or aliases are seeded, and aliases do not translate free text.

### Lifecycle

Signs and plans begin as `draft`. `POST .../{id}/review` moves a draft to `in_review`; `POST .../{id}/validate` publishes an in-review record; `POST .../{id}/reject` rejects an in-review record; and `POST .../{id}/reopen` returns a rejected record to draft. Other transitions return `409`.

A plan can be published only when it has at least one item, its concept belongs to the same institution, every referenced sign is validated, optional variants belong to the referenced signs, and all marker positions are within the ordered sequence. The API scopes lookups and validates related records against the requested institution; database constraints cover catalog codes, alias normalization, and per-plan ordering, but PostgreSQL does not enforce cross-institution plan references with composite foreign keys.

## API shape

| Action | Request/response outline |
| --- | --- |
| `POST /api/vocabulary/{institution_id}/concepts` | `{ "code", "label", "description?" }` → concept with `id` |
| `POST /api/vocabulary/{institution_id}/signs` | `{ "sign_id", "concept_id", "gloss", "language?" }` → draft sign |
| `POST /api/vocabulary/{institution_id}/concepts/{concept_id}/aliases` | `{ "alias" }` → alias mapped to the concept |
| `POST /api/vocabulary/{institution_id}/plans` | `{ "code", "concept_id", "language?", "variant?", "non_manual_markers?", "items": [{"sign_id", "variant_id?"}] }` → draft plan including ordered items |
| `GET /api/mobile/vocabulary/{institution_id}/signs` | Validated signs only |
| `GET /api/mobile/vocabulary/{institution_id}/plans` | Validated plans only, with ordered stable sign IDs, glosses, and optional variant IDs |
| `GET /api/mobile/vocabulary/{institution_id}/concepts` and `/aliases` | Concepts with validated signs and their aliases only |
| `GET /api/mobile/vocabulary/{institution_id}/signs/{sign_pk}/variants` | Variants only when the parent sign is validated |

Admin catalog routes also provide scoped list, patch, delete, and lifecycle actions where applicable. Conflict and invalid-reference responses use `409` and `422`; cross-institution object lookups return `404`.

## Authorization matrix

| Caller | Admin catalog read/write/review | Mobile catalog reads |
| --- | --- | --- |
| Institution administrator, active membership | Yes, for that institution; writes require session + CSRF | Yes, active institution only |
| Vocabulary reviewer, active membership | Yes, for that institution; writes require session + CSRF | Yes, active institution only |
| Operator, active membership | No | Yes, validated records in that institution |
| Platform staff superuser | Yes, explicit tenant bypass for active institutions | Yes, explicit tenant bypass for active institutions |
| Other/inactive membership | No | No |

Role and tenant checks reuse `accounts.policies`; JWT role claims are not trusted. Admin CRUD uses Django sessions and CSRF. Mobile endpoints use live-user JWT auth and are read-only.

## Communication, practice, and pilots MVP

The active JWT-protected routes live under `/api/mobile/mvp/{institution_id}`. Communication accepts only exact controlled intent/alias input and returns `unsupported_input`, `missing_plan`, or `missing_clip_mapping`. Practice only exposes activities whose institution, plan, concept, and sign relationships agree; attempts require active membership and consent where configured. `GET /api/mobile/mvp/{institution_id}/pilots/cohorts` returns only safe metadata for planned/active cohorts visible to the authenticated member, including whether that user is enrolled. Closed cohorts are excluded and reject enrollment. Institution administrators create cohorts, assign validated plans/activities, and manage participant rosters through the session-authenticated `/api/portal/{institution_id}` endpoints: members are listed by safe identifier, enrollment is idempotent, and deactivation preserves the participant and audit history. Institution administrators and vocabulary reviewers can read `/cohorts/{cohort_id}/progress`, which returns aggregate synthetic MVP metrics plus safe operational participant rows. Historical enrollment counts include inactive records; active totals and completion exclude inactive participants. Assignment and progress routes are tenant-scoped, reject cross-tenant or unvalidated IDs, and never return credentials, tokens, videos, raw attempts, raw payloads, or unrestricted event data. Flutter continues consuming assigned/enrolled cohorts through the mobile API. The internal `/backoffice` remains a DualSign operations surface, not the company cohort manager.

Reports filter participants, attempts, and selected activities to the cohort institution, even when no activity selection is supplied. Portal progress and `GET /api/portal/{institution_id}/cohorts/{cohort_id}/progress/export` are controlled aggregate/synthetic MVP reports only: completion means an active participant attempted every assigned validated activity within the cohort window. CSV export uses a fixed column order, includes cohort aggregates plus only the authorized institutional identifier and aggregate participant progress, and returns a stable header plus one aggregate row for an empty cohort. Formula-like text is neutralized for spreadsheet safety. Latency is exposed only as p50/p95 aggregate values and per-participant average latency. Advanced analytics, raw media, raw attempt payloads, passwords, tokens, and unrestricted event exploration are not implemented or exported. Practice uses a synthetic scaffold and preserves `UNKNOWN`; no camera recognition, real avatar assets, real dataset, or Stripe is included.

## Audit and future boundaries

Catalog create/edit/delete, lifecycle actions, and pilot enrollment append `AuditRecord` events with actor, institution, subject ID, and status only. No credentials, token values, marker payloads, aliases, video, conversation text, or unnecessary personal data are logged. Free-text translation/LLM, grammar/transliteration, datasets, renderer integration, Babylon, GLB, Unity, video, animation clips, and billing remain out of scope.

The original MVP copies remain under `../experimental/backend_mvp/` and `../experimental/mobile_mvp/` until verification is complete. React/Flutter consumers must continue to rely on backend policy checks; enterprise access remains represented by institution-owned `AccessEntitlement` and is never granted from client input.

## Stripe billing

`POST /api/mobile/billing/plus/checkout` creates an individual Plus hosted Checkout Session for a JWT user. The session URL is returned to Flutter. `GET /api/mobile/billing/status` returns the effective server entitlement. Session-authenticated portal users can read `/api/billing/status`; active institution administrators can use `POST /api/billing/enterprise/{institution_id}/checkout`. The read-only backoffice boundary includes billing status but cannot create checkout sessions.

Stripe sends lifecycle events to `POST /api/billing/webhook`. The endpoint verifies the `Stripe-Signature` against the raw request body and deduplicates event IDs. It handles `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, and `customer.subscription.deleted`. Missing test configuration returns `503`; no fake paid state is created. Tests mock Stripe and make no live calls. Hosted Checkout is intentional for this Android MVP; Play Billing migration is required for Google Play distribution.

## Docker checks

```powershell
docker compose config -q
docker compose exec -T backend python manage.py migrate --noinput
docker compose exec -T backend python manage.py test
docker compose exec -T backend python manage.py makemigrations --check --dry-run
```

The backend uses Django Ninja with the Phase 1 hybrid auth setup. Audit and consent records are append-only application records; consent history does not replace legal review.
