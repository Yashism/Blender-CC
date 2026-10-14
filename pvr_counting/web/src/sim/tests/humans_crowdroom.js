// People driven by the real crowd (crowd.js) in the real room (environment.js + cctv_pass.js).
// Humans are created lazily per agent. T >= 1000 draws boxPoints-based boxes at time T - 1000.
//   node tools/shot.mjs --entry src/sim/tests/humans_crowdroom.js --out <prefix> --times 60,75 --size 1920x1080
import * as THREE from 'three';
import { createHuman } from '../humans.js';
import { createCrowd } from '../crowd.js';

let buildEnvironment, createCCTVPasses, distortNdc = (x, y) => [x, y];

async function init() {
  try { ({ buildEnvironment } = await import('../environment.js')); } catch (e) { console.warn('[crowdroom] environment.js unavailable: ' + e.message); }
  try { const m = await import('../cctv_pass.js'); createCCTVPasses = m.createCCTVPasses; distortNdc = m.distortNdc; } catch (e) { console.warn('[crowdroom] cctv_pass.js unavailable: ' + e.message); }
  const host = document.getElementById('host');
  const W = host.clientWidth, H = host.clientHeight;
  const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H);
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const env = buildEnvironment(scene, renderer);
  const passes = createCCTVPasses(renderer, scene, env.camera, W, H, {});
  const crowd = createCrowd({ seed: 7, horizon: 600 });
  const humans = new Map();
  const ov = document.createElement('canvas');
  ov.width = W; ov.height = H;
  ov.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none';
  host.appendChild(ov);
  const g2 = ov.getContext('2d');
  const pts = [];
  const v = new THREE.Vector3();
  window.__renderAt = async (T) => {
    const boxes = T >= 1000;
    if (boxes) T -= 1000;
    g2.clearRect(0, 0, W, H);
    const active = new Set();
    for (const a of crowd.activeAt(T)) {
      const s = crowd.stateAt(a, T);
      if (!s) continue;
      active.add(a.id);
      let h = humans.get(a.id);
      if (!h) { h = createHuman(a.seed, a.human); humans.set(a.id, h); scene.add(h.object); }
      h.object.position.set(s.x, 0, s.z);
      h.object.rotation.y = s.heading;
      h.setPose(s.ndist / h.strideLength, s.speed, s.turnRate, T, s.strideK);
      h.setAlpha(s.alpha);
    }
    for (const [id, h] of humans) if (!active.has(id)) { h.dispose(); humans.delete(id); }
    env.update(T);
    passes.render(T);
    if (boxes) {
      env.camera.updateMatrixWorld(true);
      for (const [, h] of humans) {
        if (!h.object.visible) continue;
        h.object.updateMatrixWorld(true);
        h.boxPoints(pts);
        let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
        for (const q of pts) {
          v.copy(q).project(env.camera);
          const [dx, dy] = distortNdc(v.x, v.y);
          const px = (dx * 0.5 + 0.5) * W, py = (0.5 - dy * 0.5) * H;
          x0 = Math.min(x0, px); y0 = Math.min(y0, py); x1 = Math.max(x1, px); y1 = Math.max(y1, py);
        }
        g2.strokeStyle = 'rgba(0,255,120,0.95)'; g2.lineWidth = 2;
        g2.strokeRect(x0, y0, x1 - x0, y1 - y0);
      }
    }
    console.warn(`[crowdroom] T=${T} people=${humans.size}`);
  };
}
window.__ready = init();
