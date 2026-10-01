# DualSign Mobile

Flutter Android learner app for Free, Plus, and enterprise-provisioned access.

The active MVP workspace is a configured synthetic/manual pilot slice. The normal Android path is interactive email/password login or registration against `/api/mobile/token` and `/api/mobile/register`; access and refresh tokens are persisted with Android secure storage, never the password. Configure `DUALSIGN_API_BASE_URL`; after authentication, memberships come from `/api/mobile/me` and cohorts come from `/api/mobile/mvp/{institution_id}/pilots/cohorts`. The app lets the user select an institution and active cohort, and creates scoped repositories only after both values are returned by the server. Institution administrators create cohorts and manage participant rosters in `/portal`; Flutter continues consuming the assigned/enrolled cohorts and existing self-enrollment flow. `/backoffice` remains for DualSign operations. `DUALSIGN_INSTITUTION_ID` and `DUALSIGN_COHORT_ID` remain optional development defaults only and are validated against server data. Without a membership, institution, or cohort, the app shows an explicit state and never renders MVP data. Stripe is unrelated and unchanged.

Registration creates a personal account only. Institution membership and enterprise access are granted separately by authorized flows; registration does not create either. Password reset, SSO, domain validation, and Play Billing are not implemented or claimed.

## Android auth in Docker

Run the Flutter checks without installing Flutter on the host:

```powershell
$repo = (Get-Location).Path
docker run --rm --mount "type=bind,source=$repo\mobile,target=/workspace" --workdir /workspace ghcr.io/cirruslabs/flutter:stable flutter pub get
docker run --rm --mount "type=bind,source=$repo\mobile,target=/workspace" --workdir /workspace ghcr.io/cirruslabs/flutter:stable flutter analyze
docker run --rm --mount "type=bind,source=$repo\mobile,target=/workspace" --workdir /workspace ghcr.io/cirruslabs/flutter:stable flutter test
```

For an Android emulator pointed at the local Compose gateway, use `--dart-define=DUALSIGN_API_BASE_URL=http://10.0.2.2:8080/api/`. The institution and cohort defines are optional development defaults; server-backed cohort listing is the source of truth. The auth tests use fake HTTP and storage implementations, not live credentials.

Practice lets a person submit explicit synthetic/manual `correct`, `incorrect`, or `unknown` results and displays the server result, latency, and model version. Reports display aggregate participants, completion, result counts, and latency; enrollment uses the existing self-enrollment endpoint. Communication displays controlled resolution results and `clip_key`; playback is explicitly unavailable when `asset_available` is false. There is no camera recognition, real ML accuracy claim, real avatar asset, WebView integration, advanced analytics, or real LSB dataset. Stripe remains a separate completed backend capability and is not changed by this slice.
