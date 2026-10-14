// Headless screenshots of a test entry, at chosen times.
//
//   node tools/shot.mjs --entry src/sim/tests/env_test.js --out /tmp/shots/env --times 0,2.5 [--size 1920x1080]
//
// The entry module must set:
//   window.__ready     a Promise that resolves when the scene is built
//   window.__renderAt  async (T) => void, draws the frame for time T
// It should render into document.getElementById('host') (a positioned div of --size).
// Writes <out>_<T>.png for each time. Console errors from the page are printed.
import { build } from 'esbuild';
import { chromium } from 'playwright';
import { mkdtempSync, writeFileSync, mkdirSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';

const args = Object.fromEntries(process.argv.slice(2).reduce((acc, v, i, a) => (v.startsWith('--') ? acc.concat([[v.slice(2), a[i + 1]]]) : acc), []));
const entry = resolve(args.entry);
const out = resolve(args.out);
const times = (args.times || '0').split(',').map(Number);
const [W, H] = (args.size || '1920x1080').split('x').map(Number);

const dir = mkdtempSync(join(tmpdir(), 'shot-'));
await build({ entryPoints: [entry], bundle: true, format: 'iife', outfile: join(dir, 'bundle.js'), logLevel: 'warning', absWorkingDir: resolve(dirname(new URL(import.meta.url).pathname), '..') });
writeFileSync(join(dir, 'index.html'), `<!doctype html><meta charset="utf-8"><style>html,body{margin:0;background:#000}#host{position:relative;width:${W}px;height:${H}px;overflow:hidden}</style><div id="host"></div><script src="bundle.js"></script>`);
mkdirSync(dirname(out), { recursive: true });

const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
const page = await browser.newPage({ viewport: { width: W, height: H }, deviceScaleFactor: 1 });
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') console.log(`[page ${m.type()}]`, m.text()); });
page.on('pageerror', (e) => console.log('[page error]', e.message));
await page.goto('file://' + join(dir, 'index.html'));
await page.waitForFunction(() => window.__ready, null, { timeout: 120000 });
await page.evaluate(() => window.__ready);
for (const t of times) {
  const t0 = Date.now();
  await page.evaluate((T) => window.__renderAt(T), t);
  const file = `${out}_${String(t).replace('.', 'p')}.png`;
  await page.screenshot({ path: file });
  console.log(`${file}  (${Date.now() - t0} ms)`);
}
await browser.close();
