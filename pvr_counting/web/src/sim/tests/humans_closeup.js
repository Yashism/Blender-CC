// Close-up turnaround of a few people (front, 3/4, side, back) at eye level + one high-angle row.
// T selects the subject set: T = 0..3 -> people from the cast; T >= 10 -> untextured (clay) of person T-10.
import * as THREE from 'three';
import { makeRenderer, neutralScene, CAST } from './humans_testkit.js';
import { createHuman } from '../humans.js';

const { renderer, W, H } = makeRenderer();
const scene = neutralScene({ bg: 0x9a9da0 });
const cam = new THREE.PerspectiveCamera(30, W / H, 0.1, 100);
let current = [];
const clay = new THREE.MeshStandardMaterial({ color: 0xb8b2aa, roughness: 0.7 });
window.__ready = Promise.resolve();
window.__renderAt = async (T) => {
  for (const h of current) h.dispose();
  current = [];
  const isClay = T >= 10 && T < 20;
  const idx = T >= 60 ? T - 60 : T >= 40 ? T - 40 : T >= 20 ? T - 20 : isClay ? T - 10 : T;
  const extra = [[201, { kind: 'adult', sex: 'f', carry: null }], [202, { kind: 'adult', sex: 'm', carry: null }], [203, { kind: 'adult', sex: 'f', carry: 'bag' }], [204, { kind: 'child', sex: 'm', carry: 'popcorn' }], [502, { kind: 'adult', sex: 'f', carry: null }], [401, { kind: 'adult', sex: 'm', carry: null }]];
  const all = CAST.concat(extra);
  const [seed, o] = all[idx % all.length];
  const angles = [0, 0.7, Math.PI / 2, Math.PI];
  angles.forEach((a, i) => {
    const h = createHuman(seed, o);
    if (isClay) h.mesh.material = clay;
    h.object.position.set((i - 1.5) * 0.85, 0, 0);
    h.object.rotation.y = a;
    h.setPose(i === 3 ? 0.3 : 0, i === 3 ? 1.3 : 0, 0, 4);
    scene.add(h.object);
    current.push(h);
  });
  if (T >= 60) {
    // heads from above, close
    current.forEach((h, i) => { h.object.rotation.y = [0, Math.PI, 0.6, -2.4][i]; h.object.position.set((i - 1.5) * 0.42, 0, 0); h.setPose(0.3 * i, 1.2, 0, 2 + i); });
    cam.fov = 30; cam.position.set(0, current[0].height + 1.1, 1.1); cam.lookAt(0, current[0].height - 0.25, -0.05);
  } else if (T >= 20) {
    // high-angle (ceiling camera) close view: all four walking towards / away from the camera
    const ph = T >= 40 ? [0.0, 0.25, 0.5, 0.75] : [0.2, 0.47, 0.74, 1.01];
    current.forEach((h, i) => { h.object.rotation.y = T >= 40 ? 0 : (i % 2 ? Math.PI : 0); h.object.position.set((i - 1.5) * 0.8, 0, 0); h.setPose(ph[i], 1.25, 0, 3 + i); if (T >= 40) h.mesh.material = clay; });
    cam.position.set(0, 3.6, 2.2);
    cam.lookAt(0, 0.7, -0.2);
  } else {
    cam.position.set(0, 1.25, 5.6);
    cam.lookAt(0, 0.85, 0);
  }
  cam.updateProjectionMatrix();
  console.warn(`${seed} ${current[0].look.sex} ${current[0].look.outfit.top}/${current[0].look.outfit.bottom} hair ${current[0].look.hair}`);
  renderer.render(scene, cam);
};
