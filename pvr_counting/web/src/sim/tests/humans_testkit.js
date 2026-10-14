// Shared helpers for the humans_* visual tests.
import * as THREE from 'three';
import { createHuman } from '../humans.js';

export function makeRenderer(opts = {}) {
  const host = document.getElementById('host');
  const W = host.clientWidth, H = host.clientHeight;
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1);
  renderer.setSize(W, H);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = opts.toneMapping ?? THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = opts.exposure ?? 1.0;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  host.appendChild(renderer.domElement);
  return { renderer, W, H };
}

export function neutralScene(opts = {}) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(opts.bg ?? 0x8a8d90);
  const hemi = new THREE.HemisphereLight(0xe8eef5, 0x4a4540, 1.1);
  scene.add(hemi);
  const key = new THREE.DirectionalLight(0xfff4e8, 2.4);
  key.position.set(-3, 7, 4);
  key.castShadow = true;
  key.shadow.mapSize.set(2048, 2048);
  const sc = key.shadow.camera; sc.left = -6; sc.right = 6; sc.top = 6; sc.bottom = -6; sc.near = 0.5; sc.far = 20;
  key.shadow.bias = -0.0004;
  key.shadow.normalBias = 0.02;
  scene.add(key);
  const fill = new THREE.DirectionalLight(0xdde6ff, 0.7);
  fill.position.set(4, 3, 2);
  scene.add(fill);
  const floor = new THREE.Mesh(new THREE.PlaneGeometry(40, 40), new THREE.MeshStandardMaterial({ color: opts.floor ?? 0x77736e, roughness: 0.95 }));
  floor.rotation.x = -Math.PI / 2;
  floor.receiveShadow = true;
  scene.add(floor);
  return scene;
}

// A varied cast: [seed, opts]
export const CAST = [
  [101, { kind: 'adult', sex: 'm', carry: null }],
  [102, { kind: 'adult', sex: 'f', carry: 'popcorn' }],
  [103, { kind: 'adult', sex: 'm', carry: 'cup' }],
  [104, { kind: 'adult', sex: 'f', carry: 'bag' }],
  [105, { kind: 'child', sex: 'f', carry: null }],
  [106, { kind: 'adult', sex: 'm', carry: 'phone' }],
  [107, { kind: 'adult', sex: 'f', carry: null }],
  [108, { kind: 'adult', sex: 'm', carry: 'bag' }],
  [109, { kind: 'child', sex: 'm', carry: 'cup' }],
  [110, { kind: 'adult', sex: 'f', carry: 'phone' }],
  [111, { kind: 'adult', sex: 'm', carry: 'popcorn' }],
  [112, { kind: 'adult', sex: 'f', carry: 'cup' }],
];

export function makeCast(list = CAST) {
  return list.map(([seed, o]) => createHuman(seed, o));
}

export function describe(h) {
  const L = h.look, o = L.outfit;
  return `${h.seed} ${L.kind}/${L.sex} ${L.H.toFixed(2)}m ${o.top}/${o.bottom}${o.dupatta ? '+dupatta' : ''} hair:${L.hair} carry:${L.carry || '-'}`;
}
