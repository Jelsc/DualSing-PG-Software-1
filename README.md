# DualSign IA

Phase 2 builds on the Phase 0 local-development foundation and Phase 1 identity layer with a tenant-scoped LSB vocabulary catalog and a provisional, renderer-independent SignPlan API. Product learning and communication workflows remain out of scope.

## Quick Start

1. Create `.env` from `.env.example` only if a local `.env` does not already exist:

   ```powershell
   if (-not (Test-Path .env)) { Copy-Item .env.example .env }
   ```

2. Build and start the local services:

   ```powershell
   docker compose up --build
   ```

3. Open the admin shell at <http://127.0.0.1:8080>. The API health endpoint is <http://127.0.0.1:8080/api/health>.

Stop the services with `docker compose down`. Named data volumes are retained unless explicitly removed with `docker compose down -v`.

## Service Map

| Service | Purpose | Local address |
| --- | --- | --- |
| Nginx | Public local entry point; routes `/` to Next.js and `/api/` to Django | `127.0.0.1:8080` |
| Frontend | Next.js administrative shell | Routed through Nginx |
| Backend | Django + Django Ninja health API | Routed through Nginx |
| PostgreSQL | Development database | `127.0.0.1:5432` |
| Redis | Celery broker and development cache | `127.0.0.1:6379` |
| Celery worker | Background worker process | Internal Compose network |
| MinIO | Local object-storage service and console | `127.0.0.1:9000`, `127.0.0.1:9001` |

Only Nginx is the public web entry point. The frontend uses the same-origin API base `/api`; container hostnames are not exposed to the browser.

## Mobile Development

Flutter runs on the host against an emulator or device; it is not a Compose service and this scaffold does not include a web target.

```powershell
cd mobile
flutter test
flutter run
```

## Environment and Deployment

`.env.example` contains development-only placeholders. `.env` is local and ignored by Git; replace placeholders for local use, and never put real credentials in the example file.

**The Compose images, credentials, and debug settings are for local development only. They are not production deployment configuration.**

## Backend identity and vocabulary (Phases 1–2)

The browser authenticates through Django sessions and CSRF-protected same-origin requests. Flutter uses short-lived access JWTs and rotating, revocable refresh JWTs. Institution roles and access are resolved from live active memberships; platform administrators are Django staff superusers. A user's active memberships and route policies are described in [`backend/README.md`](backend/README.md).

Compose applies database migrations before starting the backend. Phase 2 provides session + CSRF-protected vocabulary management APIs and read-only JWT catalog endpoints for mobile; it does not include the Phase 3 admin UI, translation, grammar, or rendering. See [`backend/README.md`](backend/README.md) for lifecycle, role matrix, API payloads, and Docker checks. Run backend checks with `docker compose exec -T backend python manage.py test` and `docker compose exec -T backend python manage.py makemigrations --check --dry-run`. No public signup or user-management/admin UI is included.
