// Node check: feet plant without sliding, joint angle curves, IK reach.
//   node src/sim/tests/humans_gaitcheck.mjs [seed...]
import * as THREE from 'three';
import { createHuman } from '../humans.js';
import { BI } from '../human_gait.js';

const seeds = process.argv.slice(2).map(Number);
if (!seeds.length) seeds.push(11, 12, 13, 14, 15, 16, 17, 18);
const deg = (r) => (r * 180 / Math.PI).toFixed(1);
let worst = 0;
for (const seed of seeds) {
  const kinds = [{ kind: 'adult', sex: 'm' }, { kind: 'adult', sex: 'f' }, { kind: 'child', sex: 'm' }];
  const opts = kinds[seed % 3];
  const h = createHuman(seed, { ...opts, carry: seed % 4 === 0 ? 'popcorn' : null });
  const S = h.strideLength, M = h._M, R = h._R, bones = h._bones;
  const speed = 1.3;
  const pts = (side) => {
    const L = side ? 'R' : 'L';
    const heel = new THREE.Vector3(R[BI['foot' + L]].x, 0.0, -M.heelBack).sub(R[BI['foot' + L]]);
    const mtp = new THREE.Vector3(0, 0, 0);
    const tip = new THREE.Vector3(R[BI['toe' + L]].x, 0.0, M.toeF).sub(R[BI['toe' + L]]);
    return [
      heel.applyMatrix4(bones[BI['foot' + L]].matrixWorld),
      mtp.applyMatrix4(bones[BI['toe' + L]].matrixWorld),
      tip.applyMatrix4(bones[BI['toe' + L]].matrixWorld),
    ];
  };
  const N = 400;
  const rec = [[], []];
  const knee = [], hipY = [];
  let clamped = 0;
  for (let i = 0; i <= N; i++) {
    const ph = 1 + i / N; // second cycle
    h.object.position.set(0, 0, ph * S);
    h.setPose(ph, speed, 0, ph / (speed / S));
    h.object.updateMatrixWorld(true);
    for (let s = 0; s < 2; s++) rec[s].push(pts(s).map((v) => v.clone()));
    const L = 'L';
    const th = new THREE.Vector3().setFromMatrixPosition(bones[BI.thighL].matrixWorld);
    const kn = new THREE.Vector3().setFromMatrixPosition(bones[BI.shinL].matrixWorld);
    const an = new THREE.Vector3().setFromMatrixPosition(bones[BI.footL].matrixWorld);
    const a = kn.clone().sub(th).normalize(), b = an.clone().sub(kn).normalize();
    knee.push(Math.acos(Math.min(1, a.dot(b))));
    hipY.push(new THREE.Vector3().setFromMatrixPosition(bones[BI.pelvis].matrixWorld).y);
    // target vs achieved ankle
    const tgt = h._gait.out.ankle[0].clone().add(new THREE.Vector3(0, 0, ph * S));
    if (an.distanceTo(tgt) > 1e-3) clamped++;
  }
  // sliding: for each foot and contact phase segment, track the pivot point
  const g = h._gait;
  let maxSlide = 0;
  for (let s = 0; s < 2; s++) {
    for (let i = 1; i <= N; i++) {
      let p = 1 + i / N + (s ? 0.5 : 0); p -= Math.floor(p);
      let pp = 1 + (i - 1) / N + (s ? 0.5 : 0); pp -= Math.floor(pp);
      if (pp > p) continue; // wrap
      let k = -1;
      if (p <= g.pHO && pp >= 0) k = 0;           // heel planted (heel rocker + flat)
      if (pp >= g.pHO && p <= g.beta - 0.03) k = 1; // MTP planted (toe flat)
      if (k < 0) continue;
      const d = rec[s][i][k].distanceTo(rec[s][i - 1][k]);
      maxSlide = Math.max(maxSlide, d);
    }
  }
  worst = Math.max(worst, maxSlide);
  const kmax = Math.max(...knee), kmin = Math.min(...knee);
  const kStance = Math.max(...knee.slice(0, Math.round(N * 0.3)));
  console.log(`seed ${seed} ${h.look.kind}/${h.look.sex} H=${h.height.toFixed(2)} S=${S.toFixed(3)} slide/step=${(maxSlide * 1000).toFixed(2)}mm  knee min ${deg(kmin)} stance-max ${deg(kStance)} swing-max ${deg(kmax)} (at ${(knee.indexOf(kmax) / N).toFixed(2)})  bob ${((Math.max(...hipY) - Math.min(...hipY)) * 100).toFixed(1)}cm  ikMiss ${clamped}`);
}
console.log('worst per-step slide (mm):', (worst * 1000).toFixed(2));
