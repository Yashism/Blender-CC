// Measures where the lowest image point of each body (the box bottom) lies on the floor
// relative to the body centre, along the direction toward the camera. No rendering.
//   node tools/shot.mjs --entry src/sim/tests/feed_footcal.js --out /tmp/x --times 0 --size 640x360
import { createSimFeed } from '../feed_sim3d.js';
import { projectToImage } from '../environment.js';
const host = document.getElementById('host');
window.__ready = (async () => {
  const feed = await createSimFeed(host, { seed: 7, quality: 'low' });
  const { poseAt, camera } = feed._internal;
  const cx = camera.position.x, cz = camera.position.z;
  const offs = [], gaps = [], byKind = {};
  const pts = [];
  for (let T = 4; T < 200; T += 0.53) {
    for (const { h, s, gid } of poseAt(T)) {
      const child = h.look && h.look.child;
      if (s.z < -5 || s.z > 1.2) continue;
      h.boxPoints(pts);
      let best = null, by = -1;
      for (const q of pts) { const [px, py] = projectToImage(camera, q); if (py > by) { by = py; best = q; } }
      let ux = cx - s.x, uz = cz - s.z; const L = Math.hypot(ux, uz); ux /= L; uz /= L;
      const off = (best.x - s.x) * ux + (best.z - s.z) * uz;
      offs.push(off);
      (byKind[(child ? 'child' : 'adult') + (s.strideK > 0.9 ? '_k>0.9' : '_k<=0.9')] ||= []).push(off / (s.strideK || 1));
      gaps.push(by - projectToImage(camera, [s.x, 0, s.z])[1]);
    }
  }
  offs.sort((a, b) => a - b); gaps.sort((a, b) => a - b);
  const q = (a, f) => a[Math.floor(f * (a.length - 1))].toFixed(3);
  for (const k in byKind) { const a = byKind[k].sort((x, y) => x - y); console.warn(`[cal] ${k} n=${a.length} off/strideK p50 ${a[a.length >> 1].toFixed(3)}`); }
  console.warn(`[cal] n=${offs.length} off p10 ${q(offs, 0.1)} p50 ${q(offs, 0.5)} p90 ${q(offs, 0.9)} | gap px p10 ${q(gaps, 0.1)} p50 ${q(gaps, 0.5)} p90 ${q(gaps, 0.9)}`);
})();
window.__renderAt = async () => {};
