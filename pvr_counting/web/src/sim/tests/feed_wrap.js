// Plan wrap and long-run checks: the next loop's pre-roll people are already walking in
// before T = 3600 (no pop-in), events(T) for huge / non-finite T, people(T) robustness.
//   node tools/shot.mjs --entry src/sim/tests/feed_wrap.js --out <prefix> --times 0 --size 480x270
import { createSimFeed } from '../feed_sim3d.js';

const host = document.getElementById('host');
let feed;
window.__ready = (async () => { feed = await createSimFeed(host, { seed: 7, quality: 'low', motionBlur: 0 }); })();
window.__renderAt = async () => {
  const P = feed.duration;
  const al = feed._internal.activeList;
  const ids = (T) => al(T).map((x) => x.gid).sort((a, b) => a - b);
  const before = ids(P - 0.05), at = ids(P), after = ids(P + 0.05);
  const popped = at.filter((g) => !before.includes(g));
  const popInfo = popped.map((g) => { const s = feed._internal.stateOf(g, P); return { g, z: s && +s.z.toFixed(2), alpha: s && +s.alpha.toFixed(2) }; });
  console.warn(`[wrap] active at P-0.05 ${JSON.stringify(before)} at P ${JSON.stringify(at)} new at P ${JSON.stringify(popInfo)} at P+0.05 ${JSON.stringify(after)}`);
  const t0 = performance.now();
  const e1 = feed.events(36000);
  const t1 = performance.now();
  const e2 = feed.events(36000.01);
  const t2 = performance.now();
  const eInf = feed.events(Infinity), eNaN = feed.events(NaN);
  let sorted = true; for (let i = 1; i < e1.length; i++) if (e1[i].t < e1[i - 1].t) sorted = false;
  console.warn(`[events] events(36000) n=${e1.length} sorted=${sorted} ${(t1 - t0).toFixed(1)} ms, repeat ${(t2 - t1).toFixed(2)} ms same=${e1 === e2}; Infinity -> ${eInf.length}, NaN -> ${eNaN.length}`);
  const p = feed.people(NaN), f = feed.footAt(5, NaN);
  console.warn(`[robust] people(NaN) ${p.length}, footAt(NaN) ${f}`);
  await feed.seek(P - 0.2); feed.render(P - 0.2);
  const b = feed.people(P - 0.2);
  console.warn(`[wrap] boxes at P-0.2: ${JSON.stringify(b.map((q) => [q.id, +q.a.toFixed(2)]))}`);
};
