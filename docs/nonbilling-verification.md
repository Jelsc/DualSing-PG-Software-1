# Non-billing verification receipt

All application checks below ran in Docker before the interruption. On resume, source changes and screenshots were intact and `git diff --check` passed, but Docker Desktop's `dockerDesktopLinuxEngine` pipe was unavailable: tests could not be rerun and container state could not be rechecked. Git inspection and native CLI availability/help checks ran on the host. No host test suite or emulator was used; no application source was changed after the recorded successful checks.

## Results

| Command inside isolated container | Result |
|---|---|
| `python manage.py test tests.test_accounts tests.test_mvp tests.test_vocabulary tests.test_health mvp.test_authoring --noinput` | 43 passed, including five new authoring tests |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py migrate --noinput` | All migrations applied to disposable PostgreSQL 17.6 |
| `python manage.py test --noinput` (before new authoring tests) | 52 passed / 1 frozen billing failure; HTTP 500 in verified-event activation test |
| `flutter test` | 27 passed, including seven transport regressions and three new widget tests |
| `flutter analyze --no-fatal-infos` | Exit 0; 45 informational style/deprecation diagnostics, no warnings/errors |
| `npm run lint` | Passed |
| `npx tsc --noEmit` | Passed |
| `npm run build` | Passed; `/`, `/backoffice`, `/portal` generated |
| `node /tests/nonbilling.cjs` with Playwright 1.58.2 | Six Chromium interaction tests passed |
| `git diff --check` | Passed |
| `Get-Command gentle-ai`; `gentle-ai review start --help` | Available and help succeeds; no review transaction started |

Initial verification constraints: Flutter 3.41.4/Dart 3.11.1 cannot resolve the declared Dart `^3.11.5`; installed `ghcr.io/cirruslabs/flutter:stable` provides Flutter 3.44.0/Dart 3.12.0. SQLite cannot execute the PostgreSQL constraint migration. The working checks use that Flutter image and disposable PostgreSQL. Playwright image pull initially timed out and succeeded on retry. Next development-server checks required `localhost` rather than `127.0.0.1` for hydration resources.

## Reproduce without mutating source

PowerShell setup, from the repository root:

```powershell
$root = (Get-Location).Path
$evidence = 'C:\Users\nelso\AppData\Local\Temp\opencode'
```

Frontend check-only commands use the installed image dependencies and an isolated copy:

```powershell
docker run --rm --mount "type=bind,source=$root\frontend,target=/source,readonly" --entrypoint sh dualsign-frontend -c 'cp -a /source/app /app/ && npm run lint && npx tsc --noEmit && npm run build'
```

Flutter checks and format verification use a container-local copy. The source-mutating `dart format` pass was already completed on the ten changed Dart files before delivery. No frontend/Python formatter is configured for this repair.

```powershell
docker run --rm --mount "type=bind,source=$root\mobile,target=/source,readonly" --entrypoint bash ghcr.io/cirruslabs/flutter:stable -lc 'cp -a /source /tmp/mobile && cd /tmp/mobile && flutter pub get && dart format --output=none --set-exit-if-changed lib/app_session.dart lib/auth_service.dart lib/feature_http_client.dart lib/features/auth/auth_screens.dart lib/features/mvp/mvp_repositories.dart lib/features/mvp/mvp_screens.dart lib/features/workspace/workspace_screen.dart lib/features/workspace/workspace_state.dart test/feature_http_client_test.dart test/widget_test.dart && flutter test && flutter analyze --no-fatal-infos'
```

Backend checks require an isolated test database, not the application database:

```powershell
docker run --rm -d --name dualsign-nonbilling-db --tmpfs /var/lib/postgresql/data -e POSTGRES_PASSWORD=isolated-test-only -e POSTGRES_DB=dualsign_verify postgres:17.6-alpine3.22
docker exec dualsign-nonbilling-db pg_isready -U postgres
docker run --rm --network container:dualsign-nonbilling-db --mount "type=bind,source=$root\backend,target=/app,readonly" -e POSTGRES_HOST=127.0.0.1 -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=isolated-test-only -e POSTGRES_DB=dualsign_verify -e DJANGO_SECRET_KEY=isolated-test-only-key-at-least-32-bytes --entrypoint sh dualsign-backend -c 'python manage.py test tests.test_accounts tests.test_mvp tests.test_vocabulary tests.test_health mvp.test_authoring --noinput && python manage.py makemigrations --check --dry-run && python manage.py migrate --noinput'
```

Browser tests run against an isolated frontend with every `/api/**` request mocked. No backend credentials or live seed data are used. Wait for the frontend to report readiness before the browser command:

```powershell
docker run --rm -d --name dualsign-nonbilling-web --mount "type=bind,source=$root\frontend,target=/source,readonly" --entrypoint sh dualsign-frontend -c 'cp -a /source/app /app/ && npm run build && npm run start -- --hostname 0.0.0.0'
docker logs dualsign-nonbilling-web
docker run --rm --network container:dualsign-nonbilling-web --mount "type=bind,source=$root\frontend\tests,target=/tests,readonly" --mount "type=bind,source=$evidence,target=/evidence" -e NODE_PATH=/tmp/browser/node_modules mcr.microsoft.com/playwright:v1.58.2-noble sh -c 'npm install --prefix /tmp/browser playwright@1.58.2 && node /tests/nonbilling.cjs'
```

Only the two disposable verification containers above may be stopped afterward. The original seven DualSign containers were stopped at entry; none was restarted. No Compose teardown or volume deletion was performed. The disposable containers were not stopped before interruption; their current state is unknown while Docker is unavailable. Check for existing names before rerunning the setup commands.

## Evidence and provenance

Local evidence directory: `C:\Users\nelso\AppData\Local\Temp\opencode`.

- `nonbilling-before.tar`: pre-edit bytes for `frontend/app`, frontend package/lock files, `mobile/lib`, `mobile/test`, and `backend/mvp`.
- `nonbilling-before.json`: 47 scoped entries with path, existence, SHA-256 and filesystem mode; records `docs` as absent. `nonbilling-after.json` records all 20 changed paths, checkpoint hashes/modes, and snapshot-diff counts. This verification document was subsequently updated; its after-hash is stale and manifest regeneration remains pending Docker availability. New files are additions to those scopes, plus `frontend/tests` and `docs`.
- Starting Git state: clean main at `2af218e`; tracked scoped file modes were `100644`. `.env`, `.atl`, experimental packages and sibling worktrees were not edited.
- `screenshots/portal-desktop.png`, `screenshots/portal-mobile.png`, `screenshots/backoffice-desktop.png`, `screenshots/backoffice-mobile.png`: final production-build Chromium captures with mocked APIs, visually inspected at 1440×1000 and 390×844. No form/navigation overlap was observed; narrow navigation wraps. These are not native/mobile-device captures.
- Review forecast: 800–1,200 authored changed lines. Actual: **1,585 lines (1,418 additions + 167 deletions), 20 files**, using Git tracked diff plus new-file line counts. The byte-snapshot manifest uses Python sequence matching and reports 1,587 because its workspace-screen alignment differs by one addition/deletion. The overrun comes from added authoring coverage, browser/transport regressions, documentation, and formatting the touched Dart files.

## Skill resolution

All three exact requested files were read before repository work; no fallback skill or delegated agent was used:

1. `C:\Users\nelso\.agents\skills\interface-design\SKILL.md`
2. `C:\Users\nelso\.config\opencode\skills\cognitive-doc-design\SKILL.md`
3. `C:\Users\nelso\.config\opencode\skills\work-unit-commits\SKILL.md`

Native review is feasible at the CLI interface level: `gentle-ai` resolves and `review start --help` describes the supported workspace projection. Execution and any adversarial review remain owned by the parent; feasibility is not a completed review verdict.
