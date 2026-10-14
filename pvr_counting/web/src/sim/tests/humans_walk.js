// Walk-cycle filmstrip: 8 phases (0, 1/8, ... 7/8) of one person.
//   top row: side view (orthographic, the person walks to the right)
//   bottom row: high CCTV-like angle (perspective from 3.7 m)
// T = 0: man, T = 1: woman in a saree, T = 2: woman with popcorn, T = 3: child.
// T = 8: onion skin, side view, 16 poses over one cycle with the root moving at speed 1.3 m/s:
//        planted feet must overlap exactly (one sharp dark shoe per step).
//   node tools/shot.mjs --entry src/sim/tests/humans_walk.js --out <prefix> --times 0,1,8 --size 1800x900
import * as THREE from 'three';
import { makeRenderer, neutralScene } from './humans_testkit.js';
import { createHuman } from '../humans.js';
import { sampleLook } from '../human_look.js';

const { renderer, W, H } = makeRenderer();
const scene = neutralScene({ bg: 0x9a9da0 });
const persp = new THREE.PerspectiveCamera(30, 1, 0.1, 100);
const ortho = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, 100);
let current = [];
const SUBJECTS = [[401, { kind: 'adult', sex: 'm', carry: null }], [402, { kind: 'adult', sex: 'f', carry: null }], [403, { kind: 'adult', sex: 'f', carry: 'popcorn' }], [404, { kind: 'child', sex: 'm', carry: null }]];
for (let s = 500; s < 900; s++) { const l = sampleLook(s, { kind: 'adult', sex: 'f' }); if (l.outfit.top === 'saree') { SUBJECTS[1][0] = s; break; } }
const SPEED = 1.3;
// floor grid lines every 0.25 m help judge stride and planting
const grid = new THREE.GridHelper(12, 48, 0x55524e, 0x6a6662);
grid.position.y = 0.001;
scene.add(grid);
scene.traverse((c) => c.layers.enableAll());

function clear() { for (const h of current) h.dispose(); current = []; }

function renderView(cam, x, y, w, h) {
  renderer.setViewport(x, y, w, h);
  renderer.setScissor(x, y, w, h);
  renderer.render(scene, cam);
}

window.__ready = Promise.resolve();
window.__renderAt = async (T) => {
  clear();
  renderer.setScissorTest(true);
  if (T >= 8) {
    const [seed, o] = SUBJECTS[0];
    const N = 16;
    let S = 1;
    for (let i = 0; i < N; i++) {
      const h = createHuman(seed, o);
      S = h.strideLength;
      const ph = i / N;
      h.object.rotation.y = Math.PI / 2;
      h.object.position.set(ph * S - S / 2, 0, 0);
      h.setPose(ph, SPEED, 0, ph * S / SPEED);
      const m = h.mesh.material;
      m.transparent = true; m.opacity = 0.2; m.depthWrite = false; m.alphaHash = false; m.needsUpdate = true;
      h.contactShadow.visible = false;
      h.mesh.castShadow = false;
      scene.add(h.object);
      current.push(h);
    }
    const hh = 2.0, ww = hh * W / H;
    ortho.left = -ww / 2; ortho.right = ww / 2; ortho.top = hh * 0.95; ortho.bottom = -hh * 0.05;
    ortho.position.set(0, 0, 8); ortho.lookAt(0, 0, 0); ortho.updateProjectionMatrix();
    renderView(ortho, 0, 0, W, H);
    return;
  }
  const [seed, o] = SUBJECTS[Math.floor(T) % SUBJECTS.length];
  // build 16 people: 8 for the side row (at z = 0) and 8 for the high-angle row (at z = -12)
  const sp = 0.78;
  for (let i = 0; i < 8; i++) {
    const ph = i / 8;
    for (const row of [0, 1]) {
      const h = createHuman(seed, o);
      h.object.rotation.y = row ? 0 : Math.PI / 2;
      h.object.position.set((i - 3.5) * sp, 0, row ? -12 : 0);
      h.object.traverse((c) => c.layers.set(row + 1));
      if (!row) h.contactShadow.visible = false; // edge-on from the floor-level side camera
      h.setPose(ph, SPEED, 0, 2 + ph);
      scene.add(h.object);
      current.push(h);
    }
  }
  const height = current[0].height;
  // top half: side view (orthographic)
  const hh = height * 1.12, ww = hh * W / (H / 2);
  ortho.left = -ww / 2; ortho.right = ww / 2; ortho.top = hh * 0.97; ortho.bottom = -hh * 0.03;
  ortho.position.set(0, 0, 10); ortho.lookAt(0, 0, 0); ortho.updateProjectionMatrix();
  ortho.layers.set(1);
  renderView(ortho, 0, H / 2, W, H / 2);
  ortho.layers.set(0);
  // bottom half: high CCTV angle onto the row at z = -12
  persp.aspect = W / (H / 2); persp.fov = 22; persp.updateProjectionMatrix();
  persp.position.set(0, 3.7, -12 + 4.6); persp.lookAt(0, 0.55, -12);
  persp.layers.set(2);
  renderView(persp, 0, 0, W, H / 2);
};
