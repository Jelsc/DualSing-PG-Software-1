# DualSign Avatar Engine

An isolated TypeScript runtime boundary for loading a glTF/GLB avatar and playing its named Babylon.js animation groups. It can be embedded by a browser host or a Flutter WebView; it does not interpret language, SignPlan responses, or sign meaning.

## Quick path

From the repository root, generate the lockfile and run all checks in Docker:

```powershell
docker run --rm --mount "type=bind,source=$((Resolve-Path .\avatar-engine).Path),target=/workspace" -w /workspace node:22.14.0-bookworm-slim npm install --package-lock-only --ignore-scripts
docker build --tag dualsign-avatar-engine:phase5 .\avatar-engine
```

The image build installs from `package-lock.json`, then runs formatting verification, TypeScript compilation, and the NullEngine tests. It publishes no ports and does not interact with the repository Compose stack. The generated lockfile is part of this package.

## Runtime contract

```ts
import { createBrowserAvatarEngine } from "@dualsign/avatar-engine";

const avatar = createBrowserAvatarEngine(canvas);
const clipNames = await avatar.load("/assets/avatar.glb");
avatar.play("Idle", { loop: true });

// A caller-provided, ordered clip list. Each clip completes before the next starts.
await avatar.playSequence(["clip-a", "clip-b"]);

avatar.resize(); // after the host resizes its canvas
avatar.dispose(); // when the host view is torn down
```

| Boundary           | Contract                                                                                                                                                                                                                                                                                                                                                            |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Asset loading      | Uses Babylon's glTF loader with `LoadAssetContainerAsync`; returns imported animation-group names. A subsequent successful load replaces and disposes the previous asset container.                                                                                                                                                                                 |
| Clip selection     | `play(name)` selects an exact, case-sensitive imported group name. Unknown names throw an error listing available clips.                                                                                                                                                                                                                                            |
| Sequence           | `playSequence(names)` validates every name before playback, then advances in order when each non-looping group ends. `clipTimeoutMs` optionally stops a clip and advances after the supplied limit. Transitions are hard cuts at clip boundaries; no blending is implied.                                                                                           |
| Host lifecycle     | The host owns the canvas, creates/assigns a camera before rendering, and drives `render()` (or uses the exposed Babylon scene with its render loop); call `resize()` after canvas size changes and `dispose()` exactly when the view is torn down. Disposal is idempotent and stops playback, removes registered observers, and disposes assets, scene, and engine. |
| Observer lifecycle | `observeBeforeRender()` returns an unsubscribe function. The function is safe to call repeatedly, and all remaining observers are removed by `dispose()`.                                                                                                                                                                                                           |

`AvatarEngine` can also be constructed with a Babylon engine and scene for hosts with a custom engine setup. The engine and scene are owned by the instance and disposed with it.

## Integration boundary

The future Next.js browser component or Flutter WebView adapter supplies the canvas, asset URL, clip names, and ordered playback requests. Backend response models, language parsing, SignPlan validation, real sign-to-clip mappings, and avatar asset authoring stay outside this package. Callers must only pass clip names that exist in the selected asset; failures are explicit rather than silently substituting another motion.

The tests use synthetic `clip-a` and `clip-b` AnimationGroups with Babylon `NullEngine`. These are test fixtures only: they are not avatar data, authored LSB animations, real sign mappings, or evidence of linguistic correctness. Animation sequencing does not solve LSB coarticulation or linguistic validation.

## Verification scope

The Docker checks exercise compilation, formatting, clip selection, sequence ordering, missing-clip rejection, and disposal under `NullEngine`. Browser/WebGL rendering and Flutter WebView embedding are not exercised in this headless test harness and remain unverified.
