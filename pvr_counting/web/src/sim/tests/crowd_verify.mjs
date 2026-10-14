// Full verification of the crowd simulation (pure node, no browser):
//   node src/sim/tests/crowd_verify.mjs [--seed 7] [--horizon 3600]
// Checks: geometry in sync with environment.js, determinism, API shape, pairwise
// separation over the whole horizon (two sampling phases, dt = 0.05), one crossing per
// agent inside the line span, event consistency, motion sanity (no backwards walking,
// no heading snaps, speed / dist consistency), wall + obstacle clearance, fades, pauses
// away from the line, traffic mix, activeAt index, timing. Exit code 1 on any FAIL.
import { createCrowd, CROWD_GEOMETRY, LINE_DEFAULT, buildStatic } from '../crowd.js';

const args = Object.fromEntries(process.argv.slice(2).reduce((a, v, i, arr) => (v.startsWith('--') ? a.concat([[v.slice(2), arr[i + 1]]]) : a), []));
const SEED = +(args.seed ?? 7);
const HORIZON = +(args.horizon ?? 3600);
const DT = 0.05;

let fails = 0;
const results = [];
function check(name, ok, detail) {
  results.push({ name, ok, detail });
  if (!ok) fails++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail !== undefined ? '  ' + (typeof detail === 'string' ? detail : JSON.stringify(detail)) : ''}`);
}
const r3 = (v) => Math.round(v * 1000) / 1000;

// ---------------------------------------------------------------- geometry sync
try {
  const env = await import('../environment.js');
  const close = (a, b) => Math.abs(a - b) < 1e-9;
  const obsOk = env.OBSTACLES.length === CROWD_GEOMETRY.obstacles.length && env.OBSTACLES.every((o, i) => {
    const c = CROWD_GEOMETRY.obstacles[i];
    return o.kind === c.kind && o.name === c.name && Object.keys(o).every((k) => (typeof o[k] === 'number' ? close(o[k], c[k]) : o[k] === c[k]));
  });
  const walkOk = JSON.stringify(env.WALKABLE) === JSON.stringify(CROWD_GEOMETRY.walkable);
  const lineOk = JSON.stringify(env.LINE) === JSON.stringify(LINE_DEFAULT);
  const doorOk = close(env.DOOR.x0, CROWD_GEOMETRY.door.x0) && close(env.DOOR.x1, CROWD_GEOMETRY.door.x1) && close(env.DOOR.z - env.DOOR.reveal, CROWD_GEOMETRY.door.zBack);
  check('geometry mirrors environment.js (OBSTACLES, WALKABLE, LINE, DOOR)', obsOk && walkOk && lineOk && doorOk, { obsOk, walkOk, lineOk, doorOk });
} catch (e) {
  check('geometry mirrors environment.js', false, 'could not import environment.js: ' + e.message);
}

// ---------------------------------------------------------------- build + determinism
let t = performance.now();
const c = createCrowd({ seed: SEED, horizon: HORIZON });
const buildMs = performance.now() - t;
t = performance.now();
const c2 = createCrowd({ seed: SEED, horizon: HORIZON });
const buildMs2 = performance.now() - t;
const c3 = createCrowd({ seed: SEED + 1, horizon: HORIZON });
check(`build time for ${HORIZON} s`, Math.min(buildMs, buildMs2) < 4000, `${buildMs.toFixed(0)} ms / ${buildMs2.toFixed(0)} ms`);

function fingerprint(cr) {
  let h = 2166136261 >>> 0;
  const mix = (v) => { const s = Number.isFinite(v) ? v.toFixed(6) : String(v); for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619) >>> 0; };
  for (const a of cr.agents) { mix(a.id); mix(a.seed); mix(a.t0); mix(a.t1); mix(a.group); mix(a.speed); mix(a.kind === 'in' ? 1 : 2); mix(JSON.stringify(a.human).length); }
  for (const e of cr.events) { mix(e.t); mix(e.id); mix(e.x); }
  for (let k = 0; k < 3000; k++) {
    const tt = (k * 1.2345) % HORIZON;
    for (const a of cr.activeAt(tt)) { const s = cr.stateAt(a, tt); mix(s.x); mix(s.z); mix(s.heading); mix(s.speed); mix(s.dist); mix(s.turnRate); mix(s.alpha); }
  }
  return h.toString(16);
}
const f1 = fingerprint(c), f2 = fingerprint(c2), f3 = fingerprint(c3);
check('deterministic (same seed -> identical agents, events, states)', f1 === f2 && JSON.stringify(c.agents) === JSON.stringify(c2.agents) && JSON.stringify(c.events) === JSON.stringify(c2.events), `${f1} vs ${f2}`);
check('different seed -> different crowd', f1 !== f3, `${f1} vs ${f3}`);
check('repeat stateAt calls are pure', (() => { const a = c.agents[10]; const tm = (a.t0 + a.t1) / 2; return JSON.stringify(c.stateAt(a, tm)) === JSON.stringify(c.stateAt(a, tm)); })());

// ---------------------------------------------------------------- API shape
{
  const a = c.agents[0];
  const keys = ['id', 'seed', 'kind', 'group', 't0', 't1', 'human', 'speed'];
  const okA = c.agents.every((x) => keys.every((k) => k in x) && (x.kind === 'in' || x.kind === 'out') && ['adult', 'child'].includes(x.human.kind) && ['m', 'f'].includes(x.human.sex) && [null, 'popcorn', 'cup', 'bag', 'phone'].includes(x.human.carry));
  const s = c.stateAt(a, (a.t0 + a.t1) / 2);
  const sk = ['x', 'z', 'heading', 'speed', 'dist', 'turnRate', 'alpha'];
  check('agent / state shape per SPEC', okA && sk.every((k) => typeof s[k] === 'number' && Number.isFinite(s[k])) && c.stateAt(a, a.t0 - 0.01) === null && c.stateAt(a, a.t1 + 0.01) === null, { stateKeys: Object.keys(s) });
  const evOk = c.events.every((e, i) => ['t', 'id', 'dir', 'x', 'z'].every((k) => k in e) && (i === 0 || c.events[i - 1].t <= e.t));
  check('events sorted by t with {t,id,dir,x,z}', evOk);
  check('ids unique and 1..N', new Set(c.agents.map((x) => x.id)).size === c.agents.length && c.agents.every((x, i) => x.id === i + 1));
}

// ---------------------------------------------------------------- sample everything once
const tMin = Math.min(...c.agents.map((a) => a.t0));
const tMax = Math.max(...c.agents.map((a) => a.t1));
const G = CROWD_GEOMETRY, ST = buildStatic(G);
const line = c.line;
const per = new Map(c.agents.map((a) => [a.id, { crossings: [], prev: null, standStart: null, stands: [], maxTurn: 0, maxHeadStep: 0, maxDirErr: 0, maxSpeedErr: 0, maxDistErr: 0, back: 0, minClear: 9, minSpeedAtLine: 9 }]));
let minAll = 9, minCross = 9, minGroup = 9, worst = null, pairs = 0, under05 = 0, maxVisible = 0, maxActive = 0;
const visibleHist = [];
const fullFrames = [];
for (const phase of [0, 0.025]) {
  for (let tt = Math.floor(tMin) + phase; tt <= tMax; tt += DT) {
    const act = c.activeAt(tt);
    const st = act.map((a) => c.stateAt(a, tt));
    if (act.length > maxActive) maxActive = act.length;
    for (let i = 0; i < act.length; i++) {
      for (let j = i + 1; j < act.length; j++) {
        const d = Math.hypot(st[i].x - st[j].x, st[i].z - st[j].z);
        pairs++;
        if (d < 0.5) under05++;
        if (d < minAll) { minAll = d; worst = { t: r3(tt), a: act[i].id, b: act[j].id, d: r3(d), at: [r3(st[i].x), r3(st[i].z)] }; }
        if (act[i].group === act[j].group) { if (d < minGroup) minGroup = d; } else if (d < minCross) minCross = d;
      }
    }
    if (phase !== 0) continue;
    let vis = 0;
    for (let i = 0; i < act.length; i++) {
      const a = act[i], s = st[i], p = per.get(a.id);
      if (s.alpha > 0.5 && s.z < 1.6 && s.z > -5.6) vis++;
      p.minClear = Math.min(p.minClear, ST.clearance(s.x, s.z));
      if (s.speed < 0.05) { if (p.standStart === null) p.standStart = { t: tt, z: s.z }; }
      else if (p.standStart !== null) { p.stands.push({ t0: p.standStart.t, t1: tt, z: p.standStart.z }); p.standStart = null; }
      if (Math.abs(s.turnRate) > p.maxTurn) p.maxTurn = Math.abs(s.turnRate);
      if (p.prev && Math.abs(tt - p.prev.t - DT) < 1e-6) {
        const q = p.prev;
        let dh = s.heading - q.heading; dh = Math.atan2(Math.sin(dh), Math.cos(dh));
        if (Math.abs(dh) > p.maxHeadStep) p.maxHeadStep = Math.abs(dh);
        const dx = s.x - q.x, dz = s.z - q.z, dd = Math.hypot(dx, dz);
        if (dd > 0.3 * DT) {
          // walking direction vs body heading
          let e = Math.atan2(dx, dz) - s.heading; e = Math.abs(Math.atan2(Math.sin(e), Math.cos(e)));
          if (e > p.maxDirErr) p.maxDirErr = e;
          // reported speed vs actual displacement (mid-step average)
          const err = Math.abs(dd / DT - 0.5 * (s.speed + q.speed)) / Math.max(0.3, s.speed);
          if (err > p.maxSpeedErr) p.maxSpeedErr = err;
        }
        if (s.dist < q.dist - 1e-6) p.back++;
        // dist drives the gait phase: it must advance exactly with the feet (no sliding)
        const de = Math.abs(s.dist - q.dist - dd);
        if (de > p.maxDistErr) p.maxDistErr = de;
        if (s.z > G.door.zBack && q.z > G.door.zBack && (a.kind === 'in' ? dz > 1e-4 : dz < -1e-4)) p.back++;
        if ((q.z - line.z) * (s.z - line.z) < 0 || (s.z === line.z)) {
          const f = (line.z - q.z) / (s.z - q.z);
          p.crossings.push({ t: q.t + f * DT, x: q.x + f * dx, dir: s.z < q.z ? 'in' : 'out' });
          p.minSpeedAtLine = Math.min(p.minSpeedAtLine, s.speed);
        }
      }
      p.prev = { t: tt, ...s };
    }
    visibleHist.push(vis);
    if (vis > maxVisible) maxVisible = vis;
  }
}
check('separation >= 0.45 m for every pair at all times (dt 0.05, two phases)', minAll >= 0.45, { minAll: r3(minAll), minBetweenGroups: r3(minCross), minWithinGroup: r3(minGroup), pairSamples: pairs, pairsUnder0p5: under05, worst });

// ---------------------------------------------------------------- crossings & events
{
  const evBy = new Map();
  for (const e of c.events) { if (!evBy.has(e.id)) evBy.set(e.id, []); evBy.get(e.id).push(e); }
  let bad = [], dtMax = 0, dxMax = 0;
  for (const a of c.agents) {
    const p = per.get(a.id), ev = evBy.get(a.id) || [];
    const cr = p.crossings;
    const okOne = cr.length === 1 && ev.length === 1;
    const inSpan = cr.every((q) => q.x >= line.x0 && q.x <= line.x1);
    const dirOk = ev.length === 1 && ev[0].dir === a.kind && cr.every((q) => q.dir === a.kind);
    if (okOne) { dtMax = Math.max(dtMax, Math.abs(cr[0].t - ev[0].t)); dxMax = Math.max(dxMax, Math.abs(cr[0].x - ev[0].x)); }
    if (!okOne || !inSpan || !dirOk) bad.push({ id: a.id, crossings: cr.length, events: ev.length, inSpan, dirOk });
  }
  check('every agent crosses the line exactly once, inside its x span, in its own direction', bad.length === 0, { agents: c.agents.length, bad: bad.slice(0, 5) });
  check('event time / x match the sampled crossing', dtMax < 0.03 && dxMax < 0.02, { maxDt: r3(dtMax), maxDx: r3(dxMax) });
  check('all events after t = 0 (pre-roll never pre-counts)', c.events.every((e) => e.t > 0), { first: r3(c.events[0].t) });
  const minLineSpeed = Math.min(...[...per.values()].map((p) => p.minSpeedAtLine));
  check('nobody stands on the counting line (speed at crossing)', minLineSpeed > 0.4, { minSpeedAtCrossing: r3(minLineSpeed) });
}

// ---------------------------------------------------------------- motion sanity
{
  const P = [...per.values()];
  const maxTurn = Math.max(...P.map((p) => p.maxTurn));
  const maxHeadStep = Math.max(...P.map((p) => p.maxHeadStep));
  const maxDirErr = Math.max(...P.map((p) => p.maxDirErr));
  const maxSpeedErr = Math.max(...P.map((p) => p.maxSpeedErr));
  const maxDistErr = Math.max(...P.map((p) => p.maxDistErr));
  const back = P.reduce((s, p) => s + p.back, 0);
  check('no walking backwards (dist monotonic, corridor z monotonic toward goal)', back === 0, { violations: back });
  check('turn rate limited (|turnRate| <= 1.4 rad/s, heading step <= 0.08 rad / 0.05 s)', maxTurn <= 1.4 && maxHeadStep <= 0.08, { maxTurnRate: r3(maxTurn), maxHeadingStep: r3(maxHeadStep) });
  check('heading follows the walking direction (< 12 deg)', maxDirErr < (12 * Math.PI) / 180, { maxErrDeg: r3((maxDirErr * 180) / Math.PI) });
  check('dist advances with the body (gait phase, no foot sliding: < 3 mm per 0.05 s)', maxDistErr < 0.003, { maxErrMm: r3(maxDistErr * 1000) });
  check('reported speed matches displacement (< 10 %)', maxSpeedErr < 0.1, { maxRelErr: r3(maxSpeedErr) });
  const minClear = Math.min(...P.map((p) => p.minClear));
  check('bodies keep clear of walls, door leaves, podium, stanchions, seats', minClear >= -0.01, { minClearance: r3(minClear) });
  // independent check against the raw obstacle list (body radius 0.25)
  let minRaw = 9;
  for (let k = 0; k < c.agents.length; k += 1) {
    const a = c.agents[k];
    for (let tt = a.t0; tt <= a.t1; tt += 0.1) {
      const s = c.stateAt(a, tt);
      for (const o of G.obstacles) {
        let d;
        if (o.kind === 'box') d = Math.hypot(Math.max(0, Math.abs(s.x - o.cx) - o.w / 2), Math.max(0, Math.abs(s.z - o.cz) - o.d / 2));
        else if (o.kind === 'circle') d = Math.hypot(s.x - o.x, s.z - o.z) - o.r;
        else { const dx = o.x1 - o.x0, dz = o.z1 - o.z0; const u = Math.max(0, Math.min(1, ((s.x - o.x0) * dx + (s.z - o.z0) * dz) / (dx * dx + dz * dz))); d = Math.hypot(s.x - o.x0 - u * dx, s.z - o.z0 - u * dz); }
        minRaw = Math.min(minRaw, d);
      }
      if (s.z > -4.9 && s.z < -4.82 && Math.abs(s.x) > 1.3 - 0.25) minRaw = Math.min(minRaw, 0);
    }
  }
  check('raw obstacle distance >= 0.28 m (podium, stanchions, belts, door leaves)', minRaw >= 0.28, { min: r3(minRaw) });
  const stands = P.flatMap((p) => p.stands.filter((s) => s.t1 - s.t0 >= 0.4));
  const minStandLine = stands.length ? Math.min(...stands.map((s) => Math.abs(s.z - line.z))) : 9;
  check('pauses happen in view and well away from the line (>= 0.8 m)', minStandLine >= 0.8, { standingPeople: stands.length, minDistToLine: r3(minStandLine), zRange: stands.length ? [r3(Math.min(...stands.map((s) => s.z))), r3(Math.max(...stands.map((s) => s.z)))] : null });
}

// ---------------------------------------------------------------- spawn / vanish
{
  let bad = [];
  for (const a of c.agents) {
    const s0 = c.stateAt(a, a.t0), s1 = c.stateAt(a, a.t1);
    const hiddenStart = a.kind === 'in' ? s0.z > 2.8 : s0.alpha < 0.01;
    const hiddenEnd = a.kind === 'in' ? s1.alpha < 0.01 : s1.z > 2.8;
    if (!hiddenStart || !hiddenEnd) bad.push({ id: a.id, kind: a.kind, start: [r3(s0.x), r3(s0.z), r3(s0.alpha)], end: [r3(s1.x), r3(s1.z), r3(s1.alpha)] });
  }
  check('appear / vanish out of view (behind camera or alpha 0 in the dark)', bad.length === 0, { bad: bad.slice(0, 4) });
}

// ---------------------------------------------------------------- traffic mix
{
  const nIn = c.events.filter((e) => e.dir === 'in').length, n = c.events.length;
  const groups = new Map();
  for (const a of c.agents) { if (!groups.has(a.group)) groups.set(a.group, []); groups.get(a.group).push(a); }
  const sizes = [0, 0, 0, 0, 0];
  for (const g of groups.values()) sizes[g.length]++;
  const kids = c.agents.filter((a) => a.human.kind === 'child');
  const kidsOk = kids.every((k) => { const g = groups.get(k.group); return g.length > 1 && g.some((m) => m.human.kind === 'adult'); });
  const carryPct = (kind, set) => { const L = c.agents.filter((a) => a.kind === kind); return (100 * L.filter((a) => set.includes(a.human.carry)).length) / L.length; };
  const inFood = carryPct('in', ['popcorn', 'cup']), outFood = carryPct('out', ['popcorn', 'cup']);
  const perMin = (60 * n) / HORIZON;
  // bursts: persons crossing per 30 s window
  const win = new Array(Math.ceil(HORIZON / 30)).fill(0);
  for (const e of c.events) if (e.t < HORIZON) win[Math.floor(e.t / 30)]++;
  const mean = win.reduce((a, b) => a + b, 0) / win.length;
  const cv = Math.sqrt(win.reduce((a, b) => a + (b - mean) ** 2, 0) / win.length) / mean;
  check('traffic ~1 person / 2-3 s', perMin >= 20 && perMin <= 30, { personsPerMin: r3(perMin), secondsPerPerson: r3(HORIZON / n) });
  check('~70 % going in', nIn / n > 0.64 && nIn / n < 0.76, { inPct: r3((100 * nIn) / n), in: nIn, out: n - nIn });
  check('bursts and lulls (per-30 s count varies)', cv > 0.3 && Math.min(...win) <= mean * 0.6 && Math.max(...win) >= mean * 1.6, { per30sMin: Math.min(...win), per30sMean: r3(mean), per30sMax: Math.max(...win), cv: r3(cv) });
  check('children ~12 %, only inside families next to an adult', kidsOk && kids.length / n > 0.08 && kids.length / n < 0.16, { childPct: r3((100 * kids.length) / n) });
  check('~30 % carry popcorn / cup going in, fewer coming out', inFood > 22 && inFood < 38 && outFood < inFood * 0.6, { inPct: r3(inFood), outPct: r3(outFood) });
  const sp = c.agents.filter((a) => a.human.kind === 'adult');
  check('group cruise speeds 0.85..1.45 m/s', c.agents.every((a) => a.speed >= 0.82 && a.speed <= 1.46), { min: Math.min(...c.agents.map((a) => a.speed)), max: Math.max(...c.agents.map((a) => a.speed)) });
  console.log('      group sizes', { singles: sizes[1], pairs: sizes[2], trios: sizes[3], fours: sizes[4] }, 'max people in view', maxVisible, 'max active', maxActive, 'adults', sp.length);
  console.log('      planner', c.stats);
}

// ---------------------------------------------------------------- activeAt index
{
  let bad = 0;
  for (let k = 0; k < 3000; k++) {
    const tt = tMin + ((k * 7.919) % (tMax - tMin));
    const fast = c.activeAt(tt).map((a) => a.id).sort((x, y) => x - y).join(',');
    const slow = c.agents.filter((a) => tt >= a.t0 && tt <= a.t1).map((a) => a.id).sort((x, y) => x - y).join(',');
    if (fast !== slow) bad++;
  }
  let t1 = performance.now(), n = 0;
  for (let k = 0; k < 100000; k++) n += c.activeAt((k * 0.0359) % HORIZON).length;
  const actUs = ((performance.now() - t1) * 1000) / 100000;
  t1 = performance.now();
  let m = 0;
  for (let k = 0; k < 100000; k++) { const tt = (k * 0.0359) % HORIZON; for (const a of c.activeAt(tt)) { c.stateAt(a, tt); m++; } }
  const stUs = ((performance.now() - t1) * 1000) / m;
  check('activeAt matches brute force; fast', bad === 0 && actUs < 20, { mismatches: bad, activeAtMicros: r3(actUs), stateAtMicros: r3(stUs) });
}

console.log(`\n${fails ? 'FAILED' : 'ALL PASSED'}: ${results.length - fails}/${results.length} checks (seed ${SEED}, horizon ${HORIZON} s)`);
process.exit(fails ? 1 : 0);
