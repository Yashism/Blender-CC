// render(T) must be a pure function of T: draws T=41 fresh, after jumping to 63 and back,
// and after a sweep, and compares the pixels (and people(T)).
//   node tools/shot.mjs --entry src/sim/tests/feed_determinism.js --out <prefix> --times 0 --size 640x360
import { createSimFeed } from '../feed_sim3d.js';
const host = document.getElementById('host');
let feed;
window.__ready = (async () => { feed = await createSimFeed(host, { seed: 7, quality: 'medium' }); })();
window.__renderAt = async () => {
  const gl = feed._internal.renderer.getContext();
  const grab = async (T) => {
    await feed.seek(T); feed.render(T);
    const px = new Uint8Array(640 * 360 * 4);
    gl.readPixels(0, 0, 640, 360, gl.RGBA, gl.UNSIGNED_BYTE, px);
    let h = 0; for (let i = 0; i < px.length; i++) h = (Math.imul(h, 31) + px[i]) | 0;
    return h + ' ' + JSON.stringify(feed.people(T));
  };
  const a = await grab(41);
  await grab(63);
  const b = await grab(41);
  for (let T = 38; T < 41; T += 0.7) await grab(T);
  const c = await grab(41);
  console.warn(`[det] fresh==after-jump ${a === b}, fresh==after-sweep ${a === c}`);
};
