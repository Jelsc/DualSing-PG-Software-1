# DualSign non-billing requirements status

The proven access, session-expiry, cohort-selection, practice-authoring, and editor gaps are repaired in the main worktree. This is a bounded requirements check, not certification of every device or unfinished product surface.

Basis: the current request, agreed Case C memory #2006 (original project key `proyecto-grupal-sw1`), controlled-reporting memory #2055, current source, and the [verification receipt](nonbilling-verification.md). Earlier memory predates the present billing implementation; the current instruction freezes billing.

## Requirement matrix

| Requirement | Status | Evidence / boundary |
|---|---|---|
| Personal Free/Plus alongside institutional access | Implemented foundation; repaired access | Personal registration does not create membership. Authenticated users can reach Profile/logout and an honest personal home. Entitlement behavior is unchanged. |
| Separate internal backoffice and institution portal | Repaired | Backoffice now has direct session/CSRF login, denied-account sign-out, and access-check retry. Existing staff boundary remains authoritative. |
| Full backoffice operations | Placeholder; needs product decision | Institutions, users/memberships, content operations, and audit cards do not claim implemented CRUD. Password-reset service is not invented. |
| Mobile JWT expiry during feature use | Repaired | Shared non-billing transport for cohort, communication, practice, report, enrollment, and consent requests; single-flight refresh, persisted rotation, one 401 retry, API-origin/path restriction, no credential-bearing redirects, logout generation guard. Network failure preserves credentials. |
| First cohort creation | Repaired | Empty institution can open and submit the form; assignment and roster panels reload after cohort writes. |
| Tenant/cohort switching | Repaired | Institution-keyed panels discard previous state; assignment, roster, detail, and catalog responses are guarded. One-membership mobile users can switch cohorts. Feature screens remount on repository changes. Panels retain independently labeled cohort selectors. |
| Practice selection and consent | Repaired | Activity selector replaces first-row-only UI. Explicit grant/withdraw uses `/mobile/consents`, `pilot_practice`, `v1`, and the existing append-only contract. A grant is never sent on load or activity selection. |
| Empty-institution practice authoring | Implemented | Admin-only CSRF-protected `POST /portal/{institution_id}/activities` accepts validated same-tenant plan/sign IDs and writes an audit record atomically. Existing consent-required and synthetic model/schema defaults are retained. |
| Plan variants and accessible workbench | Repaired | Plan editor fetches variants independently of visiting Signs; loading/error prevent silent submission without variant data. Search focus is visible, navigation exposes `aria-current`, report uses a native table, narrow navigation wraps. |
| Controlled communication and manual evaluation | Implemented scaffold | Existing vocabulary resolution and manual/synthetic results remain explicit. Practice listing is institution-scoped under the current API, not newly restricted to a selected cohort. |
| Personal catalog and Plus learning content | Needs product decision | No approved catalog, content source, paid lesson definition, or learning progression is supplied. No invented lessons. |
| Learner access to aggregate cohort reports | Needs product decision | Existing member-accessible mobile report policy is preserved; portal reporting remains role-restricted. Decide learner visibility explicitly. |
| Participant reactivation | Needs product decision | Existing self-enrollment can reactivate inactive participation. No new reactivation policy was introduced. |
| Production consent policy and real-data collection | Needs product decision | The UI exposes the existing MVP `v1` manual-result contract; it is not a newly approved legal policy for future camera/media collection. Existing consent cannot be queried by this API; the checkbox starts unconfirmed and withdrawal is available after confirmation in the current screen. |
| Avatar playback / ML recognition | Needs real assets | Scaffold contracts do not provide real clips, capture data, trained production models, or device inference validation. |

## Verification boundaries

- Docker: 43 non-billing backend tests, migration checks/application, 27 Flutter unit/widget tests, frontend lint/typecheck/build, and six real Chromium interaction tests.
- Visual inspection: mocked-data web screenshots at 1440×1000 and 390×844; forms, navigation, wrapping, and focus inspected. No live database was seeded.
- Native/device: not validated; no emulator was launched. Secure storage, lifecycle, native networking, and platform-specific rendering still need device testing.
- Full backend run: 52 of the original 53 tests passed. Frozen billing test `test_verified_event_is_idempotent_and_activates_plus` returned HTTP 500 rather than 200. Billing source was not changed to address it.
- Stripe remains frozen; SSO remains excluded. No real payments, asset claims, or production credentials were introduced.

## Review units

| Unit | Review / rollback boundary | Verification |
|---|---|---|
| Session and personal access | Mobile auth/bootstrap/transport/provider and workspace access hunks, with transport and widget regressions | Flutter tests; native runtime still pending |
| Cohort/editor/backoffice usability | Portal/backoffice/CSS scope, form, variant, and semantic-table hunks; browser regressions | Chromium interactions and screenshots; Next build/lint/types |
| Manual practice and authoring | Practice selector/consent wiring, activity endpoint/schema/component and authoring tests | Backend role/tenant/CSRF/audit tests, Flutter interaction, browser authoring |

These are uncommitted review units. Roll back only their scoped hunks against the source snapshot; do not replace unrelated worktree contents. The parent owns any later native/adversarial review transaction.
