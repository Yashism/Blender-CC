// Crowd simulation for the procedural CCTV feed: who walks where and when, and the
// counting-line crossings. Pure JS (no three.js), deterministic from the seed, and
// generated up front for the whole horizon so stateAt(agent, t) is a pure function.
//
// (Written by the lead to unblock integration. Crowd owner: verify against SPEC.md
// and the tests in tests/crowd_*.mjs, then improve in place rather than rewrite.)
//
// World: metres, floor y = 0, camera looks toward -Z. heading 0 = facing +Z.
import { mulberry32 } from './rng.js';

export const LINE_DEFAULT = { z: -3.3, x0: -2.4, x1: 2.4 };

const DS = 0.05;            // path sample spacing (m, along the leader's path)
const Z_SPAWN = 3.6;        // behind/below the camera, outside the frame
const Z_DARK = -8.0;        // deep in the auditorium, fully faded
const MIN_SEP = 0.5;        // body-centre separation kept between different groups (m)
const CHECK_DT = 0.1;       // collision check step (s)

// keep-out boxes [x0, x1, z0, z1] grown by a body radius when checked
const OBSTACLES = [
  [1.975, 2.525, -4.575, -4.125],   // podium
  [2.85, 3.65, -4.35, -3.15],       // stanchions + belt
  [-1.78, -1.28, -5.0, -3.75],      // left door leaf (open into the corridor)
  [1.28, 1.78, -5.0, -3.75],        // right door leaf
];
const BODY_R = 0.25;

const lerp = (a, b, t) => a + (b - a) * t;

// centripetal Catmull-Rom through points [[x, z], ...] -> dense polyline
function catmullRom(pts, perSeg = 24) {
  const P = [pts[0].map((v, i) => 2 * v - pts[1][i]), ...pts, pts[pts.length - 1].map((v, i) => 2 * v - pts[pts.length - 2][i])];
  const out = [];
  for (let i = 1; i < P.length - 2; i++) {
    const [p0, p1, p2, p3] = [P[i - 1], P[i], P[i + 1], P[i + 2]];
    const d = (a, b) => Math.pow(Math.hypot(b[0] - a[0], b[1] - a[1]), 0.5) || 1e-4;
    const t0 = 0, t1 = t0 + d(p0, p1), t2 = t1 + d(p1, p2), t3 = t2 + d(p2, p3);
    for (let k = 0; k < perSeg; k++) {
      const t = t1 + ((t2 - t1) * k) / perSeg;
      const A1 = p0.map((v, j) => ((t1 - t) / (t1 - t0)) * v + ((t - t0) / (t1 - t0)) * p1[j]);
      const A2 = p1.map((v, j) => ((t2 - t) / (t2 - t1)) * v + ((t - t1) / (t2 - t1)) * p2[j]);
      const A3 = p2.map((v, j) => ((t3 - t) / (t3 - t2)) * v + ((t - t2) / (t3 - t2)) * p3[j]);
      const B1 = A1.map((v, j) => ((t2 - t) / (t2 - t0)) * v + ((t - t0) / (t2 - t0)) * A2[j]);
      const B2 = A2.map((v, j) => ((t3 - t) / (t3 - t1)) * v + ((t - t1) / (t3 - t1)) * A3[j]);
      out.push(B1.map((v, j) => ((t2 - t) / (t2 - t1)) * v + ((t - t1) / (t2 - t1)) * B2[j]));
    }
  }
  out.push(pts[pts.length - 1]);
  return out;
}

// resample a polyline to uniform spacing DS; returns { x: Float32Array, z: Float32Array, len }
function resample(poly) {
  const cum = [0];
  for (let i = 1; i < poly.length; i++) cum.push(cum[i - 1] + Math.hypot(poly[i][0] - poly[i - 1][0], poly[i][1] - poly[i - 1][1]));
  const len = cum[cum.length - 1];
  const n = Math.floor(len / DS) + 1;
  const x = new Float32Array(n), z = new Float32Array(n);
  let j = 0;
  for (let i = 0; i < n; i++) {
    const s = i * DS;
    while (j < cum.length - 2 && cum[j + 1] < s) j++;
    const f = (s - cum[j]) / Math.max(1e-6, cum[j + 1] - cum[j]);
    x[i] = lerp(poly[j][0], poly[j + 1][0], Math.min(1, f));
    z[i] = lerp(poly[j][1], poly[j + 1][1], Math.min(1, f));
  }
  return { x, z, len: (n - 1) * DS };
}

// a member walking beside/behind the leader: offset the leader samples along the normal
function offsetPath(lead, lateral, back) {
  const n = lead.x.length;
  const x = new Float32Array(n), z = new Float32Array(n), dist = new Float32Array(n);
  const shift = Math.round(back / DS);
  for (let i = 0; i < n; i++) {
    const k = i - shift;
    let px, pz, tx, tz;
    if (k >= 0) {
      const a = Math.min(k, n - 2);
      tx = lead.x[a + 1] - lead.x[a]; tz = lead.z[a + 1] - lead.z[a];
      px = lead.x[k]; pz = lead.z[k];
    } else { // before the leader's start: extend straight back along the first tangent
      tx = lead.x[1] - lead.x[0]; tz = lead.z[1] - lead.z[0];
      const l = Math.hypot(tx, tz) || 1;
      px = lead.x[0] + (tx / l) * k * DS; pz = lead.z[0] + (tz / l) * k * DS;
    }
    const l = Math.hypot(tx, tz) || 1;
    // normal pointing to the walker's right
    const nx = -tz / l, nz = tx / l;
    x[i] = px + nx * lateral; z[i] = pz + nz * lateral;
    dist[i] = i ? dist[i - 1] + Math.hypot(x[i] - x[i - 1], z[i] - z[i - 1]) : 0;
  }
  return { x, z, dist };
}

export function createCrowd({ seed = 7, horizon = 3600, line = LINE_DEFAULT } = {}) {
  const rnd = mulberry32(seed * 7919 + 13);
  const R = (a, b) => a + (b - a) * rnd();
  const pick = (arr) => arr[Math.floor(rnd() * arr.length)];

  const agents = [];
  const groups = [];
  let nextId = 1;
  const buckets = []; // per second: agents active in [k, k+1)

  function addToBuckets(a) {
    for (let k = Math.max(0, Math.floor(a.t0)); k <= Math.floor(a.t1); k++) (buckets[k] ||= []).push(a);
  }

  // leader time -> leader arc length: gentle speed wobble, always moving forward
  function makeClock(v, rr) {
    const amp = 0.05, w = (2 * Math.PI) / R(3.2, 5.0), ph = rr * Math.PI * 2;
    const s = (tau) => v * tau + ((v * amp) / w) * (Math.sin(w * tau + ph) - Math.sin(ph));
    const ds = (tau) => v * (1 + amp * Math.cos(w * tau + ph));
    return { s, ds };
  }

  function sampleAt(arr, s) {
    const f = s / DS;
    const i = Math.max(0, Math.min(arr.length - 2, Math.floor(f)));
    const u = Math.max(0, Math.min(1, f - i));
    return lerp(arr[i], arr[i + 1], u);
  }

  function pos(a, t) {
    const tau = t - a.g.t0;
    const s = a.g.clock.s(tau);
    return [sampleAt(a.x, s), sampleAt(a.z, s), s];
  }

  function obstacleClear(x, z) {
    for (const [x0, x1, z0, z1] of OBSTACLES) {
      if (x > x0 - BODY_R && x < x1 + BODY_R && z > z0 - BODY_R && z < z1 + BODY_R) return false;
    }
    return true;
  }

  // build a candidate group (not yet accepted)
  function makeGroup(t0, kind) {
    const u = rnd();
    const size = u < 0.45 ? 1 : u < 0.8 ? 2 : u < 0.92 ? 3 : 4;
    const v = size === 1 ? R(1.15, 1.42) : size === 2 ? R(1.05, 1.3) : R(0.92, 1.12);
    // members: [lateral, back, human]
    const sexA = rnd() < 0.5 ? 'm' : 'f';
    const other = sexA === 'm' ? 'f' : 'm';
    let members;
    if (size === 1) members = [[0, 0, { kind: 'adult', sex: sexA }]];
    else if (size === 2) members = [[-0.3, 0, { kind: 'adult', sex: sexA }], [0.3, 0, { kind: 'adult', sex: rnd() < 0.75 ? other : sexA }]];
    else if (size === 3) members = [[-0.3, 0, { kind: 'adult', sex: 'm' }], [0.3, 0, { kind: 'adult', sex: 'f' }], [0, 0.8, { kind: 'child', sex: rnd() < 0.5 ? 'm' : 'f' }]];
    else members = [[-0.3, 0, { kind: 'adult', sex: 'm' }], [0.3, 0, { kind: 'child', sex: rnd() < 0.5 ? 'm' : 'f' }], [-0.3, 0.85, { kind: 'adult', sex: 'f' }], [0.3, 0.85, rnd() < 0.5 ? { kind: 'child', sex: 'f' } : { kind: 'adult', sex: 'm' }]];
    for (const m of members) {
      const h = m[2];
      const r = rnd();
      if (h.kind === 'child') h.carry = r < 0.3 && kind === 'in' ? 'cup' : null;
      else if (kind === 'in') h.carry = r < 0.2 ? 'popcorn' : r < 0.32 ? 'cup' : r < 0.45 && h.sex === 'f' ? 'bag' : r < 0.55 ? 'phone' : null;
      else h.carry = r < 0.05 ? 'popcorn' : r < 0.14 ? 'cup' : r < 0.3 && h.sex === 'f' ? 'bag' : r < 0.45 ? 'phone' : null;
    }
    // leader route: from the bottom edge to the doorway lane (in), or the reverse (out)
    // keep to a side of the doorway: in on the left half, out on the right half (as seen by the camera)
    const wide = size > 1 ? 0.3 : 0;
    const doorX = kind === 'in' ? R(-0.85 + wide, -0.12 - wide * 0.4) : R(0.12 + wide * 0.4, 0.85 - wide);
    const edgeX = R(-3.4, 3.4);
    const midX = lerp(edgeX, doorX, R(0.45, 0.7)) + R(-0.3, 0.3);
    const route = [
      [edgeX, Z_SPAWN],
      [lerp(edgeX, midX, 0.5), 0.6],
      [midX, -1.9],
      [doorX, -4.1],
      [doorX * 0.9, -5.2],
      [doorX * 0.6 + R(-0.6, 0.6), Z_DARK],
      [doorX * 0.6 + R(-0.6, 0.6), Z_DARK - 1.6], // run-out so followers also reach the dark
    ];
    if (kind === 'out') { route.reverse(); route.push([route[route.length - 1][0] + R(-0.4, 0.4), Z_SPAWN + 1.4]); route.shift(); }
    const lead = resample(catmullRom(route));
    const g = { t0, kind, v, clock: makeClock(v, rnd()), lead, members: [] };
    g.t1 = t0 + lead.len / (v * 0.95);
    for (const [lat, back, human] of members) {
      const p = lat === 0 && back === 0 ? { x: lead.x, z: lead.z, dist: Float32Array.from(lead.x, (_, i) => i * DS) } : offsetPath(lead, lat, back);
      g.members.push({ x: p.x, z: p.z, dist: p.dist, human, back, lat, g });
    }
    return g;
  }

  function groupOk(g) {
    // obstacles + other groups
    for (const m of g.members) {
      for (let i = 0; i < m.x.length; i += 4) {
        if (m.z[i] > -5.0 && m.z[i] < 3.0 && !obstacleClear(m.x[i], m.z[i])) return false;
        if (m.z[i] < -5.0 && Math.abs(m.x[i]) > 1.1 && m.z[i] > -5.6) return false; // through the door frame
      }
    }
    const others = new Set();
    for (let k = Math.floor(g.t0); k <= Math.ceil(g.t1); k++) for (const a of buckets[k] || []) others.add(a);
    if (!others.size) return true;
    for (let t = g.t0; t <= g.t1; t += CHECK_DT) {
      for (const m of g.members) {
        const [x, z] = pos(m, t);
        if (z < -7.2) continue; // deep in the dark auditorium: invisible
        for (const o of others) {
          if (t < o.t0 || t > o.t1) continue;
          const [ox, oz] = pos(o, t);
          if (oz < -7.2) continue;
          if ((x - ox) ** 2 + (z - oz) ** 2 < MIN_SEP * MIN_SEP) return false;
        }
      }
    }
    return true;
  }

  // arrivals: bursts and lulls around ~1 person every 2.5 s
  let t = 0.6;
  const burstPhase = rnd() * Math.PI * 2;
  while (t < horizon) {
    const rate = (1 / 4.4) * (1 + 0.65 * Math.sin((2 * Math.PI * t) / 75 + burstPhase)); // groups per second
    t += -Math.log(1 - rnd() * 0.999) / Math.max(0.05, rate);
    // the group keeps its direction; if the way is blocked it tries other lanes, then waits
    const kind = rnd() < 0.7 ? 'in' : 'out';
    let g = null;
    for (let attempt = 0; attempt < 60 && !g; attempt++) {
      const cand = makeGroup(t + Math.floor(attempt / 4) * 0.7, kind);
      if (groupOk(cand)) g = cand;
    }
    if (!g) continue;
    g.id = groups.length;
    groups.push(g);
    for (const m of g.members) {
      const a = {
        id: nextId++, seed: Math.floor(rnd() * 2 ** 31), kind: g.kind, group: g.id,
        t0: g.t0, t1: g.t1, human: m.human, speed: g.v,
        x: m.x, z: m.z, dist: m.dist, back: m.back, g,
      };
      agents.push(a);
      addToBuckets(a);
    }
    t = Math.max(t, g.t0);
  }
  agents.sort((a, b) => a.t0 - b.t0 || a.id - b.id);

  // crossing events: the member's own path crossing line.z
  const events = [];
  for (const a of agents) {
    for (let i = 1; i < a.z.length; i++) {
      const z0 = a.z[i - 1], z1 = a.z[i];
      if ((z0 - line.z) * (z1 - line.z) > 0 || z0 === z1) continue;
      const f = (line.z - z0) / (z1 - z0);
      const s = (i - 1 + f) * DS;
      const x = lerp(a.x[i - 1], a.x[i], f);
      // invert the leader clock (monotonic) to get the time
      let lo = 0, hi = a.t1 - a.t0;
      for (let k = 0; k < 40; k++) { const mid = (lo + hi) / 2; if (a.g.clock.s(mid) < s) lo = mid; else hi = mid; }
      if (x >= line.x0 && x <= line.x1) events.push({ t: a.t0 + lo, id: a.id, dir: z1 < z0 ? 'in' : 'out', x, z: line.z });
      break;
    }
  }
  events.sort((a, b) => a.t - b.t);

  function heading(a, s) {
    const i = Math.max(0, Math.min(a.x.length - 2, Math.floor(s / DS)));
    const j = Math.min(a.x.length - 1, i + 3), k = Math.max(0, i - 3);
    return Math.atan2(a.x[j] - a.x[k], a.z[j] - a.z[k]);
  }
  const wrap = (d) => Math.atan2(Math.sin(d), Math.cos(d));

  function stateAt(a, t) {
    if (t < a.t0 || t > a.t1) return null;
    const tau = t - a.t0;
    const s = Math.min(a.g.clock.s(tau), (a.x.length - 1) * DS);
    const x = sampleAt(a.x, s), z = sampleAt(a.z, s);
    const dist = sampleAt(a.dist, s);
    const h = heading(a, s);
    const sp = a.g.clock.ds(tau);
    const ds2 = sp * 0.15;
    const turnRate = wrap(heading(a, s + ds2) - heading(a, Math.max(0, s - ds2))) / 0.3;
    // fade in/out in the dark auditorium; walkers behind the camera are outside the frame anyway
    const alpha = Math.max(0, Math.min(1, (z - Z_DARK) / 2.2));
    return { x, z, heading: h, speed: sp * (a.dist[a.dist.length - 1] / Math.max(1e-3, (a.x.length - 1) * DS)), dist, turnRate, alpha };
  }

  function activeAt(t) {
    const b = buckets[Math.floor(t)] || [];
    return b.filter((a) => t >= a.t0 && t <= a.t1);
  }

  return { agents, stateAt, activeAt, events, line };
}
