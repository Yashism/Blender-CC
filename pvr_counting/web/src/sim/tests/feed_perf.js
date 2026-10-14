// Real-time cost of the integrated feed: renders consecutive 30 fps frames and forces the
// GPU to finish each one (1-pixel readPixels), then reports the median ms per frame.
//   node tools/shot.mjs --entry src/sim/tests/feed_perf.js --out <prefix> --times 40 --size 1920x1080
// ?quality=low|medium|high, ?frames=N
import { createSimFeed } from '../feed_sim3d.js';
const host = document.getElementById('host');
const q = new URLSearchParams(location.search);
let feed;
window.__ready = (async () => { feed = await createSimFeed(host, { seed: 7, quality: window.__quality || q.get('quality') || 'high' }); })();
window.__renderAt = async (T0) => {
  const r = feed._internal.renderer, gl = r.getContext();
  const px = new Uint8Array(4);
  const n = Number(q.get('frames') || 8);
  await feed.seek(T0); feed.render(T0); gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
  const ms = [], pm = [];
  for (let i = 1; i <= n; i++) {
    const T = T0 + i / 30;
    await feed.seek(T);
    r.info.autoReset = false; r.info.reset();
    const a = performance.now();
    feed.render(T);
    gl.readPixels(0, 0, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, px);
    const b = performance.now();
    feed.people(T); feed.events(T);
    for (const p of feed.people(T)) for (let k = 0; k <= 14; k++) feed.footAt(p.id, T - k * 0.09);
    pm.push(performance.now() - b);
    ms.push(b - a);
  }
  ms.sort((x, y) => x - y); pm.sort((x, y) => x - y);
  const st = feed.stats();
  st.calls = r.info.render.calls; st.triangles = r.info.render.triangles; r.info.autoReset = true;
  console.warn(`[perf] ${st.level} canvas ${st.canvas} render ${st.render} people ${st.people}: frame median ${ms[n >> 1].toFixed(0)} ms (min ${ms[0].toFixed(0)}), people+trails ${pm[n >> 1].toFixed(2)} ms, calls ${st.calls} tris ${st.triangles}`);
};
