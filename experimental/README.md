# Experimental Features

This directory contains preserved MVP slices that are not part of the active DualSign web or mobile runtime.

| Path | Future scope | Current state |
| --- | --- | --- |
| `backend_mvp/` | Communication, Practice, and Pilot reports | Not in Django `INSTALLED_APPS`; routes and tests are not active |
| `mobile_mvp/` | Flutter repositories and screens for the same slice | Not imported by the current Flutter shell |

The active backend intentionally has no `mvp` app or `/api/mobile/mvp` route. React and Flutter surfaces must continue to use backend authorization and tenant checks; this directory is not a bypass. Reactivation is a separate product decision and must restore the app registration, migration context, API mount, and focused tests together.
