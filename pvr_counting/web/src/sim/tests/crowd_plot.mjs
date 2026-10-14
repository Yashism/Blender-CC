// Visual check of the crowd simulation: top-down trajectories, a crowded snapshot,
// the paths projected into the real camera view (over look_ref.jpg) and the hour of
// counts. Writes an HTML page and screenshots it with Playwright.
//   node src/sim/tests/crowd_plot.mjs --out <dir> [--seed 7] [--t0 0] [--t1 150] [--snap 0]
import { writeFileSync, mkdirSync } from 'node:fs';
import { resolve, dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { chromium } from 'playwright';
import { createCrowd, CROWD_GEOMETRY as G } from '../crowd.js';
import { CAMERA } from '../environment.js';
import { distortNdc } from '../cctv_pass.js';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? a.concat([[v.slice(2), arr[i + 1]]]) : a), []));
const OUT = resolve(args.out || '.');
const SEED = +(args.seed ?? 7);
const T0 = +(args.t0 ?? 0), T1 = +(args.t1 ?? 150);
mkdirSync(OUT, { recursive: true });
const here = dirname(fileURLToPath(import.meta.url));
const lookRef = resolve(here, '../../../../media/look_ref.jpg');

const crowd = createCrowd({ seed: SEED, horizon: 3600 });
const line = crowd.line;

// ---------------------------------------------------------------- camera projection
const cam = new THREE.PerspectiveCamera(CAMERA.fov, 16 / 9, CAMERA.near, CAMERA.far);
cam.position.set(...CAMERA.position);
cam.rotation.set(-CAMERA.pitch, CAMERA.yaw, CAMERA.roll, 'YXZ');
cam.updateMatrixWorld(true);
const v3 = new THREE.Vector3();
function proj(x, y, z) {
  v3.set(x, y, z).project(cam);
  if (v3.z > 1 || v3.z < -1) return null;
  const [a, b] = distortNdc(v3.x, v3.y);
  return [(a * 0.5 + 0.5) * 1920, (0.5 - b * 0.5) * 1080];
}

// busiest moment in the window for the snapshot
let snap = +(args.snap ?? 0);
if (!snap) {
  let best = -1;
  for (let t = T0 + 5; t < T1; t += 0.5) {
    const n = crowd.activeAt(t).filter((a) => { const s = crowd.stateAt(a, t); return s.alpha > 0.5 && s.z < 1.5 && s.z > -5.5; }).length;
    if (n > best) { best = n; snap = t; }
  }
}

// ---------------------------------------------------------------- data for the page
const tracks = [];
for (const a of crowd.agents) {
  if (a.t1 < T0 || a.t0 > T1) continue;
  const pts = [], img = [];
  let stand = null;
  const stands = [];
  for (let t = Math.max(a.t0, T0); t <= Math.min(a.t1, T1); t += 0.1) {
    const s = crowd.stateAt(a, t);
    pts.push([+s.x.toFixed(3), +s.z.toFixed(3)]);
    if (s.alpha > 0.05) { const p = proj(s.x, 0, s.z); if (p) img.push([+p[0].toFixed(1), +p[1].toFixed(1)]); }
    if (s.speed < 0.05) stand ||= [s.x, s.z]; else if (stand) { stands.push(stand); stand = null; }
  }
  const g = crowd.groupInfo(a.group);
  tracks.push({ id: a.id, kind: a.kind, child: a.human.kind === 'child', group: a.group, size: g.size, pts, img, stands, sidestep: g.sidesteps > 0, yieldd: g.yields > 0 });
}
const evWin = crowd.events.filter((e) => e.t >= T0 && e.t <= T1).map((e) => ({ x: e.x, dir: e.dir, img: proj(e.x, 0, line.z) }));
const snapPeople = crowd.activeAt(snap).map((a) => {
  const s = crowd.stateAt(a, snap);
  const h = a.human.kind === 'child' ? 1.15 : 1.68;
  return { id: a.id, kind: a.kind, group: a.group, child: a.human.kind === 'child', carry: a.human.carry, x: s.x, z: s.z, heading: s.heading, speed: s.speed, alpha: s.alpha, foot: proj(s.x, 0, s.z), head: proj(s.x, h, s.z) };
});
// floor region where the feet are in frame
const vis = [];
for (let x = -4.6; x <= 5.0; x += 0.1) for (let z = -9; z <= 4; z += 0.1) {
  const p = proj(x, 0, z);
  if (p && p[0] >= 0 && p[0] <= 1920 && p[1] >= 0 && p[1] <= 1080) vis.push([+x.toFixed(2), +z.toFixed(2)]);
}
// hour of counts
const series = [];
let nin = 0, nout = 0, ei = 0;
for (let t = 0; t <= 3600; t += 10) {
  while (ei < crowd.events.length && crowd.events[ei].t <= t) { if (crowd.events[ei].dir === 'in') nin++; else nout++; ei++; }
  series.push([t, nin, nout]);
}
const perMin = new Array(60).fill(0).map(() => [0, 0]);
for (const e of crowd.events) if (e.t < 3600) perMin[Math.floor(e.t / 60)][e.dir === 'in' ? 0 : 1]++;
const lineImg = [proj(line.x0, 0, line.z), proj(line.x1, 0, line.z)];
const data = { G, line, tracks, evWin, snap, snapPeople, vis, series, perMin, lineImg, T0, T1, stats: crowd.stats, seed: SEED, cam: [CAMERA.position[0], CAMERA.position[2]] };

// ---------------------------------------------------------------- page
const html = `<!doctype html><meta charset="utf-8"><title>Crowd plot</title>
<style>
:root{--in:#2a78d6;--out:#eb6834;--inside:#1baf7a;--ink:#1d1d1b;--ink2:#5e5d57;--grid:#e4e2db;--surface:#fbfaf7;--wall:#3b3a36}
body{margin:0;background:var(--surface);font:13px/1.35 system-ui,-apple-system,Segoe UI,sans-serif;color:var(--ink)}
.wrap{display:grid;grid-template-columns:620px 620px 1240px;grid-template-rows:auto auto;gap:18px;padding:18px;width:max-content}
.card{background:#fff;border:1px solid var(--grid);border-radius:8px;padding:12px}
h2{font-size:14px;margin:0 0 6px} .sub{color:var(--ink2);margin:0 0 8px}
.legend span{display:inline-flex;align-items:center;gap:6px;margin-right:14px;color:var(--ink2)} .sw{width:14px;height:3px;border-radius:2px;display:inline-block}
svg text{fill:var(--ink2);font-size:11px}
.wide{grid-column:1/3}
</style>
<div class="wrap">
 <div class="card"><h2>Top-down paths, t = ${T0}–${T1} s</h2><p class="sub">Door at the top, camera at the bottom. Dots on the line = counted crossings, rings = pauses, shaded = floor in frame.</p>
  <div class="legend"><span><i class="sw" style="background:var(--in)"></i>In</span><span><i class="sw" style="background:var(--out)"></i>Out</span><span><i class="sw" style="background:#999"></i>Child (thin)</span></div>
  <svg id="plan" width="596" height="760"></svg></div>
 <div class="card"><h2>Snapshot at t = ${snap.toFixed(1)} s</h2><p class="sub">Body discs 0.45 m across, tick = heading, grey links = same group.</p>
  <div class="legend"><span><i class="sw" style="background:var(--in)"></i>In</span><span><i class="sw" style="background:var(--out)"></i>Out</span></div>
  <svg id="snap" width="596" height="760"></svg></div>
 <div class="card" style="grid-row:1/3;grid-column:3"><h2>Projected into the camera view (look_ref.jpg)</h2><p class="sub">Foot paths for the window (faded where alpha is low), counting line in yellow, people at the snapshot as foot-to-head sticks.</p>
  <div style="position:relative;width:1216px;height:684px"><img src="file://${lookRef}" style="width:1216px;height:684px;display:block;filter:brightness(1.35)"><svg id="cam" width="1216" height="684" viewBox="0 0 1920 1080" style="position:absolute;left:0;top:0"></svg></div>
  <h2 style="margin-top:14px">Cumulative counts over the hour</h2>
  <div class="legend"><span><i class="sw" style="background:var(--in)"></i>IN</span><span><i class="sw" style="background:var(--out)"></i>OUT</span><span><i class="sw" style="background:var(--inside)"></i>INSIDE (in − out)</span></div>
  <svg id="ts" width="1216" height="230"></svg>
  <h2 style="margin-top:8px">Crossings per minute</h2>
  <svg id="pm" width="1216" height="150"></svg>
  <p class="sub" id="statline"></p></div>
</div>
<script>
const D = ${JSON.stringify(data)};
const NS='http://www.w3.org/2000/svg';
const el=(p,n,a)=>{const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);p.appendChild(e);return e};
const css=(v)=>getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const COL={in:css('--in'),out:css('--out')};
function planFrame(svg){
  // x in [-4.8, 5.1], z in [-9, 4.4] -> px
  const sx=596/9.9, X=(x)=>(x+4.8)*sx, Z=(z)=>(z+9)*sx; // door (z=-5) toward top
  const g=el(svg,'g',{});
  for(const [x,z] of D.vis) el(g,'rect',{x:X(x)-3.1,y:Z(z)-3.1,width:6.2,height:6.2,fill:'#eef3fb'});
  const W=D.G.walkable; let d='M'+W.map(p=>X(p[0])+','+Z(p[1])).join('L');
  el(g,'path',{d,fill:'none',stroke:css('--wall'),'stroke-width':2});
  // auditorium outline: landing + aisle
  el(g,'path',{d:'M'+X(-1.3)+','+Z(-4.82)+'L'+X(-1.3)+','+Z(-5.3)+'L'+X(-6)+','+Z(-5.3)+'M'+X(1.3)+','+Z(-4.82)+'L'+X(1.3)+','+Z(-5.3)+'L'+X(6)+','+Z(-5.3),stroke:css('--wall'),'stroke-width':2,fill:'none'});
  el(g,'path',{d:'M'+X(-6)+','+Z(-7.4)+'L'+X(-0.9)+','+Z(-7.4)+'L'+X(-0.9)+','+Z(-9)+'M'+X(6)+','+Z(-7.4)+'L'+X(0.9)+','+Z(-7.4)+'L'+X(0.9)+','+Z(-9),stroke:'#9b9990','stroke-width':1.5,'stroke-dasharray':'4 3',fill:'none'});
  for(const o of D.G.obstacles){
    if(o.kind==='box') el(g,'rect',{x:X(o.cx-o.w/2),y:Z(o.cz-o.d/2),width:o.w*sx,height:o.d*sx,fill:'#8a6a4a'});
    else if(o.kind==='circle') el(g,'circle',{cx:X(o.x),cy:Z(o.z),r:o.r*sx,fill:'#9aa0a6'});
    else el(g,'line',{x1:X(o.x0),y1:Z(o.z0),x2:X(o.x1),y2:Z(o.z1),stroke:o.name.startsWith('leaf')?'#3b3a36':'#111','stroke-width':o.name.startsWith('leaf')?5:2});
  }
  el(g,'line',{x1:X(D.line.x0),y1:Z(D.line.z),x2:X(D.line.x1),y2:Z(D.line.z),stroke:'#d9a400','stroke-width':3});
  el(g,'circle',{cx:X(D.cam[0]),cy:Z(D.cam[1]),r:6,fill:'#1d1d1b'});
  const t=el(g,'text',{x:X(D.cam[0])+9,y:Z(D.cam[1])+4}); t.textContent='camera';
  const t2=el(g,'text',{x:X(-0.6),y:Z(-8.8)}); t2.textContent='aisle (dark)';
  const t3=el(g,'text',{x:X(2.0),y:Z(-6.0)}); t3.textContent='landing';
  return {X,Z,sx,g};
}
{ // plan
  const {X,Z,g}=planFrame(document.getElementById('plan'));
  for(const tr of D.tracks){
    if(tr.pts.length<2) continue;
    el(g,'path',{d:'M'+tr.pts.map(p=>X(p[0]).toFixed(1)+','+Z(p[1]).toFixed(1)).join('L'),fill:'none',stroke:COL[tr.kind],'stroke-width':tr.child?1:1.6,'stroke-opacity':0.55});
    for(const s of tr.stands) el(g,'circle',{cx:X(s[0]),cy:Z(s[1]),r:6,fill:'none',stroke:COL[tr.kind],'stroke-width':2});
  }
  for(const e of D.evWin) el(g,'circle',{cx:X(e.x),cy:Z(D.line.z),r:2.6,fill:COL[e.dir],stroke:'#fff','stroke-width':1});
}
{ // snapshot
  const {X,Z,sx,g}=planFrame(document.getElementById('snap'));
  const byG={}; for(const p of D.snapPeople)(byG[p.group]||=[]).push(p);
  for(const k in byG){const L=byG[k]; for(let i=1;i<L.length;i++) el(g,'line',{x1:X(L[i-1].x),y1:Z(L[i-1].z),x2:X(L[i].x),y2:Z(L[i].z),stroke:'#b9b7ae','stroke-width':1.5});}
  for(const p of D.snapPeople){
    const r=0.225*sx;
    el(g,'circle',{cx:X(p.x),cy:Z(p.z),r:p.child?r*0.8:r,fill:COL[p.kind],'fill-opacity':0.25+0.6*p.alpha,stroke:'#fff','stroke-width':2});
    el(g,'line',{x1:X(p.x),y1:Z(p.z),x2:X(p.x+Math.sin(p.heading)*0.4),y2:Z(p.z+Math.cos(p.heading)*0.4),stroke:'#1d1d1b','stroke-width':2,'stroke-linecap':'round'});
    if(p.speed<0.05) el(g,'circle',{cx:X(p.x),cy:Z(p.z),r:r+5,fill:'none',stroke:'#1d1d1b','stroke-dasharray':'2 2'});
  }
}
{ // camera
  const s=document.getElementById('cam');
  for(const tr of D.tracks){ if(tr.img.length<2) continue; el(s,'path',{d:'M'+tr.img.map(p=>p[0]+','+p[1]).join('L'),fill:'none',stroke:COL[tr.kind],'stroke-width':tr.child?2:3,'stroke-opacity':0.6}); }
  el(s,'line',{x1:D.lineImg[0][0],y1:D.lineImg[0][1],x2:D.lineImg[1][0],y2:D.lineImg[1][1],stroke:'#ffd400','stroke-width':4});
  for(const p of D.snapPeople){ if(!p.foot||!p.head||p.alpha<0.05) continue;
    el(s,'line',{x1:p.foot[0],y1:p.foot[1],x2:p.head[0],y2:p.head[1],stroke:'#fff','stroke-width':p.child?7:9,'stroke-linecap':'round','stroke-opacity':p.alpha});
    el(s,'line',{x1:p.foot[0],y1:p.foot[1],x2:p.head[0],y2:p.head[1],stroke:COL[p.kind],'stroke-width':p.child?4:6,'stroke-linecap':'round','stroke-opacity':p.alpha});
    el(s,'circle',{cx:p.head[0],cy:p.head[1],r:p.child?8:11,fill:COL[p.kind],stroke:'#fff','stroke-width':2,'fill-opacity':p.alpha});
  }
}
{ // time series
  const s=document.getElementById('ts'), W=1216, Hh=230, L=44, B=24, maxY=Math.max(...D.series.map(r=>r[1]));
  const X=(t)=>L+(t/3600)*(W-L-90), Y=(v)=>Hh-B-(v/maxY)*(Hh-B-10);
  for(let v=0;v<=maxY;v+=200){el(s,'line',{x1:L,x2:W-60,y1:Y(v),y2:Y(v),stroke:css('--grid')}); const t=el(s,'text',{x:L-6,y:Y(v)+4,'text-anchor':'end'}); t.textContent=v;}
  for(let m=0;m<=60;m+=10){const t=el(s,'text',{x:X(m*60),y:Hh-6,'text-anchor':'middle'}); t.textContent=m+' min';}
  const path=(f)=>'M'+D.series.map(r=>X(r[0]).toFixed(1)+','+Y(f(r)).toFixed(1)).join('L');
  const sets=[['in',r=>r[1],css('--in')],['out',r=>r[2],css('--out')],['inside',r=>r[1]-r[2],css('--inside')]];
  for(const [n,f,c] of sets){ el(s,'path',{d:path(f),fill:'none',stroke:c,'stroke-width':2}); const last=D.series[D.series.length-1]; const t=el(s,'text',{x:X(3600)+4,y:Y(f(last))+4}); t.textContent=n.toUpperCase()+' '+f(last); }
}
{ // per minute
  const s=document.getElementById('pm'), W=1216, Hh=150, L=44, B=20; const maxY=Math.max(...D.perMin.map(r=>r[0]+r[1]));
  const bw=(W-L-60)/60, Y=(v)=>(v/maxY)*(Hh-B-10);
  for(let v=0;v<=maxY;v+=10){const y=Hh-B-Y(v); el(s,'line',{x1:L,x2:W-60,y1:y,y2:y,stroke:css('--grid')}); const t=el(s,'text',{x:L-6,y:y+4,'text-anchor':'end'}); t.textContent=v;}
  D.perMin.forEach((r,i)=>{const x=L+i*bw+1; const hi=Y(r[0]), ho=Y(r[1]);
    el(s,'rect',{x,y:Hh-B-hi,width:bw-2,height:Math.max(0,hi-1),fill:css('--in'),rx:2});
    el(s,'rect',{x,y:Hh-B-hi-ho,width:bw-2,height:Math.max(0,ho-1),fill:css('--out'),rx:2});});
  document.getElementById('statline').textContent='seed '+D.seed+' · '+D.stats.agents+' people in 60 min ('+(3600/D.stats.agents).toFixed(2)+' s/person) · groups '+D.stats.groups+' · sidesteps '+D.stats.sidesteps+' · yields '+D.stats.yields+' · pauses '+D.stats.pauses+' · delayed starts '+D.stats.delayedGroups+' (mean '+(D.stats.totalDelay/D.stats.groups).toFixed(2)+' s, out of view) · dropped '+D.stats.dropped;
}
</script>`;
const htmlPath = join(OUT, `crowd_plot_s${SEED}_${T0}-${T1}.html`);
writeFileSync(htmlPath, html);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 2560, height: 1000 }, deviceScaleFactor: 1 });
page.on('pageerror', (e) => console.log('[page error]', e.message));
await page.goto('file://' + htmlPath);
await page.waitForTimeout(300);
const png = htmlPath.replace(/\.html$/, '.png');
await page.screenshot({ path: png, fullPage: true });
await browser.close();
console.log(png, `snapshot t=${snap.toFixed(1)}`);
