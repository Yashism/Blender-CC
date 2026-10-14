// Line-up of 12 varied people under neutral light from a high CCTV-like angle.
// T = 0: standing idle. T = 1: mid-walk (different phases). T = 2: same as 1 seen from behind.
import * as THREE from 'three';
import { makeRenderer, neutralScene, makeCast, describe } from './humans_testkit.js';

const { renderer, W, H } = makeRenderer();
const scene = neutralScene();
const cam = new THREE.PerspectiveCamera(42, W / H, 0.1, 100);
const people = makeCast();
people.forEach((h, i) => {
  const row = i < 6 ? 0 : 1;
  const col = i % 6;
  h.object.position.set((col - 2.5) * 0.95, 0, row ? -0.9 : 0.55);
  scene.add(h.object);
});
console.warn(people.map(describe).join('\n'));
window.__ready = Promise.resolve();
window.__renderAt = async (T) => {
  const walk = T >= 1;
  people.forEach((h, i) => {
    h.object.rotation.y = T >= 2 ? Math.PI : 0;
    h.setPose(walk ? 0.13 * i + 0.1 : 0, walk ? 1.3 : 0, 0, 3 + i);
  });
  if (T >= 3) { cam.position.set(0, 1.5, 5.2); cam.lookAt(0, 0.85, 0); }
  else { cam.position.set(0, 3.9, 4.4); cam.lookAt(0, 0.55, -0.15); }
  renderer.render(scene, cam);
};
