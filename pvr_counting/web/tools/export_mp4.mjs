// Records a slide to MP4 frame by frame (deterministic, any machine), for PowerPoint.
//
//   node tools/export_mp4.mjs --html ../PVR_Entry_Counter_AI_Footage.html --out ../out/ai.mp4 \
//        --seconds 45 [--fps 30] [--video /abs/clip.webm] [--from 0] [--gl 1] [--still 12.5 --still-out x.png]
//
// --gl 1 is needed for the pure-code slide (WebGL).
//
// The page is opened with ?export so time is driven from here: window.__frame(T)
// seeks the feed, draws the dashboard, and resolves once painted. Headless Chromium has
// no H.264 decoder, so the AI slide is given a VP9 copy of the clip with --video.
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';
import { resolve } from 'node:path';

const a = Object.fromEntries(process.argv.slice(2).reduce((acc, v, i, arr) => (v.startsWith('--') ? acc.concat([[v.slice(2), arr[i + 1]]]) : acc), []));
const html = resolve(a.html);
const fps = +(a.fps || 30);
const seconds = +(a.seconds || 30);
const from = +(a.from || 0);
const q = new URLSearchParams({ export: '1' });
if (a.video) q.set('video', 'file://' + resolve(a.video));

// 2D-only pages render ~4x faster without the GPU process; WebGL pages (--gl) need SwiftShader
const gpu = a.gl ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] : ['--disable-gpu', '--disable-gpu-compositing'];
const browser = await chromium.launch({ args: [...gpu, '--autoplay-policy=no-user-gesture-required', '--allow-file-access-from-files'] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.log('[page error]', e.message));
page.on('console', (m) => { if (m.type() === 'error') console.log('[page]', m.text()); });
await page.goto(`file://${html}?${q}`);
await page.waitForFunction(() => window.__exportReady === true, null, { timeout: 180000 });

if (a.still) {
  for (const t of String(a.still).split(',')) {
    await page.evaluate((T) => window.__frame(T), +t);
    const out = a['still-out'].replace('%t', t.replace('.', 'p'));
    await page.screenshot({ path: out });
    console.log(out);
  }
  await browser.close();
  process.exit(0);
}

const ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(fps), '-c:v', 'mjpeg', '-i', '-',
  '-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-profile:v', 'high', '-movflags', '+faststart',
  '-r', String(fps), resolve(a.out)], { stdio: ['pipe', 'inherit', 'inherit'] });

const n = Math.round(seconds * fps);
const t0 = Date.now();
for (let i = 0; i < n; i++) {
  const T = from + i / fps;
  await page.evaluate((T) => window.__frame(T), T);
  const buf = await page.screenshot({ type: 'jpeg', quality: 94 });
  if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  if (i % fps === 0) process.stdout.write(`\r${i}/${n} frames  ${((Date.now() - t0) / 1000).toFixed(0)} s`);
}
ff.stdin.end();
await new Promise((r) => ff.on('close', r));
await browser.close();
console.log(`\nwrote ${a.out}`);
