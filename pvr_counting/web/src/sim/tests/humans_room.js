// People in the real room (environment.js + cctv_pass.js) seen through the CCTV camera.
// Straight-line walkers so the frame is a pure function of T.
//   node tools/shot.mjs --entry src/sim/tests/humans_room.js --out <prefix> --times 0,1.5 --size 1920x1080
import * as THREE from 'three';
import { createHuman } from '../humans.js';

// The real room and CCTV pass are other modules (possibly mid-edit); fall back to a stand-in room.
let buildEnvironment, createCCTVPasses, distortNdc = (x, y) => [x, y];
function standInRoom(scene) {
  const camera = new THREE.PerspectiveCamera(62, 16 / 9, 0.05, 60);
  camera.position.set(0, 3.7, 2.6); camera.lookAt(0, 0.6, -3.2);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(9.2, 30), new THREE.MeshStandardMaterial({ color: 0x4a1a18, roughness: 0.95 }));
  floor.rotation.x = -Math.PI / 2; floor.position.z = -9; floor.receiveShadow = true; scene.add(floor);
  const wallM = new THREE.MeshStandardMaterial({ color: 0x24261f, roughness: 0.9 });
  for (const x of [-4.6, 4.6]) { const w = new THREE.Mesh(new THREE.PlaneGeometry(30, 3.2), wallM); w.rotation.y = x < 0 ? Math.PI / 2 : -Math.PI / 2; w.position.set(x, 1.6, -9); scene.add(w); }
  const back = new THREE.Mesh(new THREE.PlaneGeometry(9.2, 3.2), wallM); back.position.set(0, 1.6, -5); scene.add(back);
  scene.add(new THREE.HemisphereLight(0x6a6050, 0x201010, 0.35));
  for (const [x, z] of [[-1.6, 0.2], [1.6, 0.2], [-1.6, -3.2], [1.6, -3.2]]) {
    const s = new THREE.SpotLight(0xffc98a, 38, 9, 0.75, 0.6, 2); s.position.set(x, 3.2, z); s.target.position.set(x, 0, z); s.castShadow = true; s.shadow.mapSize.set(1024, 1024);
    scene.add(s); scene.add(s.target);
  }
  return { camera, update() {} };
}

async function init() {
  try { ({ buildEnvironment } = await import('../environment.js')); } catch (e) { console.warn('[room] environment.js unavailable: ' + e.message); }
  try { const m = await import('../cctv_pass.js'); createCCTVPasses = m.createCCTVPasses; distortNdc = m.distortNdc; } catch (e) { console.warn('[room] cctv_pass.js unavailable: ' + e.message); }
  const host = document.getElementById('host');
  const W = host.clientWidth, H = host.clientHeight;
  const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H);
  host.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  let env;
  try { env = buildEnvironment ? buildEnvironment(scene, renderer) : null; } catch (e) { console.warn('[room] buildEnvironment failed: ' + e.message); }
  if (!env) env = standInRoom(scene);
  let passes = null;
  try { passes = createCCTVPasses ? createCCTVPasses(renderer, scene, env.camera, W, H, {}) : null; } catch (e) { console.warn('[room] CCTV pass failed: ' + e.message); }
  if (!passes) { renderer.shadowMap.enabled = true; renderer.outputColorSpace = THREE.SRGBColorSpace; renderer.toneMapping = THREE.ACESFilmicToneMapping; passes = { render: () => renderer.render(scene, env.camera) }; }
  // walkers: [seed, opts, x0, z0, x1, z1, speed, t0]
  const WALK = [
    [601, { kind: 'adult', sex: 'm', carry: 'popcorn' }, -0.6, 2.6, -0.3, -6.5, 1.25, -2.5],
    [602, { kind: 'adult', sex: 'f', carry: null }, 0.1, 2.9, 0.25, -6.5, 1.15, -1.8],
    [603, { kind: 'adult', sex: 'f', carry: 'bag' }, 0.75, 3.0, 0.5, -6.5, 1.2, -3.6],
    [604, { kind: 'child', sex: 'm', carry: 'cup' }, 1.05, 3.2, 0.75, -6.5, 1.0, -3.2],
    [605, { kind: 'adult', sex: 'm', carry: 'phone' }, 0.5, -7.0, 1.6, 3.5, 1.2, -6.0],
    [606, { kind: 'adult', sex: 'f', carry: 'cup' }, -0.5, -7.0, -1.9, 3.5, 1.1, -5.0],
    [607, { kind: 'adult', sex: 'm', carry: null }, -1.6, 3.4, -0.7, -6.5, 1.35, -0.6],
    [608, { kind: 'adult', sex: 'f', carry: 'popcorn' }, 2.2, 3.4, 0.9, -6.5, 1.15, -1.0],
  ];
  const createMs = [];
  const people = WALK.map(([seed, o, x0, z0, x1, z1, sp, t0]) => {
    const tc = performance.now();
    const h = createHuman(seed, o);
    createMs.push(performance.now() - tc);
    scene.add(h.object);
    const L = Math.hypot(x1 - x0, z1 - z0);
    return { h, x0, z0, dx: (x1 - x0) / L, dz: (z1 - z0) / L, L, sp, t0 };
  });
  console.warn('createHuman ms: ' + createMs.map((x) => x.toFixed(1)).join(', '));
  console.warn(people.map((p) => `${p.h.seed} ${p.h.look.sex} ${p.h.look.outfit.top}/${p.h.look.outfit.bottom} ${p.h.look.hair}`).join('\n'));
  // 2D overlay for boxPoints (T >= 100 draws boxes at time T - 100)
  const ov = document.createElement('canvas');
  ov.width = W; ov.height = H;
  ov.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none';
  host.appendChild(ov);
  const g2 = ov.getContext('2d');
  const pts = [];
  const v = new THREE.Vector3();
  function drawBoxes() {
    g2.clearRect(0, 0, W, H);
    env.camera.updateMatrixWorld(true);
    for (const p of people) {
      if (!p.h.object.visible) continue;
      p.h.object.updateMatrixWorld(true);
      p.h.boxPoints(pts);
      let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9;
      g2.fillStyle = 'rgba(255,255,0,0.9)';
      for (const q of pts) {
        v.copy(q).project(env.camera);
        const [dx, dy] = distortNdc(v.x, v.y);
        const px = (dx * 0.5 + 0.5) * W, py = (0.5 - dy * 0.5) * H;
        x0 = Math.min(x0, px); y0 = Math.min(y0, py); x1 = Math.max(x1, px); y1 = Math.max(y1, py);
        g2.fillRect(px - 2, py - 2, 4, 4);
      }
      g2.strokeStyle = 'rgba(0,255,120,0.95)'; g2.lineWidth = 2;
      g2.strokeRect(x0, y0, x1 - x0, y1 - y0);
    }
  }
  window.__renderAt = async (T) => {
    const boxes = T >= 100;
    if (boxes) T -= 100; else g2.clearRect(0, 0, W, H);
    for (const p of people) {
      const d = (T - p.t0) * p.sp;
      const on = d > 0 && d < p.L;
      p.h.object.visible = on;
      if (!on) continue;
      p.h.object.position.set(p.x0 + p.dx * d, 0, p.z0 + p.dz * d);
      p.h.object.rotation.y = Math.atan2(p.dx, p.dz);
      p.h.setPose(d / p.h.strideLength, p.sp, 0, T);
    }
    env.update(T);
    passes.render(T);
    if (boxes) drawBoxes();
  };

}
window.__ready = init();
