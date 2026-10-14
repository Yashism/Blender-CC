// Shader-program churn check: steps the feed through time like an export and reports every
// program compiled after start-up (there should be none once people share one program
// family and the keeper keeps it alive).
//   node tools/shot.mjs --entry src/sim/tests/feed_programs.js --out <prefix> --times 300 --size 480x270
// (T = the number of seconds to step through, at 0.5 s)
import { createSimFeed } from '../feed_sim3d.js';

const host = document.getElementById('host');
let feed;
window.__ready = (async () => { feed = await createSimFeed(host, { seed: 7, quality: 'low', motionBlur: 0 }); })();
window.__renderAt = async (dur) => {
  const r = feed._internal.renderer;
  const keys = () => new Set(r.info.programs.map((p) => p.cacheKey));
  await feed.seek(0); feed.render(0);
  let known = keys();
  const startN = known.size;
  const fresh = [];
  for (let T = 0.5; T <= dur; T += 0.5) {
    await feed.seek(T);
    feed.render(T);
    feed.people(T);
    const k = keys();
    for (const c of k) if (!known.has(c)) fresh.push({ T, people: feed._internal.pool.size });
    known = new Set([...known, ...k]);
  }
  console.warn(`[programs] at start ${startN}, after ${dur} s ${keys().size}, compiled during playback: ${fresh.length} ${JSON.stringify(fresh.slice(0, 10))}`);
};
