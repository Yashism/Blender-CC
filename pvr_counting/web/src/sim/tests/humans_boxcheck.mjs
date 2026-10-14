// Node check: the boxPoints bounding box vs the true skinned-mesh bounding box in a CCTV-like view.
//   node src/sim/tests/humans_boxcheck.mjs
// Reports per person the worst under-coverage (mesh outside the box, % of box height) and overshoot.
import * as THREE from 'three';
import { createHuman } from '../humans.js';

const cam = new THREE.PerspectiveCamera(62, 16 / 9, 0.05, 50);
cam.position.set(0, 3.7, 2.6);
cam.lookAt(0, 0.6, -3.2);
cam.updateMatrixWorld(true);
const v = new THREE.Vector3();
const H = 1080, W = 1920;
const proj = (p) => { v.copy(p).project(cam); return [(v.x * 0.5 + 0.5) * W, (0.5 - v.y * 0.5) * H]; };
let worstUnder = 0, sumOver = 0, n = 0;
const kinds = ['adult', 'adult', 'adult', 'child'];
const carries = [null, 'popcorn', 'cup', 'phone', 'bag'];
for (let i = 0; i < 24; i++) {
  const h = createHuman(3000 + i, { kind: kinds[i % 4], sex: i % 2 ? 'f' : 'm', carry: carries[i % 5] });
  const pos = h.mesh.geometry.attributes.position;
  let personUnder = 0;
  for (const [x, z, yaw, ph, sp, tr] of [[0, -1, 0, 0.1, 1.3, 0], [1.2, -2.5, Math.PI, 0.6, 1.2, 0.8], [-1.5, 0.5, 2.2, 0.35, 1.1, -0.5], [0.4, -3.4, 0.3, 0, 0, 0]]) {
    h.object.position.set(x, 0, z);
    h.object.rotation.y = yaw;
    h.setPose(ph, sp, tr, 1 + i);
    h.object.updateMatrixWorld(true);
    // true bounds from skinned vertices
    let mx0 = 1e9, my0 = 1e9, mx1 = -1e9, my1 = -1e9;
    const p = new THREE.Vector3();
    for (let k = 0; k < pos.count; k += 2) {
      p.fromBufferAttribute(pos, k);
      h.mesh.applyBoneTransform(k, p);
      p.applyMatrix4(h.mesh.matrixWorld);
      const [sx, sy] = proj(p);
      mx0 = Math.min(mx0, sx); my0 = Math.min(my0, sy); mx1 = Math.max(mx1, sx); my1 = Math.max(my1, sy);
    }
    const pts = h.boxPoints([]);
    let bx0 = 1e9, by0 = 1e9, bx1 = -1e9, by1 = -1e9;
    for (const q of pts) { const [sx, sy] = proj(q); bx0 = Math.min(bx0, sx); by0 = Math.min(by0, sy); bx1 = Math.max(bx1, sx); by1 = Math.max(by1, sy); }
    const bh = by1 - by0;
    const edges = [bx0 - mx0, mx1 - bx1, by0 - my0, my1 - by1];
    const under = Math.max(...edges, 0) / bh;
    if (process.env.EDGES && under > 0.03) console.log("  pose", x, z, "edges L R T B (px)", edges.map((e) => e.toFixed(1)).join(" "), "boxH", bh.toFixed(0));
    const over = Math.max(mx0 - bx0, bx1 - mx1, my0 - by0, by1 - my1, 0) / bh;
    personUnder = Math.max(personUnder, under);
    worstUnder = Math.max(worstUnder, under);
    sumOver += over; n++;
  }
  if (personUnder > 0.03) console.log(`seed ${3000 + i} ${h.look.kind}/${h.look.sex} ${h.look.outfit.top} ${h.look.hair} carry ${h.look.carry}${h.look.bagStyle ? '/' + h.look.bagStyle : ''}: mesh outside box by ${(personUnder * 100).toFixed(1)}% of box height`);
  h.dispose();
}
console.log(`worst under-coverage ${(worstUnder * 100).toFixed(1)}% of box height, mean overshoot ${(sumOver / n * 100).toFixed(1)}%`);
