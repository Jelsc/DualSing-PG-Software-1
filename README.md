# DualSign IA

DualSign provides a tenant-scoped LSB vocabulary catalog and a provisional, renderer-independent SignPlan API, with separate internal backoffice, company portal, consumer/mobile, avatar, offline ML, and active Communication/Practice/Pilot MVP capabilities. Each area keeps its own runtime boundary; the MVP reuses the existing backend service and Flutter app without adding a Compose service.

## Quick Start

1. Create `.env` from `.env.example` only if a local `.env` does not already exist:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

2. Build and start the local services:

   ```powershell
   docker compose up --build
   ```

3. Open the product surface index at <http://127.0.0.1:8080>. The API health endpoint is <http://127.0.0.1:8080/api/health>.

Stop the services with `docker compose down`. Named data volumes are retained unless explicitly removed with `docker compose down -v`.

## Service Map

| Service | Purpose | Local address |
| --- | --- | --- |
| Nginx | Public local entry point; routes `/` to Next.js and `/api/` to Django | `127.0.0.1:8080` |
| Frontend | Next.js product index, company portal, and internal backoffice shell | Routed through Nginx |
| Backend | Django + Django Ninja health API | Routed through Nginx |
| PostgreSQL | Development database | `127.0.0.1:5432` |
| Redis | Celery broker and development cache | `127.0.0.1:6379` |
| Celery worker | Background worker process | Internal Compose network |
| MinIO | Local object-storage service and console | `127.0.0.1:9000`, `127.0.0.1:9001` |

Only Nginx is the public web entry point. The frontend uses the same-origin API base `/api`; container hostnames are not exposed to the browser.

## Mobile Development

`mobile/` is a Flutter learner pilot slice with interactive Android login/registration, secure access/refresh token persistence, logout, five navigation areas, and institution/cohort-scoped MVP HTTP repositories. Registration creates only a personal account; institution membership and enterprise access are granted separately. Practice is synthetic/manual only; there is no camera recognition, real ML, real avatar asset, or WebView integration. It is source for a device or emulator, not a main Compose service or a source of demo learning/sign content. Run its auth and MVP tests in the Flutter SDK container:

```powershell
$repo = (Get-Location).Path
docker run --rm --mount "type=bind,source=$repo\mobile,target=/workspace" --workdir /workspace ghcr.io/cirruslabs/flutter:stable flutter test
```

For the local Android emulator, use `--dart-define=DUALSIGN_API_BASE_URL=http://10.0.2.2:8080/api/`. After authentication, the mobile app loads active memberships from `/api/mobile/me`, then loads planned/active cohorts from the server for the selected institution. `DUALSIGN_INSTITUTION_ID` and `DUALSIGN_COHORT_ID` are optional development defaults only and are accepted only when the server returns those memberships/cohorts. Cohort creation remains portal/backoffice work; Stripe is unrelated to this flow and unchanged.

## Integrated source areas

| Area | Purpose and runtime boundary | Verification |
| --- | --- | --- |
| `frontend/` | Phase 3 session + CSRF vocabulary workbench, served at `/` through the existing Nginx and frontend services | `docker compose exec -T frontend npm run lint`; `docker compose exec -T frontend npx tsc --noEmit` |
| `mobile/` | Flutter learning/navigation shell for device or emulator use; not hosted by the web service | Flutter SDK container command above |
| `avatar-engine/` | Reusable Babylon.js GLB loader and named-animation sequencer package; not a persistent service | `docker build -t dualsign-avatar-engine avatar-engine` (runs format check, build, and tests) |
| `ml/` | Offline PyTorch training/export scaffold; synthetic tests only, not a Compose service | `docker build -f ml/Dockerfile -t dualsign-ml .` then `docker run --rm --network none dualsign-ml` |

The avatar package contains no GLB assets. The ML package contains no real LSB samples, recordings, or accuracy claims. Neither area adds a service or port to the main Compose configuration.

## Environment and Deployment

`.env.example` contains development-only placeholders. `.env` is local and ignored by Git; replace placeholders for local use, and never put real credentials in the example file.

**The Compose images, credentials, and debug settings are for local development only. They are not production deployment configuration.**

## Backend identity and vocabulary (Phases 1–2)

The browser authenticates through Django sessions and CSRF-protected same-origin requests. Flutter uses interactive login/registration, short-lived access JWTs, and rotating, revocable refresh JWTs. Institution roles and access are resolved from live active memberships; platform administrators are Django staff superusers. A user's active memberships and route policies are described in [`backend/README.md`](backend/README.md).

Compose applies database migrations before starting the backend. The browser workbench uses session + CSRF-protected admin APIs and mobile uses interactive login/registration plus read-only JWT endpoints. Admin variant listing is institution-scoped and variant deletion remains protected by plan-reference constraints. See [`backend/README.md`](backend/README.md) for lifecycle, role matrix, auth payloads, and Docker checks. Run backend checks with `docker compose exec -T backend python manage.py test` and `docker compose exec -T backend python manage.py makemigrations --check --dry-run`.

## Active MVP: communication, practice, and pilots

The Phase 6/8/9 slice is active under `backend/mvp/`, `backend/tests/test_mvp.py`, and `mobile/lib/features/mvp/`. The preserved copies under `experimental/` remain as source history until the restored paths are fully verified.

When this slice is reactivated, its controlled design is:

1. A mobile JWT user submits an exact concept code, label, or validated alias to `/api/mobile/mvp/{institution_id}/communication/resolve`.
2. The backend resolves only a validated `SignPlan` in that institution and returns ordered stable sign IDs plus deterministic clip keys (`sign:<stable_sign_id>`).
3. A practice activity references validated vocabulary and accepts a controlled result (`correct`, `incorrect`, or `unknown`) from the synthetic scaffold seam.
4. An institution administrator creates a cohort, assigns validated plans/activities, and manages its participant roster in `/portal`; Flutter participants continue using the existing self-enrollment route, while administrators and vocabulary reviewers read safe roster status and aggregate synthetic progress.

### MVP limitations

- Communication is intent/alias based; it is not free translation and uses no LLM or grammar engine.
- Practice is a synthetic ONNX scaffold. `UNKNOWN` is preserved when confidence is insufficient; no accuracy, clinical, or educational efficacy claim is made.
- Flutter does not capture camera input or run on-device inference yet. Playback is abstracted and reports assets unavailable because no real GLB clips are bundled.
- Raw video is not stored by default. Consent is checked for practice attempts and pilot report eligibility.
- Portal progress and controlled CSV export are aggregate/synthetic MVP reports only: enrollment, active participants, completion, attempts, result counts, `UNKNOWN` rate, latency p50/p95, and safe operational rows. Advanced analytics, raw media, raw attempt payloads, passwords, tokens, and unrestricted event data are not implemented or exported.
- No camera recognition, real avatar assets, or real LSB dataset are included. Continuous recognition, gamification, real ML data, and store distribution are out of scope for this MVP.

Billing slice: individual Free/Plus and institution-scoped Enterprise subscriptions use Stripe test-mode hosted Checkout. The backend creates Checkout Sessions, verifies raw-body webhook signatures, finalizes event IDs only after successful handling, aggregates valid subscriptions, and grants/revokes entitlements only from verified Stripe subscription objects. Flutter receives only an authenticated backend session, opens the returned hosted URL, and refreshes status from the backend; it never stores Stripe secrets or declares payment complete. Configure only test placeholders in `.env` (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, price IDs, and success/cancel URLs). Localhost URLs and debug settings are development-only; production must set explicit non-development values and real secrets outside this repository. Exercise with mocked tests; never use live Stripe credentials here. Hosted Checkout remains the Android MVP flow; if Android is later distributed through Google Play, migrate Plus billing to Play Billing rather than adding a native Stripe SDK.
