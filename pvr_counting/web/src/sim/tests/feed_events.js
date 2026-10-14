// Events vs boxes: at each line crossing the person's box should exist and its bottom
// centre should sit on the crossing point (as the dashboard draws it). No rendering.
//   node tools/shot.mjs --entry src/sim/tests/feed_events.js --out <prefix> --times 300 --size 480x270
import { createSimFeed } from '../feed_sim3d.js';

const host = document.getElementById('host');
let feed;
window.__ready = (async () => { feed = await createSimFeed(host, { seed: 7, quality: 'low', motionBlur: 0 }); })();
window.__renderAt = async (dur) => {
  const evs = feed.events(dur);
  let missing = 0, faded = 0;
  const dy = [], dx = [];
  for (const e of evs) {
    await feed.seek(e.t);
    const b = feed.people(e.t).find((p) => p.id === e.id);
    if (!b) { missing++; continue; }
    if (b.a < 0.5) faded++;
    dx.push(b.x + b.w / 2 - e.x); dy.push(b.y + b.h - e.y);
  }
  const pct = (a, p) => { const s = a.slice().sort((x, y) => x - y); return +(s[Math.floor((s.length - 1) * p)] || 0).toFixed(1); };
  console.warn(`[events] n=${evs.length} missing box ${missing} faded ${faded}; bottom dy p5/p50/p95 ${pct(dy, 0.05)}/${pct(dy, 0.5)}/${pct(dy, 0.95)} px, dx p50 ${pct(dx, 0.5)} px`);
};
