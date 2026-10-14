// Checks projectToImage()/distortNdc() against the rendered (distorted) image:
// draws the counting line and markers at known 3D points on a 2D overlay.
// node tools/shot.mjs --entry src/sim/tests/env_line.js --out <prefix> --times 0
import * as THREE from 'three';
import { buildEnvironment, projectToImage, LINE, OBSTACLES, DOOR } from '../environment.js';
import { createCCTVPasses } from '../cctv_pass.js';

const host = document.getElementById('host');
const W = host.clientWidth, H = host.clientHeight;
const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.domElement.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%';
host.appendChild(renderer.domElement);
const overlay = document.createElement('canvas');
overlay.width = W; overlay.height = H;
overlay.style.cssText = 'position:absolute;left:0;top:0;width:100%;height:100%';
host.appendChild(overlay);

const scene = new THREE.Scene();
const env = buildEnvironment(scene, renderer);
const passes = createCCTVPasses(renderer, scene, env.camera, W, H, { renderScale: 1.25 });

function drawOverlay() {
  const g = overlay.getContext('2d');
  g.clearRect(0, 0, W, H);
  const sx = W / 1920, sy = H / 1080;
  const P = (v) => { const [x, y] = projectToImage(env.camera, v); return [x * sx, y * sy]; };
  // counting line, sampled so lens curvature shows
  g.strokeStyle = 'rgba(0,255,255,0.9)'; g.lineWidth = 2;
  g.beginPath();
  for (let i = 0; i <= 40; i++) {
    const x = LINE.x0 + (LINE.x1 - LINE.x0) * (i / 40);
    const [px, py] = P([x, 0, LINE.z]);
    if (i === 0) g.moveTo(px, py); else g.lineTo(px, py);
  }
  g.stroke();
  const mark = (v, c) => { const [x, y] = P(v); g.strokeStyle = c; g.lineWidth = 2; g.beginPath(); g.arc(x, y, 6, 0, Math.PI * 2); g.stroke(); };
  // door opening corners (front plane), podium front-bottom corners, stanchion heads/bases
  for (const x of [DOOR.x0, DOOR.x1]) { mark([x, 0, DOOR.z], '#0f0'); mark([x, DOOR.height, DOOR.z], '#0f0'); }
  const pod = OBSTACLES[0];
  for (const dx of [-pod.w / 2, pod.w / 2]) { mark([pod.cx + dx, 0, pod.cz + pod.d / 2], '#ff0'); mark([pod.cx + dx, 1.12, pod.cz + pod.d / 2], '#ff0'); }
  for (const o of OBSTACLES.filter((q) => q.kind === 'circle')) { mark([o.x, 0, o.z], '#f0f'); mark([o.x, 1.06, o.z], '#f0f'); }
  // a 1 m floor grid around the line to judge perspective
  g.strokeStyle = 'rgba(255,255,255,0.25)'; g.lineWidth = 1;
  for (let z = -5; z <= 1; z += 1) {
    g.beginPath();
    for (let i = 0; i <= 30; i++) { const [px, py] = P([-3.5 + 8.3 * i / 30, 0, z]); if (i === 0) g.moveTo(px, py); else g.lineTo(px, py); }
    g.stroke();
  }
}

window.__ready = Promise.resolve();
window.__renderAt = async (T) => { env.update(T); passes.render(T); drawOverlay(); };
// grab helper for tools that read pixels: composite both canvases
window.__grab = () => {
  const c = document.createElement('canvas'); c.width = W; c.height = H;
  const g = c.getContext('2d'); g.drawImage(renderer.domElement, 0, 0); g.drawImage(overlay, 0, 0);
  return c.toDataURL('image/png');
};
