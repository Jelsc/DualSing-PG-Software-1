import { Engine, type AbstractEngine, type Scene } from "@babylonjs/core";
import { Scene as BabylonScene } from "@babylonjs/core/scene.js";
import { LoadAssetContainerAsync } from "@babylonjs/core/Loading/sceneLoader.js";
import type { AssetContainer } from "@babylonjs/core/assetContainer.js";
import type { AnimationGroup } from "@babylonjs/core/Animations/animationGroup.js";
import "@babylonjs/loaders/glTF/index.js";

export interface PlayOptions {
  loop?: boolean;
  speedRatio?: number;
}

export interface SequenceOptions {
  /**
   * Maximum time to wait for a clip to finish before advancing. The default
   * waits for the clip's natural end; zero advances immediately after start.
   */
  clipTimeoutMs?: number;
}

/** Owns one Babylon scene and one loaded glTF/GLB asset container. */
export class AvatarEngine {
  readonly scene: Scene;
  private container: AssetContainer | undefined;
  private groups = new Map<string, AnimationGroup>();
  private activeGroup: AnimationGroup | undefined;
  private sequenceCancel: (() => void) | undefined;
  private sequenceId = 0;
  private readonly observerCleanup = new Set<() => void>();
  private disposed = false;

  constructor(
    private readonly engine: AbstractEngine,
    scene?: Scene,
  ) {
    this.scene = scene ?? new BabylonScene(engine);
  }

  /** Load one glTF/GLB from a URL or browser-relative path. */
  async load(assetUrl: string): Promise<readonly string[]> {
    this.assertUsable();
    if (!assetUrl.trim()) throw new Error("An avatar asset URL is required.");

    const loaded = await LoadAssetContainerAsync(assetUrl, this.scene);
    if (this.disposed) {
      loaded.dispose();
      throw new Error("AvatarEngine was disposed while the asset was loading.");
    }

    this.stop();
    this.container?.dispose();
    loaded.addAllToScene();
    this.container = loaded;
    this.groups = new Map(
      loaded.animationGroups.map((group) => [group.name, group]),
    );
    return [...this.groups.keys()];
  }

  get clipNames(): readonly string[] {
    return [...this.groups.keys()];
  }

  get activeClipName(): string | undefined {
    return this.activeGroup?.name;
  }

  /** Start one named clip. A missing name throws with available clip names. */
  play(name: string, options: PlayOptions = {}): void {
    this.assertUsable();
    const group = this.requireGroup(name);
    this.stop();
    group.start(
      options.loop ?? false,
      options.speedRatio ?? 1,
      group.from,
      group.to,
    );
    this.activeGroup = group;
  }

  /** Play clips in order, advancing on natural completion or an optional timeout. */
  async playSequence(
    names: readonly string[],
    options: SequenceOptions = {},
  ): Promise<void> {
    this.assertUsable();
    // Validate the complete caller-supplied sequence before starting any clip.
    for (const name of names) this.requireGroup(name);
    this.stop();
    const sequenceId = this.sequenceId;

    for (const name of names) {
      this.assertUsable();
      const group = this.requireGroup(name);
      group.start(false, 1, group.from, group.to);
      this.activeGroup = group;
      await this.waitForClip(group, options.clipTimeoutMs);
      if (this.disposed || sequenceId !== this.sequenceId) return;
    }
    this.activeGroup = undefined;
  }

  /** Stop playback and any pending sequence wait. */
  stop(): void {
    this.sequenceId++;
    this.sequenceCancel?.();
    this.sequenceCancel = undefined;
    this.activeGroup?.stop();
    this.activeGroup = undefined;
  }

  /** Register a scene render observer and receive an idempotent unsubscribe. */
  observeBeforeRender(observer: () => void): () => void {
    this.assertUsable();
    const token = this.scene.onBeforeRenderObservable.add(observer);
    const unsubscribe = () => {
      this.scene.onBeforeRenderObservable.remove(token);
      this.observerCleanup.delete(unsubscribe);
    };
    this.observerCleanup.add(unsubscribe);
    return unsubscribe;
  }

  /** Let the host drive rendering in its own browser/WebView lifecycle. */
  render(): void {
    this.assertUsable();
    this.scene.render();
  }

  /** Notify Babylon after the host canvas changes size. */
  resize(): void {
    this.assertUsable();
    this.engine.resize();
  }

  /** Dispose observers, playback, imported assets, scene, and engine once. */
  dispose(): void {
    if (this.disposed) return;
    this.disposed = true;
    this.sequenceCancel?.();
    this.sequenceCancel = undefined;
    this.activeGroup?.stop();
    this.activeGroup = undefined;
    for (const cleanup of [...this.observerCleanup]) cleanup();
    this.container?.dispose();
    this.container = undefined;
    this.groups.clear();
    this.scene.dispose();
    this.engine.dispose();
  }

  private waitForClip(
    group: AnimationGroup,
    timeoutMs?: number,
  ): Promise<void> {
    return new Promise((resolve) => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      const observer = group.onAnimationEndObservable.add(() => finish());
      const finish = () => {
        if (timer !== undefined) clearTimeout(timer);
        group.onAnimationEndObservable.remove(observer);
        if (this.sequenceCancel === cancel) this.sequenceCancel = undefined;
        resolve();
      };
      const cancel = () => {
        group.onAnimationEndObservable.remove(observer);
        if (timer !== undefined) clearTimeout(timer);
        resolve();
      };
      this.sequenceCancel = cancel;
      if (timeoutMs !== undefined) {
        timer = setTimeout(
          () => {
            group.stop();
            finish();
          },
          Math.max(0, timeoutMs),
        );
      }
    });
  }

  private requireGroup(name: string): AnimationGroup {
    const group = this.groups.get(name);
    if (!group) {
      const available = this.clipNames;
      throw new Error(
        `Avatar clip "${name}" is unavailable. Available clips: ${available.length ? available.join(", ") : "none"}.`,
      );
    }
    return group;
  }

  private assertUsable(): void {
    if (this.disposed) throw new Error("AvatarEngine has been disposed.");
  }
}

/** Create a browser/WebView WebGL engine for the host-provided canvas. */
export function createBrowserAvatarEngine(
  canvas: HTMLCanvasElement,
  options: ConstructorParameters<typeof Engine>[2] = {},
): AvatarEngine {
  const engine = new Engine(canvas, true, options);
  return new AvatarEngine(engine);
}
