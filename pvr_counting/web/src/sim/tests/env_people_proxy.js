// Lighting check with simple stand-in bodies (capsules) at typical positions:
// are people lit plausibly, do they cast soft shadows, do they read at this angle?
// node tools/shot.mjs --entry src/sim/tests/env_people_proxy.js --out <prefix> --times 0
import * as THREE from 'three';
import { buildEnvironment, projectToImage, createContactShadow } from '../environment.js';
import { createCCTVPasses } from '../cctv_pass.js';

const host = document.getElementById('host');
const W = host.clientWidth, H = host.clientHeight;
const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true });
renderer.setPixelRatio(1);
renderer.setSize(W, H);
host.appendChild(renderer.domElement);
const scene = new THREE.Scene();
const env = buildEnvironment(scene, renderer);
const passes = createCCTVPasses(renderer, scene, env.camera, W, H);

const cloth = [0x2a3550, 0x7a1f24, 0xd8d2c4, 0x1b1b1b, 0x3f5a3a, 0xc9a227];
const skin = new THREE.MeshStandardMaterial({ color: 0x8d5a3b, roughness: 0.6 });
const hair = new THREE.MeshStandardMaterial({ color: 0x0c0a09, roughness: 0.5 });
const spots = [[-0.6, -4.6], [0.5, -3.6], [-1.2, -2.6], [1.6, -1.2], [-0.2, -0.4], [2.6, -0.1], [-2.6, 0.2]];
spots.forEach(([x, z], i) => {
  const g = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.19, 0.75, 6, 16), new THREE.MeshStandardMaterial({ color: cloth[i % cloth.length], roughness: 0.85 }));
  body.position.y = 1.0; body.scale.set(1, 1, 0.7);
  const legs = new THREE.Mesh(new THREE.CapsuleGeometry(0.13, 0.55, 4, 12), new THREE.MeshStandardMaterial({ color: 0x1d2633, roughness: 0.9 }));
  legs.position.y = 0.42; legs.scale.set(1.2, 1, 0.8);
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.11, 20, 14), skin); head.position.y = 1.6;
  const hr = new THREE.Mesh(new THREE.SphereGeometry(0.115, 20, 10, 0, Math.PI * 2, 0, Math.PI * 0.55), hair); hr.position.y = 1.62;
  for (const m of [body, legs, head, hr]) { m.castShadow = true; m.receiveShadow = true; g.add(m); }
  g.position.set(x, 0, z);
  scene.add(g);
  const cs = createContactShadow(0.4); cs.position.x = x; cs.position.z = z; scene.add(cs);
});

window.__ready = Promise.resolve();
window.__renderAt = async (T) => { env.update(T); passes.render(T); };
void projectToImage;
