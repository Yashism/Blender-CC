// Debug view of the integrated sim feed: camera image + boxes, ids, foot points, the
// counting line (straight endpoints in cyan, true curved line in yellow) and recent events.
//   node tools/shot.mjs --entry src/sim/tests/feed_test.js --out <prefix> --times 3,9,17 --size 1920x1080
// Query (own tools only): ?clean=1 hides the overlay, ?quality=low|medium|high, ?seed=N
import { createSimFeed } from '../feed_sim3d.js';

const host = document.getElementById('host');
const q = new URLSearchParams(location.search);
const clean = q.get('clean') === '1' || window.__clean;

async function init() {
  const t0 = performance.now();
  const feed = await createSimFeed(host, { seed: Number(q.get('seed') || 7), quality: q.get('quality') || window.__quality || 'high', motionBlur: window.__motionBlur });
  console.warn(`[feed] created in ${(performance.now() - t0).toFixed(0)} ms`);
  const ov = document.createElement('canvas');
  ov.width = 1920; ov.height = 1080;
  ov.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;pointer-events:none';
  host.appendChild(ov);
  const g = ov.getContext('2d');
  const sx = 1920 / feed.width;
  window.__feed = feed;
  window.__renderAt = async (T) => {
    const ts = performance.now();
    await feed.seek(T);
    const t1 = performance.now();
    feed.render(T);
    const gl = feed._internal.renderer.getContext(); gl.finish();
    const t2 = performance.now();
    const people = feed.people(T);
    const t3 = performance.now();
    const evs = feed.events(T);
    g.clearRect(0, 0, 1920, 1080);
    if (!clean) {
      g.lineWidth = 2;
      g.strokeStyle = 'rgba(0,220,255,0.9)';
      g.beginPath(); g.moveTo(feed.line[0][0] * sx, feed.line[0][1] * sx); g.lineTo(feed.line[1][0] * sx, feed.line[1][1] * sx); g.stroke();
      g.strokeStyle = 'rgba(255,230,0,0.9)'; g.lineWidth = 1;
      g.beginPath(); feed.linePoints.forEach(([x, y], i) => (i ? g.lineTo(x, y) : g.moveTo(x, y))); g.stroke();
      g.font = '600 16px monospace';
      for (const p of people) {
        g.strokeStyle = `rgba(0,255,120,${0.3 + 0.7 * p.a})`; g.lineWidth = 2;
        g.strokeRect(p.x, p.y, p.w, p.h);
        g.fillStyle = 'rgba(0,255,120,1)';
        g.fillText(`${p.id} ${p.conf.toFixed(2)}`, p.x + 2, p.y - 5);
        // box bottom-centre (what the dashboard draws) vs footAt (trail)
        g.fillStyle = '#ff3'; g.beginPath(); g.arc(p.x + p.w / 2, p.y + p.h, 4, 0, 7); g.fill();
        const f = feed.footAt(p.id, T);
        if (f) { g.fillStyle = '#f0f'; g.beginPath(); g.arc(f[0], f[1], 4, 0, 7); g.fill(); }
        g.strokeStyle = 'rgba(255,0,255,0.6)'; g.beginPath();
        for (let k = 0; k <= 14; k++) { const ff = feed.footAt(p.id, T - k * 0.09); if (!ff) break; k ? g.lineTo(ff[0], ff[1]) : g.moveTo(ff[0], ff[1]); }
        g.stroke();
      }
      for (const e of evs.slice(-6)) {
        g.fillStyle = e.dir === 'in' ? '#3f6' : '#f46';
        g.beginPath(); g.arc(e.x, e.y, 6, 0, 7); g.fill();
        g.fillText(`${e.dir} #${e.id} t=${e.t.toFixed(1)}`, e.x + 8, e.y + 20);
      }
      const nin = evs.filter((e) => e.dir === 'in').length;
      g.fillStyle = '#fff'; g.font = '600 22px monospace';
      g.fillText(`T=${T}  IN ${nin}  OUT ${evs.length - nin}  boxes ${people.length}`, 20, 34);
    }
    for (const p of people) { const s = feed._internal.stateOf(p.id, T); console.warn(`  box ${p.id} z=${s.z.toFixed(2)} x=${s.x.toFixed(2)} a=${s.alpha.toFixed(2)} boxA=${p.a.toFixed(2)} conf=${p.conf} h=${p.h.toFixed(0)}`); }
    const st = feed.stats();
    console.warn(`[feed] T=${T} seek ${(t1 - ts).toFixed(0)} ms, render ${(t2 - t1).toFixed(0)} ms, people() ${(t3 - t2).toFixed(1)} ms, ${JSON.stringify(st)}`);
  };
}
window.__ready = init();
