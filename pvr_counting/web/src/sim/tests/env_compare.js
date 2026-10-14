// Side-by-side page: live render (left) next to look_ref.jpg (right), same size.
// node tools/shot.mjs --entry src/sim/tests/env_compare.js --out <prefix> --times 0 --size 1920x540
// (the reference is loaded from the repo by absolute file:// URL; only used by this test page)
import * as THREE from 'three';
import { buildEnvironment } from '../environment.js';
import { createCCTVPasses } from '../cctv_pass.js';

const REF = new URLSearchParams(location.search).get('ref') || 'file:///home/user/Blender-CC/pvr_counting/media/look_ref.jpg';
const host = document.getElementById('host');
const W = Math.floor(host.clientWidth / 2), H = Math.round(W * 9 / 16);
const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
renderer.domElement.style.cssText = `position:absolute;left:0;top:0;width:${W}px;height:${H}px`;
host.appendChild(renderer.domElement);
const img = new Image();
img.style.cssText = `position:absolute;left:${W}px;top:0;width:${W}px;height:${H}px`;
host.appendChild(img);
const label = (txt, x) => {
  const d = document.createElement('div');
  d.textContent = txt;
  d.style.cssText = `position:absolute;left:${x + 10}px;top:8px;font:600 14px sans-serif;color:#fff;background:rgba(0,0,0,.55);padding:3px 8px;border-radius:3px`;
  host.appendChild(d);
};
label('procedural (three.js)', 0);
label('look_ref.jpg', W);

const scene = new THREE.Scene();
const env = buildEnvironment(scene, renderer);
const passes = createCCTVPasses(renderer, scene, env.camera, W, H, { renderScale: 1.25 });
window.__ready = new Promise((res) => { img.onload = res; img.onerror = res; img.src = REF; });
window.__renderAt = async (T) => { env.update(T); passes.render(T); };
