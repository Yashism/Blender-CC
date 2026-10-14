// The slide around the camera feed: KPI odometers, tracking overlay, counting line,
// occupancy chart, event log, OSD. render(T) is a pure function of the presentation
// time T (seconds), so the same code drives the live slide and the frame-exact export.
import { mulberry32 } from '../sim/rng.js';

const COL = { in: '#2fdc84', out: '#ff5a6e', track: '#8be9ff', brand: '#ff6b00' };
const RGB = { in: '47,220,132', out: '255,90,110', track: '139,233,255', brand: '255,107,0' };

const clamp = (v, a = 0, b = 1) => Math.min(b, Math.max(a, v));
const easeOut = (p) => 1 - Math.pow(1 - clamp(p), 3);
const easeOut4 = (p) => 1 - Math.pow(1 - clamp(p), 4);
const smooth = (p) => { p = clamp(p); return p * p * (3 - 2 * p); };
const pad2 = (n) => String(n).padStart(2, '0');
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

// number of entries in sorted array `a` with value <= t
function countLE(a, t) {
  let lo = 0, hi = a.length;
  while (lo < hi) { const m = (lo + hi) >> 1; if (a[m] <= t) lo = m + 1; else hi = m; }
  return lo;
}

// Plausible arrivals before the feed started, so the chart has history and the
// starting IN/OUT values are real counts (not just numbers typed in).
function makeHistory(cfg) {
  const H = cfg.historyMinutes * 60;
  const rnd = mulberry32(cfg.seed || 11);
  const sample = (n, shape) => {
    const out = [];
    while (out.length < n) {
      const u = rnd();
      const t = -H + u * H;
      if (rnd() < shape((t + H) / H)) out.push(t - 0.5);
    }
    return out.sort((a, b) => a - b);
  };
  // arrivals ramp up toward the show; a trickle of people step out (snacks, washroom)
  const ins = sample(cfg.in0, (x) => 0.12 + 0.88 * Math.pow(x, 1.6));
  const outs = sample(cfg.out0, (x) => 0.35 + 0.65 * x);
  return { ins, outs };
}

function buildOdometer(el) {
  const n = +el.dataset.digits;
  el.innerHTML = '';
  const cols = [];
  for (let i = 0; i < n; i++) {
    const col = document.createElement('div');
    col.className = 'col';
    const strip = document.createElement('div');
    strip.className = 'strip';
    for (let d = 0; d <= 10; d++) {
      const s = document.createElement('span');
      s.textContent = String(d % 10);
      strip.appendChild(s);
    }
    col.appendChild(strip);
    el.appendChild(col);
    cols.unshift({ col, strip, last: '' }); // cols[0] = ones
  }
  return cols;
}

// Continuous odometer: every digit rolls, carries roll with the digit below.
function setOdometer(cols, V) {
  V = Math.max(0, V);
  for (let k = 0; k < cols.length; k++) {
    const p10 = Math.pow(10, k);
    let pos;
    if (k === 0) pos = V % 10;
    else {
      const r = V % p10;
      const carry = r > p10 - 1 ? r - (p10 - 1) : 0;
      pos = (Math.floor(V / p10) % 10) + carry;
    }
    const vis = k === 0 ? 1 : clamp(V - (p10 - 1));
    const tf = `translateY(${(-pos * 1.3).toFixed(4)}em)`;
    const c = cols[k];
    const key = tf + vis.toFixed(3);
    if (c.last !== key) {
      c.strip.style.transform = tf;
      c.col.style.width = (0.6 * vis).toFixed(4) + 'em';
      c.col.style.opacity = vis.toFixed(3);
      c.last = key;
    }
  }
}

export function createDashboard(feed, cfg) {
  const $ = (s) => document.querySelector(s);
  const hist = makeHistory(cfg);
  const clockStart = new Date(cfg.clockStart).getTime();
  const wall = (t) => new Date(clockStart + t * 1000);
  const hms = (d) => `${pad2(d.getHours())}:${pad2(d.getMinutes())}:${pad2(d.getSeconds())}`;

  const odo = {
    in: buildOdometer($('#k-in .odo')),
    out: buildOdometer($('#k-out .odo')),
    inside: buildOdometer($('#k-inside .odo')),
  };
  const cards = { in: $('#k-in'), out: $('#k-out'), inside: $('#k-inside') };
  const glows = { in: $('#k-in .glow'), out: $('#k-out .glow'), inside: $('#k-inside .glow') };
  const pluses = { in: $('#k-in .plus'), out: $('#k-out .plus'), inside: $('#k-inside .plus') };

  // canvases sized for the stage scale × devicePixelRatio
  const ov = $('#ov'), chart = $('#chart'), bootNoise = $('#boot-noise');
  const octx = ov.getContext('2d'), cctx = chart.getContext('2d'), nctx = bootNoise.getContext('2d');
  let pxr = 1;
  function resize(stageScale) {
    pxr = clamp(stageScale * (window.devicePixelRatio || 1), 1, 2.5);
    for (const c of [ov, chart]) {
      c.width = Math.round(c.clientWidth * pxr);
      c.height = Math.round(c.clientHeight * pxr);
    }
    bootNoise.width = 320; bootNoise.height = 180;
  }

  const S = 1232 / feed.width; // native image px -> panel px
  const fmtId = (id) => 'ID ' + String(id).padStart(4, '0');

  // ---------- counts ----------
  function liveSplit(evs) {
    const ins = [], outs = [];
    for (const e of evs) (e.dir === 'in' ? ins : outs).push(e.t);
    return { ins, outs };
  }
  function countAt(t, live) {
    const hi = t < 0 ? countLE(hist.ins, t) : hist.ins.length + countLE(live.ins, t);
    const ho = t < 0 ? countLE(hist.outs, t) : hist.outs.length + countLE(live.outs, t);
    return { in: hi, out: ho };
  }
  function animated(times, T, base, intro, dur = 0.6) {
    let v = base * intro;
    let i = countLE(times, T) - 1;
    let full = i + 1;
    while (i >= 0 && T - times[i] < dur) { v += easeOut4((T - times[i]) / dur); full--; i--; }
    return v + full;
  }

  // ---------- overlay ----------
  function drawOverlay(T, people, evs, introA) {
    const w = ov.clientWidth, h = ov.clientHeight;
    octx.setTransform(pxr, 0, 0, pxr, 0, 0);
    octx.clearRect(0, 0, w, h);
    octx.globalAlpha = introA;

    // last crossing direction per id
    const dirOf = new Map(), crossT = new Map();
    for (const e of evs) { dirOf.set(e.id, e.dir); crossT.set(e.id, e.t); }

    // counting line
    const [[ax, ay], [bx, by]] = feed.line.map(([x, y]) => [x * S, y * S]);
    const dx = bx - ax, dy = by - ay, L = Math.hypot(dx, dy);
    const nx = -dy / L, ny = dx / L; // normal (points down-ish = camera side)
    const band = 9;
    octx.save();
    octx.beginPath();
    octx.moveTo(ax - nx * band, ay - ny * band); octx.lineTo(bx - nx * band, by - ny * band);
    octx.lineTo(bx + nx * band, by + ny * band); octx.lineTo(ax + nx * band, ay + ny * band);
    octx.closePath();
    const bandGrad = octx.createLinearGradient(ax, ay, bx, by);
    bandGrad.addColorStop(0, 'rgba(255,107,0,0)'); bandGrad.addColorStop(0.08, 'rgba(255,107,0,.16)');
    bandGrad.addColorStop(0.92, 'rgba(255,107,0,.16)'); bandGrad.addColorStop(1, 'rgba(255,107,0,0)');
    octx.fillStyle = bandGrad; octx.fill();
    // moving chevrons inside the band (toward the door = "in" direction)
    octx.beginPath();
    octx.rect(Math.min(ax, bx), Math.min(ay, by) - band, Math.abs(dx), Math.abs(dy) + band * 2);
    octx.clip();
    octx.strokeStyle = 'rgba(255,170,90,.18)'; octx.lineWidth = 1.5;
    const step = 22, off = (T * 18) % step;
    for (let s = -step; s < L + step; s += step) {
      const px = ax + (dx / L) * (s + off), py = ay + (dy / L) * (s + off);
      octx.beginPath(); octx.moveTo(px - 6, py + 4); octx.lineTo(px, py - 3); octx.lineTo(px + 6, py + 4); octx.stroke();
    }
    octx.restore();
    // the line itself
    let pulse = 0;
    for (let i = evs.length - 1; i >= 0 && T - evs[i].t < 1; i--) pulse = Math.max(pulse, 1 - (T - evs[i].t));
    octx.save();
    octx.shadowColor = COL.brand; octx.shadowBlur = 14 + 18 * pulse;
    octx.strokeStyle = `rgba(255,${130 + 80 * pulse},${40 + 120 * pulse},.95)`; octx.lineWidth = 3 + pulse;
    octx.beginPath(); octx.moveTo(ax, ay); octx.lineTo(bx, by); octx.stroke();
    octx.lineWidth = 3; octx.shadowBlur = 8;
    for (const [px, py] of [[ax, ay], [bx, by]]) { // end caps
      octx.beginPath(); octx.moveTo(px - nx * 12, py - ny * 12); octx.lineTo(px + nx * 12, py + ny * 12); octx.stroke();
    }
    octx.restore();
    // direction arrows + labels
    const arrow = (t, dir) => {
      const px = ax + dx * t, py = ay + dy * t;
      const sgn = dir === 'in' ? -1 : 1; // in = toward the door (away from camera)
      const tipX = px + nx * 36 * sgn, tipY = py + ny * 36 * sgn;
      const baseX = px + nx * 8 * sgn, baseY = py + ny * 8 * sgn;
      octx.save();
      octx.strokeStyle = COL[dir]; octx.fillStyle = COL[dir]; octx.lineWidth = 3; octx.lineCap = 'round';
      octx.shadowColor = 'rgba(0,0,0,.8)'; octx.shadowBlur = 4;
      octx.beginPath(); octx.moveTo(baseX, baseY); octx.lineTo(tipX, tipY); octx.stroke();
      octx.beginPath();
      octx.moveTo(tipX + nx * 7 * sgn, tipY + ny * 7 * sgn);
      octx.lineTo(tipX - (dx / L) * 7, tipY - (dy / L) * 7);
      octx.lineTo(tipX + (dx / L) * 7, tipY + (dy / L) * 7);
      octx.closePath(); octx.fill();
      octx.font = '800 15px Outfit, sans-serif';
      octx.textAlign = 'left'; octx.textBaseline = 'middle';
      octx.fillText(dir.toUpperCase(), tipX + 11, tipY + ny * 4 * sgn);
      octx.restore();
    };
    arrow(0.9, 'in'); arrow(0.1, 'out');
    // line tag
    octx.save();
    octx.font = '700 11px Outfit, sans-serif';
    const tag = 'COUNTING LINE';
    const tw = octx.measureText(tag).width + 16;
    const tx = ax + 6, ty = ay - ny * 22 - 11;
    octx.fillStyle = 'rgba(255,107,0,.92)';
    roundRect(octx, tx, ty, tw, 20, 5); octx.fill();
    octx.fillStyle = '#140800'; octx.textBaseline = 'middle'; octx.fillText(tag, tx + 8, ty + 10.5);
    octx.restore();

    // crossing bursts
    for (let i = evs.length - 1; i >= 0 && T - evs[i].t < 1.4; i--) {
      const e = evs[i];
      const p = (T - e.t);
      if (p < 0) continue;
      const ex = e.x * S, ey = ay + (by - ay) * ((e.x * S - ax) / (dx || 1));
      octx.save();
      const g = octx.createRadialGradient(ex, ey, 0, ex, ey, 120);
      g.addColorStop(0, `rgba(${RGB[e.dir]},${0.55 * (1 - p / 1.4)})`); g.addColorStop(1, `rgba(${RGB[e.dir]},0)`);
      octx.fillStyle = g; octx.fillRect(ex - 120, ey - 30, 240, 60);
      if (p < 0.9) {
        octx.strokeStyle = `rgba(${RGB[e.dir]},${1 - p / 0.9})`; octx.lineWidth = 2.5;
        octx.beginPath(); octx.ellipse(ex, ey, 10 + 60 * easeOut(p / 0.9), (10 + 60 * easeOut(p / 0.9)) * 0.38, 0, 0, Math.PI * 2); octx.stroke();
      }
      const lift = 34 * easeOut(p / 1.4);
      octx.globalAlpha = introA * (p < 1 ? 1 : 1 - (p - 1) / 0.4);
      octx.font = '800 22px Outfit, sans-serif'; octx.textAlign = 'center';
      octx.shadowColor = 'rgba(0,0,0,.85)'; octx.shadowBlur = 6;
      octx.fillStyle = COL[e.dir];
      octx.fillText(e.dir === 'in' ? '+1 IN' : '+1 OUT', ex, ey - 22 - lift);
      octx.restore();
    }

    // people: nearest first, so their labels win when labels would overlap
    const placed = [];
    const hit = (r) => placed.some((q) => r.x < q.x + q.w && r.x + r.w > q.x && r.y < q.y + q.h && r.y + r.h > q.y);
    for (const p of [...people].sort((a, b) => (b.y + b.h) - (a.y + a.h))) {
      const dir = dirOf.get(p.id);
      const col = dir ? COL[dir] : COL.track, rgb = dir ? RGB[dir] : RGB.track;
      const a = p.a == null ? 1 : p.a;
      const x = p.x * S, y = p.y * S, bw = p.w * S, bh = p.h * S;
      const ct = crossT.get(p.id);
      const flash = ct != null && T - ct < 0.7 ? 1 - (T - ct) / 0.7 : 0;
      octx.save();
      octx.globalAlpha = introA * a;
      // trail of the foot point
      const pts = [];
      for (let k = 0; k <= 14; k++) { const f = feed.footAt(p.id, T - k * 0.09); if (!f) break; pts.push([f[0] * S, f[1] * S]); }
      for (let k = 1; k < pts.length; k++) {
        octx.strokeStyle = `rgba(${rgb},${0.55 * (1 - k / pts.length)})`; octx.lineWidth = 2.6 * (1 - k / (pts.length + 2));
        octx.beginPath(); octx.moveTo(pts[k - 1][0], pts[k - 1][1]); octx.lineTo(pts[k][0], pts[k][1]); octx.stroke();
      }
      // box
      octx.fillStyle = `rgba(${rgb},${0.06 + 0.22 * flash})`;
      octx.fillRect(x, y, bw, bh);
      octx.strokeStyle = `rgba(${rgb},.5)`; octx.lineWidth = 1;
      octx.strokeRect(x + 0.5, y + 0.5, bw - 1, bh - 1);
      const cl = clamp(Math.min(bw, bh) * 0.22, 8, 22);
      octx.strokeStyle = col; octx.lineWidth = 2.6; octx.lineCap = 'square';
      octx.shadowColor = `rgba(${rgb},.6)`; octx.shadowBlur = 6 + 10 * flash;
      octx.beginPath();
      octx.moveTo(x, y + cl); octx.lineTo(x, y); octx.lineTo(x + cl, y);
      octx.moveTo(x + bw - cl, y); octx.lineTo(x + bw, y); octx.lineTo(x + bw, y + cl);
      octx.moveTo(x + bw, y + bh - cl); octx.lineTo(x + bw, y + bh); octx.lineTo(x + bw - cl, y + bh);
      octx.moveTo(x + cl, y + bh); octx.lineTo(x, y + bh); octx.lineTo(x, y + bh - cl);
      octx.stroke();
      octx.shadowBlur = 0;
      // foot point
      octx.fillStyle = col;
      octx.beginPath(); octx.arc(x + bw / 2, y + bh, 3.2, 0, Math.PI * 2); octx.fill();
      // label
      const label = fmtId(p.id) + (dir ? (dir === 'in' ? '  IN ✓' : '  OUT ✓') : '  ' + p.conf.toFixed(2));
      octx.font = '600 12.5px "JetBrains Mono", monospace';
      const lw = octx.measureText(label).width + 14;
      const lx = clamp(x - 1, 2, w - lw - 2);
      let ly = null;
      // weak detections deep in the dark doorway keep their box but not a label
      const cands = !dir && p.conf < 0.6 ? [] : [y - 24, y + 4, y + 28];
      for (const cand of cands) {
        if (cand < 4 || cand > y + bh - 22) continue;
        if (!hit({ x: lx, y: cand, w: lw, h: 20 })) { ly = cand; break; }
      }
      if (ly == null) { octx.restore(); continue; }
      placed.push({ x: lx, y: ly, w: lw, h: 20 });
      octx.fillStyle = dir ? col : 'rgba(6,10,16,.8)';
      roundRect(octx, lx, ly, lw, 20, 4); octx.fill();
      if (!dir) { octx.strokeStyle = `rgba(${rgb},.6)`; octx.lineWidth = 1; octx.stroke(); }
      octx.fillStyle = dir ? '#04110a' : col;
      if (dir === 'out') octx.fillStyle = '#1a0408';
      octx.textBaseline = 'middle'; octx.fillText(label, lx + 7, ly + 10.5);
      octx.restore();
    }
    octx.globalAlpha = 1;
  }

  // ---------- chart ----------
  function drawChart(T, live, reveal) {
    const w = chart.clientWidth, h = chart.clientHeight;
    const ctx = cctx;
    ctx.setTransform(pxr, 0, 0, pxr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const L = 44, R = 70, Tp = 10, B = 22;
    const pw = w - L - R, ph = h - Tp - B;
    const span = cfg.historyMinutes * 60, t1 = T + 20, t0 = t1 - span;
    const X = (t) => L + ((t - t0) / span) * pw;
    const ymax = cfg.capacity * 1.08;
    const Y = (v) => Tp + ph - (v / ymax) * ph;
    ctx.save();
    ctx.beginPath(); ctx.rect(0, 0, L + pw * reveal + 2, h); ctx.clip();
    // grid + labels
    ctx.font = '500 12px "JetBrains Mono", monospace'; ctx.fillStyle = '#5b6576'; ctx.textBaseline = 'middle';
    ctx.strokeStyle = 'rgba(255,255,255,.05)'; ctx.lineWidth = 1;
    for (const v of [0, Math.round(cfg.capacity / 2)]) {
      ctx.beginPath(); ctx.moveTo(L, Y(v) + 0.5); ctx.lineTo(L + pw, Y(v) + 0.5); ctx.stroke();
      ctx.textAlign = 'right'; ctx.fillText(String(v), L - 8, Y(v));
    }
    const first = Math.ceil((clockStart / 1000 + t0) / 300) * 300; // every 5 min of wall clock
    ctx.textAlign = 'center'; ctx.textBaseline = 'alphabetic';
    for (let s = first; s < clockStart / 1000 + t1; s += 300) {
      const t = s - clockStart / 1000;
      const d = new Date(s * 1000);
      ctx.strokeStyle = 'rgba(255,255,255,.05)';
      ctx.beginPath(); ctx.moveTo(X(t) + 0.5, Tp); ctx.lineTo(X(t) + 0.5, Tp + ph); ctx.stroke();
      ctx.fillText(`${pad2(d.getHours())}:${pad2(d.getMinutes())}`, X(t), h - 5);
    }
    // capacity
    ctx.setLineDash([6, 6]); ctx.strokeStyle = 'rgba(255,255,255,.32)';
    ctx.beginPath(); ctx.moveTo(L, Y(cfg.capacity) + 0.5); ctx.lineTo(L + pw, Y(cfg.capacity) + 0.5); ctx.stroke();
    ctx.setLineDash([]);
    ctx.textAlign = 'right'; ctx.textBaseline = 'middle'; ctx.fillStyle = 'rgba(255,255,255,.45)';
    ctx.fillText(String(cfg.capacity), L - 8, Y(cfg.capacity));
    // in/out bars per 30 s bucket (wall-clock aligned)
    const bucket = 30;
    const bStart = Math.floor((clockStart / 1000 + t0) / bucket) * bucket - clockStart / 1000;
    const bw = (bucket / span) * pw;
    const unit = 4.2;
    for (let b = bStart; b < T; b += bucket) {
      const e = Math.min(b + bucket, T);
      const c0 = countAt(b, live), c1 = countAt(e, live);
      const ni = c1.in - c0.in, no = c1.out - c0.out;
      const x = X(b);
      if (ni) { ctx.fillStyle = 'rgba(47,220,132,.75)'; ctx.fillRect(x + bw * 0.12, Tp + ph - ni * unit, bw * 0.34, ni * unit); }
      if (no) { ctx.fillStyle = 'rgba(255,90,110,.75)'; ctx.fillRect(x + bw * 0.54, Tp + ph - no * unit, bw * 0.34, no * unit); }
    }
    // inside series
    const pts = [];
    for (let t = t0; t <= T; t += 4) { const c = countAt(t, live); pts.push([X(t), Y(c.in - c.out)]); }
    const cNow = countAt(T, live);
    pts.push([X(T), Y(cNow.in - cNow.out)]);
    const grad = ctx.createLinearGradient(0, Tp, 0, Tp + ph);
    grad.addColorStop(0, 'rgba(255,107,0,.38)'); grad.addColorStop(1, 'rgba(255,107,0,0)');
    ctx.beginPath(); ctx.moveTo(pts[0][0], Tp + ph);
    for (const [x, y] of pts) ctx.lineTo(x, y);
    ctx.lineTo(pts[pts.length - 1][0], Tp + ph); ctx.closePath();
    ctx.fillStyle = grad; ctx.fill();
    ctx.beginPath();
    pts.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)));
    ctx.strokeStyle = COL.brand; ctx.lineWidth = 2.5; ctx.lineJoin = 'round';
    ctx.shadowColor = 'rgba(255,107,0,.6)'; ctx.shadowBlur = 8; ctx.stroke(); ctx.shadowBlur = 0;
    // now marker
    const [nxp, nyp] = pts[pts.length - 1];
    const pr = (T % 1.6) / 1.6;
    ctx.fillStyle = `rgba(255,107,0,${0.35 * (1 - pr)})`;
    ctx.beginPath(); ctx.arc(nxp, nyp, 5 + 12 * pr, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(nxp, nyp, 4.5, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = COL.brand; ctx.beginPath(); ctx.arc(nxp, nyp, 2.6, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
    // live value tag
    const v = cNow.in - cNow.out;
    ctx.font = '700 15px "JetBrains Mono", monospace';
    const tw = ctx.measureText(String(v)).width + 16;
    const tx = Math.min(nxp + 12, w - tw - 2), ty = clamp(nyp - 12, 2, h - 26);
    ctx.globalAlpha = reveal;
    ctx.fillStyle = COL.brand; roundRect(ctx, tx, ty, tw, 24, 6); ctx.fill();
    ctx.fillStyle = '#160900'; ctx.textAlign = 'left'; ctx.textBaseline = 'middle'; ctx.fillText(String(v), tx + 8, ty + 12.5);
    ctx.globalAlpha = 1;
  }

  // ---------- event log ----------
  const log = $('#log');
  const rows = [];
  for (let i = 0; i < 5; i++) {
    const r = document.createElement('div');
    r.className = 'row';
    r.innerHTML = '<span class="t"></span><span class="id"></span><span class="tag"></span>';
    log.appendChild(r);
    rows.push({ el: r, t: r.children[0], id: r.children[1], tag: r.children[2], key: '' });
  }
  function drawLog(T, evs) {
    const recent = evs.slice(-5).reverse();
    const q = recent.length ? easeOut((T - recent[0].t) / 0.45) : 1;
    rows.forEach((r, i) => {
      const e = recent[i];
      if (!e) { r.el.style.opacity = 0; return; }
      const key = e.t + e.dir + e.id;
      if (r.key !== key) {
        r.t.textContent = hms(wall(e.t));
        r.id.textContent = fmtId(e.id);
        r.tag.className = 'tag ' + e.dir;
        r.tag.textContent = e.dir === 'in' ? '↑  IN' : '↓  OUT';
        r.key = key;
      }
      const y = (i - 1 + q) * 42;
      r.el.style.transform = `translateY(${y.toFixed(2)}px)`;
      r.el.style.opacity = (i === 0 ? q : 1 - clamp((y - 84) / 30)).toFixed(3);
      const hl = i === 0 ? clamp(1 - (T - e.t) / 2.5) : 0;
      r.el.style.background = hl > 0 ? `rgba(${RGB[e.dir]},${(0.14 * hl).toFixed(3)})` : 'transparent';
    });
  }

  // ---------- intro choreography ----------
  const introEls = [
    ['#hdr', 0.05], ['#cam', 0.12], ['#k-in', 0.25], ['#k-out', 0.32], ['#k-inside', 0.40],
    ['#chart-card', 0.50], ['#feed-card', 0.58], ['#foot', 0.7],
  ].map(([s, d]) => [$(s), d]);
  let introDone = false;
  function intro(T) {
    if (introDone && T > 3) return;
    for (const [el, d] of introEls) {
      const p = easeOut((T - d) / 0.7);
      el.style.opacity = p.toFixed(3);
      el.style.transform = p >= 1 ? '' : `translateY(${(24 * (1 - p)).toFixed(2)}px)`;
    }
    introDone = T > 3;
  }

  // ---------- main render ----------
  let lastTxt = {};
  const setText = (sel, v) => { if (lastTxt[sel] !== v) { $(sel).textContent = v; lastTxt[sel] = v; } };

  function render(T) {
    intro(T);
    const evs = feed.events(T);
    const live = liveSplit(evs);
    const people = feed.people(T);

    // boot screen over the feed
    const boot = $('#boot');
    const bootA = 1 - smooth((T - 0.55) / 0.45);
    boot.style.opacity = bootA.toFixed(3);
    boot.style.display = bootA <= 0 ? 'none' : 'flex';
    if (bootA > 0) {
      const img = nctx.createImageData(320, 180);
      const rnd = mulberry32(Math.floor(T * 30) + 1);
      for (let i = 0; i < img.data.length; i += 4) { const v = rnd() * 255; img.data[i] = img.data[i + 1] = img.data[i + 2] = v; img.data[i + 3] = 255; }
      nctx.putImageData(img, 0, 0);
    }
    const introA = smooth((T - 0.7) / 0.6);

    // KPIs
    const countIntro = easeOut4((T - 0.5) / 1.6);
    const vin = animated(live.ins, T, hist.ins.length, countIntro);
    const vout = animated(live.outs, T, hist.outs.length, countIntro);
    const vins = vin - vout;
    setOdometer(odo.in, vin);
    setOdometer(odo.out, vout);
    setOdometer(odo.inside, vins);

    const now = countAt(T, live);
    const inside = now.in - now.out;
    const c5 = countAt(T - 300, live);
    setText('#in-5', '+' + (now.in - c5.in));
    setText('#out-5', '+' + (now.out - c5.out));
    const occ = clamp(vins / cfg.capacity, 0, 1);
    $('#gauge-arc').setAttribute('stroke-dasharray', `${(occ * 2 * Math.PI * 76).toFixed(2)} 1000`);
    setText('#pct', Math.round(occ * 100) + '%');
    $('#cap-fill').style.width = (occ * 100).toFixed(3) + '%';
    setText('#cap-in', String(Math.round(vins)));
    setText('#cap-free', String(Math.max(0, cfg.capacity - Math.round(vins))));

    // card glow + "+1"
    const fx = (times, T2) => {
      let g = 0, last = null, n = 0;
      for (let i = times.length - 1; i >= 0 && T2 - times[i] < 3; i--) {
        const d = T2 - times[i];
        if (d < 0) continue;
        g += Math.exp(-d / 0.45);
        if (last == null) last = times[i];
        if (d < 1.3) n++;
      }
      return { g: Math.min(1, g), last, n };
    };
    const fIn = fx(live.ins, T), fOut = fx(live.outs, T);
    const setGlow = (key, g, rgb) => {
      glows[key].style.opacity = g.toFixed(3);
      glows[key].style.boxShadow = `0 0 0 1.5px rgba(${rgb},${(0.9 * g).toFixed(3)}) inset, 0 0 40px rgba(${rgb},${(0.35 * g).toFixed(3)}) inset`;
    };
    setGlow('in', fIn.g, RGB.in);
    setGlow('out', fOut.g, RGB.out);
    const insideDir = (fIn.last ?? -1e9) >= (fOut.last ?? -1e9) ? 'in' : 'out';
    setGlow('inside', Math.max(fIn.g, fOut.g) * 0.8, RGB[insideDir]);
    const setPlus = (key, f, txt, color) => {
      const el = pluses[key];
      if (f.last == null || T - f.last >= 1.3) { el.style.opacity = 0; return; }
      const p = (T - f.last) / 1.3;
      el.style.opacity = (Math.sin(Math.min(1, p * 1.25) * Math.PI) ** 0.5).toFixed(3);
      el.style.transform = `translateY(${(-24 * easeOut(p)).toFixed(2)}px)`;
      if (el.textContent !== txt) el.textContent = txt;
      if (color) el.style.color = color;
    };
    setPlus('in', fIn, '+' + fIn.n);
    setPlus('out', fOut, '+' + fOut.n);
    const fIns = insideDir === 'in' ? fIn : fOut;
    setPlus('inside', fIns, insideDir === 'in' ? '+1' : '−1', COL[insideDir]);

    // overlay, chart, log
    drawOverlay(T, people, evs, introA);
    drawChart(T, live, easeOut((T - 0.6) / 1.4));
    drawLog(T, evs);

    // OSD + header
    const d = wall(T);
    setText('#osd-time', `${pad2(d.getDate())}-${pad2(d.getMonth() + 1)}-${d.getFullYear()} ${DAYS[d.getDay()]} ${hms(d)}`);
    const clk = $('#clock');
    const ct = hms(d);
    if (lastTxt.clock !== ct) { clk.firstChild.nodeValue = ct; lastTxt.clock = ct; }
    $('#osd-rec').style.opacity = (T % 1) < 0.6 ? 1 : 0.35;
    const pr = (T % 1.6) / 1.6;
    $('#live-dot').style.boxShadow = `0 0 0 ${(10 * pr).toFixed(2)}px rgba(255,59,59,${(0.55 * (1 - pr)).toFixed(3)})`;
    setText('#n-tracked', String(people.length));
    return { in: now.in, out: now.out, inside };
  }

  return { render, resize };
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}
