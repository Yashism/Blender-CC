// Builds the self-contained slides (one .html file each, no network needed):
//   ../PVR_Entry_Counter_AI_Footage.html  looping CCTV clip + offline YOLO tracks
//   ../PVR_Entry_Counter_Pure_Code.html   three.js scene rendered live, no footage at all
//
//   node build.mjs            build both (the AI one needs ../media/audi_entry_loop.mp4 and ../data/tracks.json)
//   node build.mjs --only sim
import { build } from 'esbuild';
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, '..');
const REPO = resolve(ROOT, '..');
const only = process.argv.includes('--only') ? process.argv[process.argv.indexOf('--only') + 1] : null;

const b64 = (p) => readFileSync(p).toString('base64');
const font = (fam, w, file) =>
  `@font-face{font-family:'${fam}';font-weight:${w};font-style:normal;font-display:block;src:url(data:font/woff2;base64,${b64(resolve(ROOT, 'assets/fonts', file))}) format('woff2');}`;
const FONTS = [
  ...[400, 500, 600, 700, 800].map((w) => font('Outfit', w, `outfit-latin-${w}-normal.woff2`)),
  font('JetBrains Mono', 500, 'jetbrains-mono-latin-500-normal.woff2'),
  font('JetBrains Mono', 600, 'jetbrains-mono-latin-700-normal.woff2'),
  font('JetBrains Mono', 700, 'jetbrains-mono-latin-700-normal.woff2'),
].join('\n');
const LOGO = `<img id="logo" alt="RAMS Digital" src="data:image/png;base64,${b64(resolve(REPO, 'assets/logo/rams_logo_white.png'))}">`;

const BASE_CFG = {
  eyebrow: 'PVR Cinemas · Audi 03 entrance',
  headline: 'Live entry &amp; exit counting',
  camName: 'AUDI-03 ENTRY',
  camId: 'CAM-03',
  clockLabel: 'Local time',
  insideSub: 'People in Audi 03 right now',
  historyMinutes: 20,
  seed: 11,
};

async function bundle(entry) {
  const r = await build({
    entryPoints: [resolve(HERE, entry)], bundle: true, format: 'iife', minify: true, write: false,
    target: 'es2020', legalComments: 'none', logLevel: 'warning',
  });
  return r.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
}

function page(cfg, script, payload) {
  const tpl = readFileSync(resolve(HERE, 'src/slide/template.html'), 'utf8');
  const fill = {
    TITLE: cfg.title, FONTS_CSS: FONTS, LOGO, EYEBROW: cfg.eyebrow, HEADLINE: cfg.headline,
    CLOCK_LABEL: cfg.clockLabel, CAM_NAME: cfg.camName, CAM_ID: cfg.camId, INSIDE_SUB: cfg.insideSub,
    CAPACITY: String(cfg.capacity), FOOT_LEFT: cfg.footLeft, FOOT_RIGHT: cfg.footRight,
    CONFIG: JSON.stringify(cfg), PAYLOAD: payload,
  };
  // SCRIPT last: the bundle may contain "{{" sequences
  let html = tpl.replace(/\{\{(\w+)\}\}/g, (m, k) => (k === 'SCRIPT' ? m : fill[k] ?? m));
  return html.replace('{{SCRIPT}}', () => script);
}

function write(name, html) {
  const out = resolve(ROOT, name);
  writeFileSync(out, html);
  console.log(`${name}  ${(html.length / 1048576).toFixed(2)} MB`);
}

if (only !== 'sim') {
  const clip = resolve(ROOT, 'media/audi_entry_loop.mp4');
  const tracks = resolve(ROOT, 'data/tracks.json');
  if (existsSync(clip) && existsSync(tracks)) {
    const meta = JSON.parse(readFileSync(resolve(ROOT, 'data/session.json'), 'utf8'));
    const cfg = {
      ...BASE_CFG, ...meta.video,
      title: 'Audi Entry Counter',
      footLeft: 'Illustrative demo · AI-generated CCTV footage · people detected and tracked by YOLO11 + ByteTrack',
      footRight: 'INSIDE = IN − OUT · a count is made the moment a person crosses the line',
    };
    const payload =
      `<script type="application/json" id="tracks">${readFileSync(tracks, 'utf8')}</script>\n` +
      `<script type="text/plain" id="clip-mp4">${b64(clip)}</script>`;
    write('PVR_Entry_Counter_AI_Footage.html', page(cfg, await bundle('src/main_video.js'), payload));
  } else console.log('skip AI-footage slide (clip or tracks missing)');
}

if (only !== 'video') {
  if (existsSync(resolve(HERE, 'src/main_sim.js')) && existsSync(resolve(HERE, 'src/sim/feed_sim3d.js'))) {
    const meta = JSON.parse(readFileSync(resolve(ROOT, 'data/session.json'), 'utf8'));
    const cfg = {
      ...BASE_CFG, ...meta.sim,
      title: 'Audi Entry Counter 3D',
      footLeft: 'Illustrative demo · real-time 3D simulation rendered in the browser, no footage',
      footRight: 'INSIDE = IN − OUT · a count is made the moment a person crosses the line',
    };
    write('PVR_Entry_Counter_Pure_Code.html', page(cfg, await bundle('src/main_sim.js'), ''));
  } else console.log('skip pure-code slide (sim feed not built yet)');
}
