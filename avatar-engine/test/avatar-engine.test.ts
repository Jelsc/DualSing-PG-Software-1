import assert from "node:assert/strict";
import test from "node:test";
import { Animation } from "@babylonjs/core/Animations/animation.js";
import { AnimationGroup } from "@babylonjs/core/Animations/animationGroup.js";
import { NullEngine } from "@babylonjs/core/Engines/nullEngine.js";
import { TransformNode } from "@babylonjs/core/Meshes/transformNode.js";
import { Scene } from "@babylonjs/core/scene.js";
import { AvatarEngine } from "../src/index.js";

function makeFixtureClip(scene: Scene, name: string): AnimationGroup {
  // Synthetic test fixture only; this does not represent a sign or real avatar.
  const target = new TransformNode(`${name}-test-target`, scene);
  const animation = new Animation(
    `${name}-test-animation`,
    "position.x",
    1,
    Animation.ANIMATIONTYPE_FLOAT,
    Animation.ANIMATIONLOOPMODE_CONSTANT,
  );
  animation.setKeys([
    { frame: 0, value: 0 },
    { frame: 1, value: 1 },
  ]);
  const group = new AnimationGroup(name, scene);
  group.addTargetedAnimation(animation, target);
  return group;
}

function createFixture(): { avatar: AvatarEngine; engine: NullEngine } {
  const engine = new NullEngine();
  const scene = new Scene(engine);
  const avatar = new AvatarEngine(engine, scene);
  makeFixtureClip(scene, "clip-a");
  makeFixtureClip(scene, "clip-b");
  // Fixture registration stands in for clip groups returned by a loaded asset.
  (avatar as unknown as { groups: Map<string, AnimationGroup> }).groups =
    new Map(scene.animationGroups.map((group) => [group.name, group]));
  return { avatar, engine };
}

test("starts a named clip and rejects unavailable clips with choices", () => {
  const { avatar } = createFixture();
  avatar.play("clip-a", { loop: true });
  assert.equal(avatar.activeClipName, "clip-a");
  assert.throws(
    () => avatar.play("missing"),
    /Available clips: clip-a, clip-b/,
  );
  avatar.dispose();
});

test("validates a complete sequence before starting its first clip", async () => {
  const { avatar } = createFixture();
  await assert.rejects(
    avatar.playSequence(["clip-a", "missing"]),
    /Avatar clip "missing" is unavailable/,
  );
  assert.equal(avatar.activeClipName, undefined);
  avatar.dispose();
});

test("sequences clips in order when each fixture group completes", async () => {
  const { avatar } = createFixture();
  const sequence = avatar.playSequence(["clip-a", "clip-b"]);
  assert.equal(avatar.activeClipName, "clip-a");
  avatar.scene.animationGroups[0]!.onAnimationEndObservable.notifyObservers(
    avatar.scene.animationGroups[0]!.targetedAnimations[0]!,
  );
  await Promise.resolve();
  assert.equal(avatar.activeClipName, "clip-b");
  avatar.scene.animationGroups[1]!.onAnimationEndObservable.notifyObservers(
    avatar.scene.animationGroups[1]!.targetedAnimations[0]!,
  );
  await sequence;
  assert.equal(avatar.activeClipName, undefined);
  avatar.dispose();
});

test("stop and dispose clear sequence waits and render observers idempotently", async () => {
  const { avatar } = createFixture();
  let observed = 0;
  avatar.observeBeforeRender(() => observed++);
  avatar.scene.onBeforeRenderObservable.notifyObservers(avatar.scene);
  assert.equal(observed, 1);

  const pending = avatar.playSequence(["clip-a", "clip-b"]);
  avatar.stop();
  await pending;
  assert.equal(avatar.activeClipName, undefined);
  avatar.dispose();
  avatar.dispose();
  assert.throws(() => avatar.render(), /disposed/);
});
