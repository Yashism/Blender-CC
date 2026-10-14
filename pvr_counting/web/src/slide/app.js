// Boots the slide: fits the 1920x1080 stage to the window, runs the live loop, and
// exposes a frame-exact hook for the MP4 export (tools/export_mp4.mjs).
import { createDashboard } from './dashboard.js';

export async function runSlide(makeFeed) {
  const cfg = window.SLIDE_CFG;
  const stage = document.getElementById('stage');
  const exportMode = /[?&#]export/.test(location.href);

  await document.fonts.ready.catch(() => {});
  const feed = await makeFeed(document.getElementById('feed'), cfg);
  const dash = createDashboard(feed, cfg);

  function fit() {
    const s = exportMode ? 1 : Math.min(innerWidth / 1920, innerHeight / 1080);
    stage.style.setProperty('--s', s);
    dash.resize(s);
  }
  fit();
  addEventListener('resize', fit);

  if (exportMode) {
    window.__frame = async (T) => {
      await feed.seek(T);
      feed.render(T);
      const r = dash.render(T);
      await new Promise((res) => requestAnimationFrame(() => requestAnimationFrame(res)));
      return r;
    };
    window.__exportReady = true;
    return;
  }

  // live: T follows the feed's own clock (the video, or wall time for the 3D sim)
  const started = await feed.start();
  if (started === false) {
    const tap = document.getElementById('tap');
    tap.style.display = 'flex';
    tap.addEventListener('click', async () => { tap.style.display = 'none'; await feed.start(); }, { once: true });
  }
  const loop = () => {
    const T = feed.clock();
    feed.render(T);
    dash.render(T);
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);
}
