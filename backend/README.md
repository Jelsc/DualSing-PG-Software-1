# Backend identity and vocabulary API

Phase 1 supplies identity, institution membership, tenant authorization, consent history, and append-only audit events. Phase 2 adds a bounded LSB vocabulary catalog and an internal SignPlan representation. It does not supply a renderer, language grammar, or translation service.

## Quick path

1. Compose applies migrations when the backend starts. For an already-running stack, run `docker compose exec -T backend python manage.py migrate`.
2. A web vocabulary manager signs in through `/api/web/login`, keeps the session cookie, fetches `/api/web/csrf`, and sends `X-CSRFToken` on every vocabulary write.
3. Vocabulary endpoints live under `/api/vocabulary/{institution_id}`; Flutter read-only endpoints use `/api/mobile/vocabulary/{institution_id}` with a bearer access JWT.

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

A plan can be published only when it has at least one item, its concept belongs to the same institution, every referenced sign is validated, optional variants belong to the referenced signs, and all marker positions are within the ordered sequence. Plans with cross-institution references are rejected by both the API and PostgreSQL composite foreign keys. Catalog codes, alias normalization, and per-plan ordering have database constraints.

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

## Audit and future boundaries

Catalog create/edit/delete and lifecycle actions append `AuditRecord` events with actor, institution, subject ID, and status only. No credentials, token values, marker payloads, aliases, video, conversation text, or unnecessary personal data are logged. Phase 2 does not include the Phase 3 admin UI, free-text translation/LLM, grammar/transliteration, datasets, renderer integration, Babylon, GLB, Unity, video, or animation clips.

## Docker checks

```powershell
docker compose config -q
docker compose exec -T backend python manage.py migrate --noinput
docker compose exec -T backend python manage.py test
docker compose exec -T backend python manage.py makemigrations --check --dry-run
```

The backend uses Django Ninja with the Phase 1 hybrid auth setup. Audit and consent records are append-only application records; consent history does not replace legal review.
