// Opens a slide in live mode (as a viewer would), samples the counters over time and
// takes screenshots, to check the real-time path (clock, loop wrap, box sync).
//   node tools/live_check.mjs --html ../X.html --seconds 40 --every 5 --out /tmp/live [--video clip.webm]
import { chromium } from 'playwright';
import { resolve } from 'node:path';
const a = Object.fromEntries(process.argv.slice(2).reduce((acc, v, i, arr) => (v.startsWith('--') ? acc.concat([[v.slice(2), arr[i + 1]]]) : acc), []));
const q = a.video ? '?video=' + encodeURIComponent('file://' + resolve(a.video)) : '';
const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--autoplay-policy=no-user-gesture-required', '--allow-file-access-from-files'] });
const page = await browser.newPage({ viewport: { width: 1600, height: 900 } });
page.on('pageerror', (e) => console.log('[page error]', e.message));
page.on('console', (m) => { if (m.type() === 'error') console.log('[page]', m.text()); });
await page.goto('file://' + resolve(a.html) + q);
const n = Math.round(+a.seconds / +a.every);
for (let i = 0; i <= n; i++) {
  await page.waitForTimeout(+a.every * 1000);
  const s = await page.evaluate(() => ({
    in: document.querySelector('#in-5')?.textContent, pct: document.querySelector('#pct')?.textContent,
    clock: document.querySelector('#clock')?.firstChild?.nodeValue, tracked: document.querySelector('#n-tracked')?.textContent,
    seats: document.querySelector('#cap-in')?.textContent,
  }));
  console.log(((i + 1) * +a.every).toFixed(0) + 's', JSON.stringify(s));
  await page.screenshot({ path: `${a.out}_${i}.png` });
}
await browser.close();
