// High-angle check of the garments that read worst from a ceiling camera: hoodie hoods,
// dupattas and churidars. Picks matching seeds from the look sampler.
//   node tools/shot.mjs --entry src/sim/tests/humans_hood.js --out <prefix> --times 0,1 --size 1600x900
// T = 0: hoodies (back, front), T = 1: dupattas / churidar
import * as THREE from 'three';
import { makeRenderer, neutralScene } from './humans_testkit.js';
import { createHuman, _internal } from '../humans.js';

const { renderer, W, H } = makeRenderer();
const scene = neutralScene({ bg: 0x6a6c70 });
const cam = new THREE.PerspectiveCamera(30, W / H, 0.1, 100);
let current = [];
function find(pred, sex, n) {
  const out = [];
  for (let s = 1; s < 4000 && out.length < n; s++) { const l = _internal.sampleLook(s, { kind: 'adult', sex, carry: null }); if (pred(l)) out.push(s); }
  return out;
}
window.__ready = Promise.resolve();
window.__renderAt = async (T) => {
  for (const h of current) h.dispose();
  current = [];
  const seeds = T === 0 ? find((l) => l.outfit.top === 'hoodie', 'm', 2).concat(find((l) => l.outfit.top === 'hoodie', 'f', 2))
    : find((l) => l.outfit.dupatta, 'f', 3).concat(find((l) => l.outfit.bottom === 'churidar', 'f', 1));
  seeds.forEach((seed, i) => {
    const sex = T === 0 ? (i < 2 ? 'm' : 'f') : 'f';
    const h = createHuman(seed, { kind: 'adult', sex, carry: null });
    h.object.position.set((i - 1.5) * 0.85, 0, 0);
    h.object.rotation.y = i % 2 ? Math.PI : 0;
    h.setPose(0.15 + 0.3 * i, 1.2, 0, 3 + i);
    scene.add(h.object);
    current.push(h);
  });
  cam.position.set(0, 3.4, 2.6);
  cam.lookAt(0, 0.8, -0.1);
  renderer.render(scene, cam);
  console.warn('seeds', seeds.join(','));
};
