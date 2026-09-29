# Backend identity foundation

Phase 1 provides identity, institution membership, consent history, security audit events, and the health endpoint. It does not include courses, curriculum, SignPlan, sign-language content, avatar, datasets/ML, signup, or an admin UI. Consent records support traceability; they do not replace legal review.

## Local migration and tests

Compose runs `python manage.py migrate --noinput` before starting Django. For a one-off local migration or test run:

```powershell
docker compose exec -T backend python manage.py migrate
docker compose exec -T backend python manage.py test
docker compose exec -T backend python manage.py makemigrations --check --dry-run
```

## Authentication and tenant policy

| Client | Flow | API routes |
| --- | --- | --- |
| Next.js browser | Django server-side session; fetch `/api/web/csrf`, then send `X-CSRFToken` for login/logout and other cookie-authenticated writes. Same-origin Nginx routing keeps session cookies first-party. | `/api/web/login`, `/api/web/logout`, `/api/web/me` |
| Flutter | Email/password issues a 5-minute access token and 7-day refresh token. Refresh rotates and blacklists the old refresh token; revoke blacklists the supplied refresh token. | `/api/mobile/token`, `/api/mobile/token/refresh`, `/api/mobile/token/revoke`, `/api/mobile/me` |

Institution membership and role are loaded from the database for every protected request; JWTs carry no tenant or role authorization. Active members can list and view their institutions. Only active Django staff superusers are platform administrators and can see all active institutions or create one. Cross-tenant detail requests return 404. The three membership roles are institution administrator, operator, and vocabulary reviewer.

Audit and consent records are append-only application records. Keep audit metadata free of credentials, tokens, passwords, conversation bodies, and unnecessary personal data. Local development uses non-secure cookies; `DEBUG=false` enables secure session and CSRF cookies. Production must supply its own secret key and HTTPS/reverse-proxy configuration.
