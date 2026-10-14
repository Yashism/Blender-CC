// Empty-room render of the environment with the CCTV pass.
// node tools/shot.mjs --entry src/sim/tests/env_room.js --out <prefix> --times 0,1.5
import * as THREE from 'three';
import { buildEnvironment } from '../environment.js';
import { createCCTVPasses } from '../cctv_pass.js';

const host = document.getElementById('host');
const W = host.clientWidth, H = host.clientHeight;
const params = new URLSearchParams(location.search);
const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance' });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.domElement.style.cssText = 'display:block;width:100%;height:100%';
host.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const t0 = performance.now();
const env = buildEnvironment(scene, renderer);
const passes = createCCTVPasses(renderer, scene, env.camera, W, H, { renderScale: Number(params.get('scale') || 1.25) });
if (params.get('clean')) { passes.params.noise = 0; passes.params.block = 0; passes.params.chromaNoise = 0; }
if (params.get('exposure')) passes.params.exposure = Number(params.get('exposure'));
console.warn(`[env] build ${(performance.now() - t0).toFixed(0)} ms, render ${passes.renderSize.join('x')}`);
window.__env = env; window.__passes = passes;
window.__ready = Promise.resolve();
window.__renderAt = async (T) => {
  const t1 = performance.now();
  env.update(T);
  passes.render(T);
  const gl = renderer.getContext(); gl.finish();
  console.warn(`[env] frame T=${T} ${(performance.now() - t1).toFixed(0)} ms, calls=${renderer.info.render.calls} tris=${renderer.info.render.triangles}`);
};
