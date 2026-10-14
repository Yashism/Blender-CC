// Browser timing of createHuman (geometry + texture painting) and of setPose.
import * as THREE from 'three';
import { createHuman } from '../humans.js';
window.__ready = Promise.resolve();
window.__renderAt = async () => {
  const opts = (i) => ({ kind: i % 6 ? 'adult' : 'child', sex: i % 2 ? 'f' : 'm', carry: [null, 'popcorn', 'cup', 'phone', 'bag'][i % 5] });
  for (let i = 0; i < 5; i++) createHuman(900 + i, opts(i)).dispose();
  const N = 40;
  let t = performance.now();
  const hs = [];
  for (let i = 0; i < N; i++) hs.push(createHuman(1000 + i, opts(i)));
  const create = (performance.now() - t) / N;
  t = performance.now();
  let k = 0;
  for (let f = 0; f < 50; f++) for (const h of hs) { h.setPose(f * 0.031 + k++ * 0.1, 1.25, 0.1, f / 30); h.object.updateMatrixWorld(true); }
  const pose = (performance.now() - t) / (50 * N);
  const verts = hs.reduce((a, h) => a + h.mesh.geometry.attributes.position.count, 0) / N;
  const tris = hs.reduce((a, h) => a + h.mesh.geometry.index.count / 3, 0) / N;
  for (const h of hs) h.dispose();
  console.warn(`createHuman ${create.toFixed(1)} ms/person, setPose+updateMatrixWorld ${(pose * 1000).toFixed(0)} us/person, avg ${verts.toFixed(0)} verts ${tris.toFixed(0)} tris`);
};
