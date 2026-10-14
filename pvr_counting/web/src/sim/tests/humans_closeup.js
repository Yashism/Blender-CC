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
  const isClay = T >= 10;
  const idx = isClay ? T - 10 : T;
  const extra = [[201, { kind: 'adult', sex: 'f', carry: null }], [202, { kind: 'adult', sex: 'm', carry: null }], [203, { kind: 'adult', sex: 'f', carry: 'bag' }], [204, { kind: 'child', sex: 'm', carry: 'popcorn' }]];
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
  cam.position.set(0, 1.25, 5.6);
  cam.lookAt(0, 0.85, 0);
  console.warn(`${seed} ${current[0].look.sex} ${current[0].look.outfit.top}/${current[0].look.outfit.bottom} hair ${current[0].look.hair}`);
  renderer.render(scene, cam);
};
