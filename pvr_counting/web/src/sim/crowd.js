// Crowd simulation for the procedural CCTV feed: who walks where and when, and the
// counting-line crossings. Pure JS (no three.js). Everything is planned up front for
// the whole horizon from the seed, so stateAt(agent, t) is a pure function of t.
//
//   createCrowd({ seed = 7, horizon = 3600, line = LINE }) -> {
//     agents,            // [{ id, seed, kind: 'in'|'out', group, t0, t1, human: {kind, sex, carry}, speed }]
//     stateAt(agent, t), // null if inactive, else { x, z, heading, speed, dist, turnRate, alpha, y, ndist, strideK }
//     activeAt(t),       // agents active at t (per-second index)
//     events,            // [{ t, id, dir: 'in'|'out', x, z }] sorted by t, exactly one per agent
//     line, stats, groupInfo(groupId)
//   }
//   heading: yaw about +Y (three.js rotation.y), 0 = facing +Z (toward the camera)
//   speed: m/s of this person; dist: metres this person walked since t0 (phase = dist / stride)
//   turnRate: d(heading)/dt in rad/s; alpha: 0..1 fade into the dark auditorium / behind
//   the door wall; y: floor height under the person (0 except on the auditorium steps).
//   strideK: stride factor at this speed (people shorten their stride when they walk slowly:
//   strideK = strideFactor(speed)); ndist: integral of speed / strideK dt. With a person's
//   full stride S the walk phase is ndist / S, and stride * dphase/dt = speed (no sliding).
//   Extra option: preroll (s, default 16) plans arrivals before t = 0 so the room is not
//   empty at T = 0; such groups are kept only if they cross the line after t = 0, so every
//   event has t > 0 and the counters start at zero. Agents may have t0 < 0.
//
// How it works
//  - Groups (singles, couples, friends, families with kids) arrive by an inhomogeneous
//    Poisson process with slow bursts and lulls (~1 person / 2.5 s, ~70 % going in).
//  - Each group gets a route: a centre line (centripetal Catmull-Rom through a few
//    waypoints, Gaussian-smoothed, arc-length resampled) from behind the camera or the
//    bottom corners through the doorway, then down the dark centre aisle or along the
//    cross-aisle landing behind the door wall; people coming out do the reverse. In the
//    open corridor everybody keeps a little to their left, at the door each flow keeps its
//    own half of the opening. Members walk offset curves of the centre line (side by side,
//    kids next to an adult, staggered rows) at a shared pace; groups heading down the
//    narrow aisle string out into single file on the landing (and fan out again coming out).
//  - Speed along the path: cruise speed with smooth noise, slower at the door and in the
//    dark, turn-rate and lateral-acceleration limits on curves, occasional short pauses
//    (checking a phone, a family regrouping) never near the counting line, gentle
//    accel/decel (forward/backward passes), integrated to a 0.05 s time grid.
//  - Prioritised planning: each new group is checked against everyone already planned on
//    the 0.05 s grid (comfortable passing distance, a longer gap when following). On a
//    conflict it sidesteps (smooth lateral bump) or yields (slows a little before the
//    spot), tries other lanes, and only then starts later: start points are out of frame
//    or in the dark, so waiting there is invisible.
import { mulberry32, hash2, smoothNoise1 } from './rng.js';

export const LINE_DEFAULT = { z: -3.3, x0: -2.4, x1: 2.4 };
export const LINE = LINE_DEFAULT;

// ---------------------------------------------------------------------------------
// Room geometry, mirrored from environment.js (OBSTACLES, WALKABLE, DOOR, auditorium).
// tests/crowd_verify.mjs checks that these stay in sync with the environment.
const rad = (d) => (d * Math.PI) / 180;
export const CROWD_GEOMETRY = {
  walkable: [[-4.5, 3.6], [-3.6, 1.0], [-3.88, -4.02], [-2.88, -4.82], [4.86, -4.82], [4.92, 1.0], [4.95, 3.6]],
  door: { x0: -1.3, x1: 1.3, zFace: -4.82, zBack: -5.3 },
  landing: { zEnd: -7.4, half: 6.8 },   // cross-aisle landing inside the auditorium
  aisleHalf: 0.9,                        // centre aisle between the seat rows (z < landing.zEnd)
  obstacles: [
    { kind: 'box', name: 'podium', cx: 2.4, cz: -3.98, w: 0.6, d: 0.48 },
    { kind: 'circle', name: 'stanchionA', x: 3.12, z: -4.12, r: 0.18 },
    { kind: 'circle', name: 'stanchionB', x: 3.23, z: -2.6, r: 0.18 },
    { kind: 'circle', name: 'stanchionC', x: 3.98, z: -3.28, r: 0.18 },
    { kind: 'segment', name: 'beltAB', x0: 3.12, z0: -4.12, x1: 3.23, z1: -2.6 },
    { kind: 'segment', name: 'beltBC', x0: 3.23, z0: -2.6, x1: 3.98, z1: -3.28 },
    { kind: 'segment', name: 'leafL', x0: -1.3, z0: -4.96, x1: -1.3 + 1.27 * Math.cos(rad(106.6)), z1: -4.96 + 1.27 * Math.sin(rad(106.6)) },
    { kind: 'segment', name: 'leafR', x0: 1.3, z0: -4.96, x1: 1.3 - 1.27 * Math.cos(rad(104.5)), z1: -4.96 + 1.27 * Math.sin(rad(104.5)) },
  ],
};

// clearances: body centre to surface (m)
export const CLEARANCE = { wall: 0.3, seat: 0.3, box: 0.36, circle: 0.3, belt: 0.3, leaf: 0.34 };

// ---------------------------------------------------------------------------------
// tuning
const DS = 0.1;             // path sample spacing (m of group progress)
const H = 0.05;             // time grid (s); planning checks run on this grid
const EXT = 0.15;           // straight run-in / run-out at both ends (+ formation depth) (m)
const Z_SPAWN = 3.7;        // behind the camera (camera at z ~ 2.9)
const Z_AISLE_END = -8.5;   // far enough into the dark aisle that alpha is 0
const X_SIDE_END = 2.85;    // cross-aisle exits, behind the door wall (occluded, alpha 0)
const Z_SIDE = -6.4;

const SEP_PASS = 0.66;      // planned centre distance between people of different groups
const SEP_DOOR = 0.58;      // ... squeezing past each other in the doorway
const SEP_FOLLOW = 0.92;    // ... when one walks behind the other in the same direction
const SEP_HIDDEN = 0.52;    // ... both deep in the dark aisle, or both behind the camera
const SEP_GROUP = 0.48;     // within a group (formation), checked along the path (adult pairs walk 0.62 apart)
const COARSE = SEP_FOLLOW + 0.18; // coarse-step skip distance (max closing speed 3.6 m/s x 0.05 s)

const OMEGA_MAX = 1.15;     // rad/s turn rate limit
const OMEGA_NEAR = 0.8;     // ... in the lit corridor in view (tight turns make the planted foot slip)
const V_MIN_VIEW = 0.55;    // nobody stands still or crawls in the open corridor: yields slow to this at most
const A_LAT = 0.85;         // m/s^2 lateral acceleration limit
const A_ACC = 0.42;         // m/s^2 speeding up
const A_DEC = 0.55;         // m/s^2 slowing down
const V_MEMBER_MAX = 1.65;  // outer member of a turning group never runs

const FILE_GAP = 0.72;      // spacing when a group walks single file
const KEEP_LEFT = 0.36;     // corridor lane offset to the walker's left (m)
const MAX_DELAY = 30;       // s a group may wait (out of view) before it is dropped
const DELAY_STEP = 0.35;
const LAMBDA_PERSONS = 1 / 2.35; // mean arrivals, persons per second

// ---------------------------------------------------------------------------------
// small helpers
const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);
const lerp = (a, b, t) => a + (b - a) * t;
// stride factor vs walking speed (1 = the person's full stride at a brisk walk)
export function strideFactor(v) { return clamp(0.55 + 0.35 * v, 0.6, 1.0); }
function ss(e0, e1, x) { let t = (x - e0) / (e1 - e0); t = t < 0 ? 0 : t > 1 ? 1 : t; return t * t * (3 - 2 * t); }
const gauss = (r) => (r() + r() + r() + r() - 2) * 1.7320508; // ~N(0, 1), bounded
const wrapPi = (a) => a - 2 * Math.PI * Math.floor((a + Math.PI) / (2 * Math.PI));
const hyp = (x, z) => Math.sqrt(x * x + z * z);

function segDist(px, pz, x0, z0, x1, z1) {
  const dx = x1 - x0, dz = z1 - z0;
  const l2 = dx * dx + dz * dz;
  let t = l2 > 0 ? ((px - x0) * dx + (pz - z0) * dz) / l2 : 0;
  t = t < 0 ? 0 : t > 1 ? 1 : t;
  const ex = px - (x0 + dx * t), ez = pz - (z0 + dz * t);
  return Math.sqrt(ex * ex + ez * ez);
}

// ---------------------------------------------------------------------------------
// static environment: where a body centre may be
export function buildStatic(geo = CROWD_GEOMETRY) {
  const W = geo.walkable;
  const d = geo.door;
  const zTop = W[0][1];
  const walls = [];
  for (let i = 0; i < W.length - 1; i++) {
    const [ax, az] = W[i], [bx, bz] = W[i + 1];
    if (Math.abs(az - d.zFace) < 1e-6 && Math.abs(bz - d.zFace) < 1e-6) {
      walls.push([ax, az, d.x0, az], [d.x1, bz, bx, bz]); // door wall, doorway left open
    } else walls.push([ax, az, bx, bz]);
  }
  walls.push([d.x0, d.zFace, d.x0, d.zBack], [d.x1, d.zFace, d.x1, d.zBack]);      // jambs
  walls.push([-geo.landing.half, d.zBack, d.x0, d.zBack], [d.x1, d.zBack, geo.landing.half, d.zBack]); // inner side of the door wall
  const seats = [
    [-geo.aisleHalf, geo.landing.zEnd, -geo.aisleHalf, -40], [geo.aisleHalf, geo.landing.zEnd, geo.aisleHalf, -40],
    [-geo.landing.half, geo.landing.zEnd, -geo.aisleHalf, geo.landing.zEnd], [geo.aisleHalf, geo.landing.zEnd, geo.landing.half, geo.landing.zEnd],
  ];
  const segs = [];
  const addSeg = (x0, z0, x1, z1, need) => segs.push({ x0, z0, x1, z1, need, bx0: Math.min(x0, x1) - need, bx1: Math.max(x0, x1) + need, bz0: Math.min(z0, z1) - need, bz1: Math.max(z0, z1) + need });
  for (const w of walls) addSeg(w[0], w[1], w[2], w[3], CLEARANCE.wall);
  for (const s of seats) addSeg(s[0], s[1], s[2], s[3], CLEARANCE.seat);
  for (const o of geo.obstacles) if (o.kind === 'segment') addSeg(o.x0, o.z0, o.x1, o.z1, o.name.startsWith('leaf') ? CLEARANCE.leaf : CLEARANCE.belt);
  const boxes = geo.obstacles.filter((o) => o.kind === 'box');
  const circles = geo.obstacles.filter((o) => o.kind === 'circle');

  function insidePoly(x, z) {
    let c = false;
    for (let i = 0, j = W.length - 1; i < W.length; j = i++) {
      const xi = W[i][0], zi = W[i][1], xj = W[j][0], zj = W[j][1];
      if ((zi > z) !== (zj > z) && x < ((xj - xi) * (z - zi)) / (zj - zi) + xi) c = !c;
    }
    return c;
  }
  function region(x, z) {
    if (z > zTop) return Math.abs(x) < 5.6;            // lobby behind the camera (out of frame)
    if (z >= d.zFace) return insidePoly(x, z);
    if (z >= d.zBack) return x > d.x0 && x < d.x1;     // doorway
    if (z >= geo.landing.zEnd) return Math.abs(x) < geo.landing.half;
    return Math.abs(x) < geo.aisleHalf;
  }
  // signed clearance (m): >= 0 means a body centre fits here. Exact when < ~0.3.
  function clearance(x, z) {
    if (!region(x, z)) return -1;
    let c = 1;
    for (let i = 0; i < segs.length; i++) {
      const q = segs[i];
      if (x < q.bx0 || x > q.bx1 || z < q.bz0 || z > q.bz1) continue;
      const v = segDist(x, z, q.x0, q.z0, q.x1, q.z1) - q.need;
      if (v < c) c = v;
    }
    for (const o of boxes) {
      const dx = Math.max(0, Math.abs(x - o.cx) - o.w / 2), dz = Math.max(0, Math.abs(z - o.cz) - o.d / 2);
      c = Math.min(c, hyp(dx, dz) - CLEARANCE.box);
    }
    for (const o of circles) c = Math.min(c, hyp(x - o.x, z - o.z) - o.r - CLEARANCE.circle);
    return c;
  }
  // cached lookup: clearance is 1-Lipschitz, so a 5 cm grid value >= 0.036 proves the
  // spot is free; anything closer is computed exactly
  const G0x = -5.6, G0z = -10.5, GS = 0.05, GW = 225, GH = 330;
  let grid = null;
  function ok(x, z) {
    const i = Math.round((x - G0x) / GS), k = Math.round((z - G0z) / GS);
    if (i < 0 || k < 0 || i >= GW || k >= GH) return clearance(x, z) >= 0;
    if (!grid) {
      grid = new Float32Array(GW * GH);
      for (let kk = 0; kk < GH; kk++) for (let ii = 0; ii < GW; ii++) grid[kk * GW + ii] = clearance(G0x + ii * GS, G0z + kk * GS);
    }
    const g = grid[k * GW + i];
    if (g >= 0.036) return true;
    if (g < -0.036) return false;
    return clearance(x, z) >= 0;
  }
  return { clearance, region, ok };
}

// floor height under a walker: the aisle steps down 0.1 m per 1 m row past the landing
function floorY(geo, x, z) {
  if (z > geo.landing.zEnd + 0.5 || Math.abs(x) > geo.aisleHalf) return 0;
  const dd = geo.landing.zEnd - z;
  const n = Math.max(0, Math.floor(dd + 0.5));
  return -0.1 * (n + ss(-0.15, 0.15, dd - n));
}

// visibility fade: into the dark auditorium, and sideways behind the door wall
function alphaAt(geo, x, z) {
  let a = ss(-8.25, -5.6, z);
  if (z < geo.door.zBack) a *= 1 - ss(1.75, 2.6, Math.abs(x));
  return a;
}

// ---------------------------------------------------------------------------------
// paths

// centripetal Catmull-Rom through points [[x, z], ...] -> dense xs, zs
function catmullRom(pts) {
  const n = pts.length;
  const P = [[2 * pts[0][0] - pts[1][0], 2 * pts[0][1] - pts[1][1]], ...pts,
    [2 * pts[n - 1][0] - pts[n - 2][0], 2 * pts[n - 1][1] - pts[n - 2][1]]];
  const xs = [], zs = [];
  const knot = (a, b) => Math.max(1e-4, Math.sqrt(hyp(b[0] - a[0], b[1] - a[1])));
  for (let i = 1; i < P.length - 2; i++) {
    const p0 = P[i - 1], p1 = P[i], p2 = P[i + 1], p3 = P[i + 2];
    const t0 = 0, t1 = knot(p0, p1), t2 = t1 + knot(p1, p2), t3 = t2 + knot(p2, p3);
    const m = Math.max(4, Math.ceil(hyp(p2[0] - p1[0], p2[1] - p1[1]) / 0.025));
    for (let k = 0; k < m; k++) {
      const t = t1 + ((t2 - t1) * k) / m;
      for (let c = 0; c < 2; c++) {
        const A1 = ((t1 - t) * p0[c] + (t - t0) * p1[c]) / (t1 - t0);
        const A2 = ((t2 - t) * p1[c] + (t - t1) * p2[c]) / (t2 - t1);
        const A3 = ((t3 - t) * p2[c] + (t - t2) * p3[c]) / (t3 - t2);
        const B1 = ((t2 - t) * A1 + (t - t0) * A2) / (t2 - t0);
        const B2 = ((t3 - t) * A2 + (t - t1) * A3) / (t3 - t1);
        (c ? zs : xs).push(((t2 - t) * B1 + (t - t1) * B2) / (t2 - t1));
      }
    }
  }
  xs.push(pts[n - 1][0]); zs.push(pts[n - 1][1]);
  return { xs, zs };
}

// uniform arc-length resampling (spacing DS)
function resample(xs, zs) {
  const n = xs.length;
  const cum = new Float64Array(n);
  for (let i = 1; i < n; i++) cum[i] = cum[i - 1] + hyp(xs[i] - xs[i - 1], zs[i] - zs[i - 1]);
  const m = Math.floor(cum[n - 1] / DS) + 1;
  const X = new Float64Array(m), Z = new Float64Array(m);
  let j = 0;
  for (let i = 0; i < m; i++) {
    const s = i * DS;
    while (j < n - 2 && cum[j + 1] < s) j++;
    const seg = cum[j + 1] - cum[j];
    const f = seg > 1e-12 ? clamp((s - cum[j]) / seg, 0, 1) : 0;
    X[i] = xs[j] + (xs[j + 1] - xs[j]) * f;
    Z[i] = zs[j] + (zs[j + 1] - zs[j]) * f;
  }
  return { x: X, z: Z, n: m };
}

// Gaussian smoothing along the path; ends are padded by linear extrapolation
function smoothPath(p, sigma) {
  const r = Math.ceil((2.5 * sigma) / DS);
  const w = new Float64Array(2 * r + 1);
  let ws = 0;
  for (let k = -r; k <= r; k++) { w[k + r] = Math.exp(-0.5 * ((k * DS) / sigma) ** 2); ws += w[k + r]; }
  const n = p.n, X = new Float64Array(n), Z = new Float64Array(n);
  const px = p.x, pz = p.z;
  for (let i = 0; i < n; i++) {
    let sx = 0, sz = 0;
    for (let k = -r; k <= r; k++) {
      const j = i + k;
      let vx, vz;
      if (j < 0) { vx = px[0] + (px[0] - px[1]) * -j; vz = pz[0] + (pz[0] - pz[1]) * -j; }
      else if (j >= n) { vx = px[n - 1] + (px[n - 1] - px[n - 2]) * (j - n + 1); vz = pz[n - 1] + (pz[n - 1] - pz[n - 2]) * (j - n + 1); }
      else { vx = px[j]; vz = pz[j]; }
      sx += w[k + r] * vx; sz += w[k + r] * vz;
    }
    X[i] = sx / ws; Z[i] = sz / ws;
  }
  return resample(X, Z);
}

// unit tangents (central differences)
function tangents(p) {
  const n = p.n, tx = new Float64Array(n), tz = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const a = Math.max(0, i - 1), b = Math.min(n - 1, i + 1);
    const dx = p.x[b] - p.x[a], dz = p.z[b] - p.z[a], l = hyp(dx, dz) || 1;
    tx[i] = dx / l; tz[i] = dz / l;
  }
  p.tx = tx; p.tz = tz;
  return p;
}

// lateral offset b(s) (+ = walker's right) applied along the normals, then resampled
function offsetPath(p, fn) {
  const n = p.n, X = new Float64Array(n), Z = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    const b = fn(i * DS, p.x[i], p.z[i]);
    X[i] = p.x[i] - p.tz[i] * b;
    Z[i] = p.z[i] + p.tx[i] * b;
  }
  return tangents(resample(X, Z));
}

// ---------------------------------------------------------------------------------
// groups

function makeHuman(r, kind, age, sexHint) {
  const sex = sexHint || (r() < 0.5 ? 'm' : 'f');
  const u = r();
  let carry = null;
  if (age === 'child') {
    if (kind === 'in') carry = u < 0.2 ? 'popcorn' : u < 0.35 ? 'cup' : null;
    else carry = u < 0.06 ? 'cup' : null;
  } else if (kind === 'in') {
    carry = u < 0.17 ? 'popcorn' : u < 0.31 ? 'cup' : u < (sex === 'f' ? 0.49 : 0.35) ? 'bag' : u < (sex === 'f' ? 0.58 : 0.45) ? 'phone' : null;
  } else {
    carry = u < 0.04 ? 'popcorn' : u < 0.12 ? 'cup' : u < (sex === 'f' ? 0.3 : 0.16) ? 'bag' : u < (sex === 'f' ? 0.44 : 0.31) ? 'phone' : null;
  }
  return { kind: age, sex, carry };
}

// composition + formation. lat: + = walker's right; back: metres behind the front row.
function composeGroup(r, kind) {
  const u = r();
  const size = kind === 'in' ? (u < 0.38 ? 1 : u < 0.72 ? 2 : u < 0.87 ? 3 : 4) : (u < 0.58 ? 1 : u < 0.88 ? 2 : u < 0.96 ? 3 : 4);
  const A = (sex, lat, back) => ({ age: 'adult', sex, lat, back });
  const C = (lat, back) => ({ age: 'child', sex: null, lat, back });
  const anySex = () => (r() < 0.5 ? 'm' : 'f');
  const sexA = anySex(), sexB = sexA === 'm' ? 'f' : 'm';
  let type, mem;
  if (size === 1) { type = 'single'; mem = [A(sexA, 0, 0)]; }
  else if (size === 2) {
    if (r() < 0.07) { type = 'family'; mem = [A(sexA, -0.29, 0), C(0.27, 0.03 + 0.05 * r())]; }
    else { type = r() < 0.7 ? 'couple' : 'friends'; mem = [A(sexA, -0.31, 0), A(type === 'couple' ? sexB : sexA, 0.31, 0.1 * r() - 0.05)]; }
  } else if (size === 3) {
    const v = r();
    if (r() < 0.7) {
      type = 'family';
      if (v < 0.25) mem = [A(sexA, -0.52, 0), C(0, 0.05), A(sexB, 0.52, 0.04)];          // kid between the parents
      else if (v < 0.8) mem = [A(sexA, -0.28, 0), C(0.28, 0.04), A(sexB, 0, 0.95)];      // parent + kid, parent behind
      else mem = [C(-0.5, 0.04), A(sexA, 0, 0), C(0.5, 0.06)];                           // one parent, two kids
    } else {
      type = 'friends';
      if (v < 0.3) mem = [A(sexA, -0.62, 0), A(anySex(), 0, 0.12), A(anySex(), 0.62, 0.02)];
      else mem = [A(sexA, -0.31, 0), A(anySex(), 0.31, 0.05), A(anySex(), 0, 0.95)];
    }
  } else if (r() < 0.75) {
    type = 'family';
    const v = r();
    if (v < 0.5) mem = [A(sexA, -0.29, 0), C(0.27, 0.03), A(sexB, -0.29, 0.95), C(0.27, 0.98)];
    else if (v < 0.8) mem = [A(sexA, -0.29, 0), C(0.27, 0.04), A(sexB, -0.31, 0.95), A(anySex(), 0.31, 0.97)];
    else mem = [C(-0.27, 0.02), A(sexA, 0.29, 0), A(sexB, -0.31, 0.96), A(anySex(), 0.31, 0.94)];
  } else {
    type = 'friends';
    mem = [A(sexA, -0.31, 0), A(anySex(), 0.31, 0.06), A(anySex(), -0.31, 0.96), A(anySex(), 0.31, 1.0)];
  }
  if (r() < 0.5) for (const m of mem) m.lat = -m.lat;
  const humans = mem.map((m) => makeHuman(r, kind, m.age, m.sex));
  const hasKid = mem.some((m) => m.age === 'child');
  let cruise;
  if (hasKid) cruise = clamp(0.98 + 0.07 * gauss(r), 0.85, 1.12);
  else if (size === 1) cruise = clamp(1.27 + 0.1 * gauss(r), 1.05, 1.45);
  else if (size === 2) cruise = clamp(1.17 + 0.08 * gauss(r), 1.0, 1.36);
  else cruise = clamp(1.12 + 0.07 * gauss(r), 1.0, 1.3);
  if (kind === 'out') cruise *= 0.97;
  const half = Math.max(...mem.map((m) => Math.abs(m.lat)));
  // single-file order for the narrow aisle: row by row, left to right within a row.
  // B(tLong) = back + tLong * dF keeps the group's mean position fixed while it strings out.
  const order = mem.map((m, i) => i).sort((a, b) => Math.round(mem[a].back / 0.5) - Math.round(mem[b].back / 0.5) || mem[a].lat - mem[b].lat);
  order.forEach((mi, rank) => { mem[mi].backF = rank * FILE_GAP; });
  const meanB = mem.reduce((a, m) => a + m.back, 0) / mem.length;
  const meanF = mem.reduce((a, m) => a + m.backF, 0) / mem.length;
  for (const m of mem) m.dF = m.backF - m.back - (meanF - meanB);
  return { size, type, mem, humans, cruise, half, meanB };
}

function setDepth(G, file) {
  G.useFile = file && G.size > 1;
  let bmax = -Infinity, bmin = Infinity;
  for (const m of G.mem) {
    for (const B of G.useFile ? [m.back, m.back + m.dF] : [m.back]) { bmax = Math.max(bmax, B); bmin = Math.min(bmin, B); }
  }
  G.Bmax = bmax;
  G.depth = bmax - bmin;
}

// ---------------------------------------------------------------------------------

export function createCrowd({ seed = 7, horizon = 3600, line = LINE_DEFAULT, preroll = 16 } = {}) {
  const geo = CROWD_GEOMETRY;
  const ST = buildStatic(geo);
  const seedBase = (Math.imul(seed | 0, 0x9e3779b1) ^ 0x2545f491) >>> 0;

  const agents = [];
  const events = [];
  const groups = [];            // accepted group plans (private)
  const priv = new Map();       // agent id -> { g, m }
  const reserv = [];            // planned member trajectories on the global time grid
  const stampOf = [];
  let stamp = 0;
  const resBuckets = new Map(); // second -> reservation indices
  const stats = { horizon, preroll, groups: 0, agents: 0, dropped: 0, prerollSkipped: 0, delayedGroups: 0, totalDelay: 0, maxDelay: 0, sidesteps: 0, yields: 0, pauses: 0, slowWalkers: 0, evaluations: 0, rejectedRoutes: 0 };

  // ------------------------------------------------------------------ routes
  // waypoints of the group centre line, in walking order
  function makeRoute(r, G, plan, variant) {
    const lim = 0.97 - G.half - 0.03;
    const sgnK = G.kind === 'in' ? -1 : 1; // keep left: in -> x < 0 at the door, out -> x > 0
    // doorway lane: the inner edge of each flow stays ~0.3 m off the centre line
    const xd = clamp(sgnK * (0.3 + G.half) + (variant === 0 ? plan.laneN : gauss(r)) * 0.17, -lim, lim);
    const aisleLim = Math.max(0, geo.aisleHalf - CLEARANCE.seat - (G.useFile ? 0 : G.half) - 0.03);
    const xa = sgnK * aisleLim * (G.useFile ? 0.62 + 0.15 * r() : 0.7 + 0.3 * r());
    let P0, fMid;
    if (plan.edge === 'left') { P0 = [-3.4 + G.half, Z_SPAWN]; fMid = 0.35 + 0.2 * r(); }
    else if (plan.edge === 'right') { P0 = [3.9 - G.half, Z_SPAWN]; fMid = 0.35 + 0.2 * r(); }
    else { P0 = [plan.xs + (variant ? 0.25 * gauss(r) : 0), Z_SPAWN]; fMid = 0.45 + 0.25 * r(); }
    P0[0] = clamp(P0[0], -3.4 + G.half, 3.9 - G.half);
    const zMid = 0.1 + 0.35 * gauss(r);
    const M = [lerp(P0[0], xd, fMid) + 0.22 * gauss(r), zMid];
    const corridor = [P0];
    if (plan.edge !== 'mid') corridor.push([lerp(P0[0], M[0], 0.45), lerp(Z_SPAWN, zMid, 0.5)]);
    corridor.push(M, [xd + 0.08 * gauss(r), -2.45 + 0.12 * gauss(r)]);
    const inner = [[xd * 0.92, -5.05]];
    if (plan.aud === 'aisle') inner.push([lerp(xd, xa, 0.6), -6.25], [xa, -7.35], [xa, Z_AISLE_END]);
    else {
      const s = plan.aud === 'sideL' ? -1 : 1;
      inner.push([xd + s * 0.25, -6.15], [s * 1.5, Z_SIDE - 0.05], [s * X_SIDE_END, Z_SIDE - 0.08]);
    }
    const pts = G.kind === 'in' ? [...corridor, ...inner] : [...inner.reverse(), ...corridor.reverse()];
    // straight run-in / run-out so staggered members also start / end out of view
    const ext = EXT + G.depth;
    const a = pts[0], b = pts[1], y = pts[pts.length - 1], z = pts[pts.length - 2];
    const la = hyp(a[0] - b[0], a[1] - b[1]), ly = hyp(y[0] - z[0], y[1] - z[1]);
    pts.unshift([a[0] + ((a[0] - b[0]) / la) * ext, a[1] + ((a[1] - b[1]) / la) * ext]);
    pts.push([y[0] + ((y[0] - z[0]) / ly) * ext, y[1] + ((y[1] - z[1]) / ly) * ext]);
    return pts;
  }

  function centreFromRoute(pts) {
    const cr = catmullRom(pts);
    const p = tangents(smoothPath(resample(cr.xs, cr.zs), 0.32));
    // lane etiquette: in the open corridor everybody keeps a little to their left, so
    // people walking the same line in opposite directions pass each other
    return offsetPath(p, (s, x, z) => -KEEP_LEFT * ss(-3.5, -1.6, z) * (1 - ss(1.3, 3.6, z)));
  }

  // member curves indexed by group progress s = j * DS
  function buildMembers(G, C) {
    const Lc = (C.n - 1) * DS;
    const Lg = Lc - G.depth;
    const N = Math.floor(Lg / DS) + 1;
    const cx = C.x, cz = C.z, ctx = C.tx, ctz = C.tz, cn = C.n;
    // single file for the narrow aisle: first spread out front-to-back (approaching the
    // door), then close up sideways (on the landing). 0 = formation, 1 = file.
    let aL = 0, bL = 0, aT = 0, bT = 0;
    const file = G.useFile;
    if (file) {
      const first = (pred) => { for (let i = 0; i < cn; i++) if (pred(cz[i])) return i * DS; return Lc; };
      if (G.kind === 'in') { aL = first((z) => z < -2.8); bL = first((z) => z < -6.1); aT = first((z) => z < -5.3); bT = first((z) => z < -6.9); }
      else { bL = first((z) => z > -6.1); aL = first((z) => z > -2.8); bT = first((z) => z > -6.9); aT = first((z) => z > -5.3); }
    }
    const gOff = G.Bmax - G.meanB;
    const members = [];
    for (let mi = 0; mi < G.mem.length; mi++) {
      const fm = G.mem[mi];
      const js = G.jitSeeds[mi];
      const x = new Float32Array(N), z = new Float32Array(N), sig = new Float32Array(N);
      for (let j = 0; j < N; j++) {
        const s = j * DS;
        let tLong = 0, tLat = 0;
        if (file) {
          const sg = s + gOff;
          if (G.kind === 'in') { tLong = ss(aL, Math.max(bL, aL + 0.5), sg); tLat = ss(aT, Math.max(bT, aT + 0.5), sg); }
          else { tLong = 1 - ss(bL, Math.max(aL, bL + 0.5), sg); tLat = 1 - ss(bT, Math.max(aT, bT + 0.5), sg); }
        }
        const fwd = G.Bmax - (fm.back + tLong * fm.dF);
        const jit = G.size > 1 ? 0.055 * smoothNoise1(js, s / 2.6) * ss(0, 1.5, s) * ss(Lg, Lg - 1.5, s) : 0;
        const sg = s + fwd + jit;
        sig[j] = sg;
        // centre line point and normal at sg (Catmull-Rom between samples)
        const f = clamp(sg / DS, 0, cn - 1);
        let i = Math.floor(f);
        if (i >= cn - 1) i = cn - 2;
        const u = f - i, u2 = u * u, u3 = u2 * u;
        const i0 = i > 0 ? i - 1 : 0, i2 = i + 1, i3 = i + 2 < cn ? i + 2 : cn - 1;
        const qx = 0.5 * (2 * cx[i] + (cx[i2] - cx[i0]) * u + (2 * cx[i0] - 5 * cx[i] + 4 * cx[i2] - cx[i3]) * u2 + (3 * cx[i] - cx[i0] - 3 * cx[i2] + cx[i3]) * u3);
        const qz = 0.5 * (2 * cz[i] + (cz[i2] - cz[i0]) * u + (2 * cz[i0] - 5 * cz[i] + 4 * cz[i2] - cz[i3]) * u2 + (3 * cz[i] - cz[i0] - 3 * cz[i2] + cz[i3]) * u3);
        let tx = ctx[i] + (ctx[i2] - ctx[i]) * u, tz = ctz[i] + (ctz[i2] - ctz[i]) * u;
        const tl = hyp(tx, tz) || 1;
        tx /= tl; tz /= tl;
        const lat = fm.lat * (1 - tLat);
        x[j] = qx - tz * lat; // right normal (-tz, tx)
        z[j] = qz + tx * lat;
      }
      // heading (unwrapped), own walked distance, d(own length)/ds, d(heading)/ds
      const h = new Float32Array(N), d = new Float32Array(N), l = new Float32Array(N), w = new Float32Array(N);
      let prev = 0;
      for (let j = 0; j < N; j++) {
        const a = j > 1 ? j - 2 : 0, b = j + 2 < N ? j + 2 : N - 1;
        let hh = Math.atan2(x[b] - x[a], z[b] - z[a]);
        if (j) hh = prev + wrapPi(hh - prev);
        h[j] = prev = hh;
        if (j) d[j] = d[j - 1] + hyp(x[j] - x[j - 1], z[j] - z[j - 1]);
      }
      const wr = new Float64Array(N);
      for (let j = 0; j < N; j++) {
        const a = j > 0 ? j - 1 : 0, b = j + 1 < N ? j + 1 : N - 1;
        l[j] = (d[b] - d[a]) / ((b - a) * DS);
        wr[j] = (h[b] - h[a]) / ((b - a) * DS);
      }
      for (let j = 0; j < N; j++) {
        const a = j > 0 ? j - 1 : 0, b = j + 1 < N ? j + 1 : N - 1;
        w[j] = 0.25 * wr[a] + 0.5 * wr[j] + 0.25 * wr[b];
      }
      members.push({ x, z, h, d, l, w, sig });
    }
    const zc = new Float32Array(N);
    for (let j = 0; j < N; j++) { let s = 0; for (const m of members) s += m.z[j]; zc[j] = s / members.length; }
    return { N, Lg: (N - 1) * DS, members, zc };
  }

  // geometry checks independent of time: walls/obstacles, one crossing, never backwards,
  // formation spacing
  function staticCheck(G, B) {
    const { N, members } = B;
    const zb = geo.door.zBack;
    for (const m of members) {
      let crossings = 0;
      for (let j = 0; j < N; j++) {
        if (!ST.ok(m.x[j], m.z[j])) return 'wall';
        if (m.l[j] < 0.55) return 'cusp'; // inner member of a turning group still walks
        if (j) {
          const a = m.z[j - 1] - line.z, b = m.z[j] - line.z;
          if ((a > 0) !== (b > 0)) {
            crossings++;
            const xc = lerp(m.x[j - 1], m.x[j], a / (a - b));
            if (xc < line.x0 + 0.05 || xc > line.x1 - 0.05) return 'span';
            if ((G.kind === 'in') !== (b < a)) return 'dir';
          }
          // in the corridor people only ever head toward their goal
          if (m.z[j] > zb && m.z[j - 1] > zb && (G.kind === 'in' ? m.z[j] > m.z[j - 1] + 0.004 : m.z[j] < m.z[j - 1] - 0.004)) return 'back';
        }
      }
      if (crossings !== 1) return 'cross';
    }
    for (let a = 0; a < members.length; a++) for (let b = a + 1; b < members.length; b++) {
      const A = members[a], Bm = members[b];
      for (let j = 0; j < N; j++) if (hyp(A.x[j] - Bm.x[j], A.z[j] - Bm.z[j]) < SEP_GROUP) return 'formation';
    }
    return null;
  }

  // ------------------------------------------------------------------ speed profile
  function zoneFactor(kind, z) {
    if (kind === 'in') return 1 - 0.06 * ss(-3.7, -4.9, z) - 0.1 * ss(-5.0, -6.3, z) - 0.04 * ss(-6.6, -7.6, z);
    return 0.82 + 0.15 * ss(-6.6, -4.4, z) + 0.03 * ss(-3.0, 0.5, z);
  }

  // desired speed along the path before yields / pauses / accel limits (cached per curve set)
  function baseSpeed(G, B) {
    if (B.vdes) return B;
    const { N, members, zc } = B;
    const vdes = new Float64Array(N), vcap = new Float64Array(N);
    const ns = G.noiseSeed;
    for (let j = 0; j < N; j++) {
      const s = j * DS;
      let f = G.cruise * (1 + 0.035 * smoothNoise1(ns, s / 2.7) + 0.015 * smoothNoise1(ns + 1, s / 0.85));
      f *= zoneFactor(G.kind, zc[j]);
      if (G.slow) f *= 1 - (1 - G.slow.f) * ss(G.slow.zLo - 0.8, G.slow.zLo, zc[j]) * ss(G.slow.zHi + 0.8, G.slow.zHi, zc[j]);
      let wmax = 0, latmax = 0, lmax = 0;
      for (const m of members) {
        const w = Math.abs(m.w[j]);
        if (w > wmax) wmax = w;
        if (w * m.l[j] > latmax) latmax = w * m.l[j];
        if (m.l[j] > lmax) lmax = m.l[j];
      }
      let cap = V_MEMBER_MAX / lmax;
      const om = zc[j] > -5.2 && zc[j] < 2.6 ? OMEGA_NEAR : OMEGA_MAX;
      if (wmax > 1e-6) cap = Math.min(cap, om / wmax);
      if (latmax > 1e-6) cap = Math.min(cap, Math.sqrt(A_LAT / latmax));
      vdes[j] = f; vcap[j] = cap;
    }
    B.vdes = vdes; B.vcap = vcap;
    return B;
  }

  function buildProfile(G, B, slows) {
    const { N, zc } = B;
    baseSpeed(G, B);
    const v = new Float64Array(N);
    for (let j = 0; j < N; j++) {
      const s = j * DS;
      let f = B.vdes[j];
      // yielding: walk a little slower before a spot where someone else passes
      for (const q of slows) f *= 1 - (1 - q.f) * ss(q.s0 - 1.0, q.s0, s) * ss(q.s1 + 0.6, q.s1, s);
      // in view, a yield slows people down but never brings them to a crawl
      if (zc[j] > -5.0 && zc[j] < 2.6) f = Math.max(f, Math.min(B.vdes[j], V_MIN_VIEW));
      v[j] = Math.min(f, B.vcap[j]);
    }
    // pause point: group centre reaches the target z
    let jp = -1;
    if (G.pause) {
      for (let j = 1; j < N; j++) if ((zc[j - 1] - G.pause.z) * (zc[j] - G.pause.z) <= 0) { jp = j; break; }
      if (jp > 0) v[jp] = 0;
    }
    for (let j = N - 2; j >= 0; j--) v[j] = Math.min(v[j], Math.sqrt(v[j + 1] * v[j + 1] + 2 * A_DEC * DS));
    for (let j = 1; j < N; j++) v[j] = Math.min(v[j], Math.sqrt(v[j - 1] * v[j - 1] + 2 * A_ACC * DS));
    // time at each sample (constant acceleration per segment)
    const T = new Float64Array(N);
    for (let j = 1; j < N; j++) T[j] = T[j - 1] + (2 * DS) / Math.max(1e-6, v[j - 1] + v[j]);
    const dur = jp > 0 ? G.pause.dur : 0;
    const Tp = jp > 0 ? T[jp] : Infinity;
    const K = Math.ceil((T[N - 1] + dur) / H);
    const V = new Float32Array(K + 1), S = new Float32Array(K + 1);
    let j = 0;
    for (let k = 0; k <= K; k++) {
      let t = k * H;
      if (t >= Tp && t <= Tp + dur) { V[k] = 0; continue; }
      if (t > Tp + dur) t -= dur;
      while (j < N - 2 && T[j + 1] <= t) j++;
      if (t >= T[N - 1]) { V[k] = v[N - 1]; continue; }
      const a = (v[j + 1] * v[j + 1] - v[j] * v[j]) / (2 * DS);
      V[k] = Math.max(0, v[j] + a * (t - T[j]));
    }
    // integrate the piecewise-linear speed so stateAt's quadratic interpolation is exact
    for (let k = 1; k <= K; k++) S[k] = S[k - 1] + 0.5 * (V[k - 1] + V[k]) * H;
    let Kend = K;
    for (let k = 1; k <= K; k++) if (S[k] >= B.Lg) { Kend = k; break; }
    return { K: Kend, S: S.subarray(0, Kend + 1), V: V.subarray(0, Kend + 1), Lg: B.Lg, jp, pauseT: jp > 0 ? Tp : -1 };
  }

  // member trajectories on the local time grid
  function sampleTraj(B, P) {
    return B.members.map((m) => {
      const px = new Float32Array(P.K + 1), pz = new Float32Array(P.K + 1);
      for (let k = 0; k <= P.K; k++) {
        const f = clamp(P.S[k] / DS, 0, B.N - 1);
        let j = Math.floor(f);
        if (j >= B.N - 1) j = B.N - 2;
        const u = f - j;
        px[k] = m.x[j] + (m.x[j + 1] - m.x[j]) * u;
        pz[k] = m.z[j] + (m.z[j + 1] - m.z[j]) * u;
      }
      return { px, pz };
    });
  }

  // ------------------------------------------------------------------ conflicts
  function reqSep(ax, az, avx, avz, bx, bz, bvx, bvz) {
    if ((az < -7.0 && bz < -7.0) || (az > 2.7 && bz > 2.7)) return SEP_HIDDEN;
    const va = hyp(avx, avz), vb = hyp(bvx, bvz);
    if (va > 0.02 && vb > 0.02 && (avx * bvx + avz * bvz) / (va * vb) > 0.5) {
      let ux = avx / va + bvx / vb, uz = avz / va + bvz / vb;
      const ul = hyp(ux, uz) || 1;
      ux /= ul; uz /= ul;
      const dx = bx - ax, dz = bz - az;
      if (Math.abs(dx * ux + dz * uz) > Math.abs(dx * uz - dz * ux)) return SEP_FOLLOW;
    }
    return az < -3.4 && az > -6.0 ? SEP_DOOR : SEP_PASS;
  }

  // earliest grid step where a candidate member gets too close to anyone planned
  function findConflict(traj, k0, K) {
    stamp++;
    const k1 = k0 + K;
    const nm = traj.length;
    let best = null;
    const tooClose = (k, o) => {
      const io = k - o.k0, ic = k - k0;
      const ox = o.px[io], oz = o.pz[io];
      for (let mi = 0; mi < nm; mi++) {
        const T = traj[mi];
        const dx = T.px[ic] - ox, dz = T.pz[ic] - oz;
        const d2 = dx * dx + dz * dz;
        if (d2 >= SEP_FOLLOW * SEP_FOLLOW) continue;
        const ia = ic > 0 ? ic - 1 : 0, ib = ic < K ? ic + 1 : K;
        const ja = io > 0 ? io - 1 : 0, jb = io < o.K ? io + 1 : o.K;
        const req = reqSep(T.px[ic], T.pz[ic], T.px[ib] - T.px[ia], T.pz[ib] - T.pz[ia], ox, oz, o.px[jb] - o.px[ja], o.pz[jb] - o.pz[ja]);
        if (d2 < req * req) return mi;
      }
      return -1;
    };
    for (let sec = Math.floor(k0 * H) - 1; sec <= Math.floor(k1 * H) + 1; sec++) {
      const list = resBuckets.get(sec);
      if (!list) continue;
      for (let li = 0; li < list.length; li++) {
        const ri = list[li];
        if (stampOf[ri] === stamp) continue;
        stampOf[ri] = stamp;
        const o = reserv[ri];
        const a = Math.max(k0, o.k0);
        let b = Math.min(k1, o.k0 + o.K);
        if (best && best.k - 1 < b) b = best.k - 1;
        // coarse pass every other step; distances change by < 0.18 m per step
        for (let k = a; k <= b; k += 2) {
          const io = k - o.k0, ic = k - k0;
          let near = false;
          for (let mi = 0; mi < nm; mi++) {
            const dx = traj[mi].px[ic] - o.px[io], dz = traj[mi].pz[ic] - o.pz[io];
            if (dx * dx + dz * dz < COARSE * COARSE) { near = true; break; }
          }
          if (!near) continue;
          let hit = -1, kh = -1;
          for (let kk = Math.max(a, k - 1); kk <= Math.min(b, k + 1) && hit < 0; kk++) { hit = tooClose(kk, o); kh = kk; }
          if (hit >= 0) { best = { k: kh, mi: hit, ox: o.px[kh - o.k0], oz: o.pz[kh - o.k0], ri }; break; }
        }
      }
    }
    return best;
  }

  function reserve(traj, k0, K, gid) {
    for (const T of traj) {
      const ri = reserv.length;
      reserv.push({ k0, K, px: T.px, pz: T.pz, gid });
      stampOf.push(0);
      for (let sec = Math.floor(k0 * H); sec <= Math.floor((k0 + K) * H); sec++) {
        let l = resBuckets.get(sec);
        if (!l) resBuckets.set(sec, (l = []));
        l.push(ri);
      }
    }
  }

  // ------------------------------------------------------------------ plan one group
  function planGroup(gi, ta, kind) {
    const r = mulberry32((seedBase ^ Math.imul(gi + 1, 0x9e3779b1)) >>> 0);
    const G = composeGroup(r, kind);
    G.kind = kind;
    G.noiseSeed = Math.floor(r() * 1e9);
    G.jitSeeds = G.mem.map(() => Math.floor(r() * 1e9));
    const plan = {
      edge: r() < (kind === 'in' ? 0.66 : 0.6) ? 'mid' : r() < 0.5 ? 'left' : 'right',
      xs: -2.6 + 5.4 * r(),
      // the cross-aisle turn is too tight for three walking abreast: those take the aisle
      aud: r() < (kind === 'in' ? 0.64 : 0.68) || G.half > 0.4 ? 'aisle' : r() < 0.5 ? 'sideL' : 'sideR',
      laneN: gauss(r),
    };
    G.plan = plan;
    setDepth(G, plan.aud === 'aisle');
    // a pause (phone check, a family regrouping) or a slow phone-walk, mid-corridor
    const hasPhone = G.humans.some((h) => h.carry === 'phone');
    const pp = kind === 'in' ? (hasPhone ? 0.33 : 0.055) : (hasPhone ? 0.22 : 0.035);
    if (r() < pp) {
      // Nobody freezes in the open corridor (it reads as random stopping on camera): a phone
      // check or a family regrouping becomes a slow stroll over a couple of metres instead.
      const z = kind === 'in' ? -1.9 + 2.3 * r() : -1.6 + 1.9 * r();
      const zc = Math.max(z, line.z + (kind === 'in' ? 0.9 : 1.6) + G.depth);
      const dur = r();
      G.slow = { f: Math.max(0.6, V_MIN_VIEW / G.cruise) + 0.08 * dur, zLo: zc - 1.1, zHi: zc + 1.1 };
    } else if (hasPhone && G.size === 1 && r() < 0.3) {
      const zLo = kind === 'in' ? -2.0 + 1.8 * r() : -2.8 + 1.8 * r();
      G.slow = { f: Math.max(0.62 + 0.12 * r(), V_MIN_VIEW / G.cruise), zLo, zHi: zLo + 2.2 };
    }

    const variants = [];
    function getVariant(vi) {
      while (variants.length <= vi) {
        const idx = variants.length;
        let v = null;
        for (let tries = 0; tries < 6 && !v; tries++) {
          const C = centreFromRoute(makeRoute(r, G, plan, idx === 0 && tries === 0 ? 0 : 1));
          const B = buildMembers(G, C);
          if (staticCheck(G, B)) { stats.rejectedRoutes++; continue; }
          const P = buildProfile(G, B, []);
          v = { C, C0: C, B, P, traj: sampleTraj(B, P), bumps: [], slows: [] };
        }
        variants.push(v);
      }
      return variants[vi];
    }

    // sidestep: smooth lateral bump of the centre line around the conflict spot
    function withBump(base, conf) {
      const { P, B } = base;
      const kl = conf.k - conf.k0;
      const m = B.members[conf.mi];
      const sc = m.sig[Math.min(B.N - 1, Math.round(Math.min(P.S[kl], B.Lg) / DS))];
      const i = Math.min(Math.floor(clamp(sc / DS, 0, base.C.n - 1)), base.C.n - 2);
      const cz = base.C.z[i];
      if (cz < -3.6 || cz > 2.9) return null; // only in the open corridor
      const nx = -base.C.tz[i], nz = base.C.tx[i];
      const T = base.traj[conf.mi];
      const side = (conf.ox - T.px[kl]) * nx + (conf.oz - T.pz[kl]) * nz;
      const dir = Math.abs(side) > 0.05 ? -Math.sign(side) : -1; // head-on: step to the left
      const amp = clamp(SEP_PASS + 0.08 - Math.abs(side), 0.18, 0.75);
      const bumps = [...base.bumps, { c: sc - 0.3, w: 1.1 + amp, a: dir * amp }];
      const C = offsetPath(base.C0, (s) => { let b = 0; for (const q of bumps) b += q.a * Math.exp(-(((s - q.c) / q.w) ** 2)); return b; });
      const Bn = buildMembers(G, C);
      if (staticCheck(G, Bn)) return null;
      const Pn = buildProfile(G, Bn, base.slows);
      return { C, C0: base.C0, B: Bn, P: Pn, traj: sampleTraj(Bn, Pn), bumps, slows: base.slows };
    }

    // yield: slow down over the few metres before the conflict so the other person passes first
    function withSlow(base, conf) {
      const { P, B } = base;
      const s = Math.min(P.S[conf.k - conf.k0], B.Lg);
      const slows = [...base.slows, { s0: Math.max(0, s - 3.2), s1: s + 0.2, f: base.slows.length ? 0.8 : 0.74 }];
      const Pn = buildProfile(G, B, slows);
      return { C: base.C, C0: base.C0, B, P: Pn, traj: sampleTraj(B, Pn), bumps: base.bumps, slows };
    }

    const k0a = Math.round(ta / H);
    // try lane variant vi starting at k0, repairing conflicts with a sidestep or by yielding
    function attempt(vi, k0, fixes) {
      let cand = getVariant(vi);
      for (let fix = 0; fix <= fixes && cand; fix++) {
        stats.evaluations++;
        const conf = findConflict(cand.traj, k0, cand.P.K);
        if (!conf) return cand;
        if (fix === fixes) break;
        conf.k0 = k0;
        // opposing / crossing traffic in the open corridor: sidestep; following, or in
        // the doorway / auditorium: slow down a little and let them pass first
        const T = cand.traj[conf.mi], o = reserv[conf.ri];
        const ic = conf.k - k0, io = conf.k - o.k0;
        const avx = T.px[Math.min(ic + 1, cand.P.K)] - T.px[Math.max(ic - 1, 0)], avz = T.pz[Math.min(ic + 1, cand.P.K)] - T.pz[Math.max(ic - 1, 0)];
        const bvx = o.px[Math.min(io + 1, o.K)] - o.px[Math.max(io - 1, 0)], bvz = o.pz[Math.min(io + 1, o.K)] - o.pz[Math.max(io - 1, 0)];
        const same = avx * bvx + avz * bvz > 0.3 * hyp(avx, avz) * hyp(bvx, bvz);
        let next = null;
        if (!same && cand.bumps.length < 2) next = withBump(cand, conf);
        if (!next && cand.slows.length < 2) next = withSlow(cand, conf);
        if (!next && cand.bumps.length < 2) next = withBump(cand, conf);
        cand = next;
      }
      return null;
    }
    // Conflicts are solved in the order that looks most natural on camera:
    // 1) on time, a few lanes, untouched
    for (let vi = 0; vi < 3; vi++) {
      const c = attempt(vi, k0a, 0);
      if (c) return accept(gi, G, c, k0a, 0);
    }
    // 2) start a little later (start points are out of view / in the dark): invisible
    const freeSteps = Math.round(8 / DELAY_STEP);
    for (let step = 1; step <= freeSteps; step++) {
      const k0 = k0a + Math.round((step * DELAY_STEP) / H);
      for (let vi = 0; vi < 3; vi++) {
        const c = attempt(vi, k0, 0);
        if (c) return accept(gi, G, c, k0, step * DELAY_STEP);
      }
    }
    // 3) on time with a sidestep / lane change, then a gentle slow-down (never a stop)
    for (let vi = 0; vi < 3; vi++) {
      const c = attempt(vi, k0a, vi === 0 ? 3 : 1);
      if (c) return accept(gi, G, c, k0a, 0);
    }
    // 4) later still, with repairs now and then
    const maxSteps = Math.round(MAX_DELAY / DELAY_STEP);
    for (let step = 1; step <= maxSteps; step++) {
      const repair = step % 3 === 0;
      if (step <= freeSteps && !repair) continue;
      const k0 = k0a + Math.round((step * DELAY_STEP) / H);
      for (let vi = 0; vi < 3; vi++) {
        const c = attempt(vi, k0, repair && vi === 0 ? 2 : 0);
        if (c) return accept(gi, G, c, k0, step * DELAY_STEP);
      }
    }
    stats.dropped++;
    return null;
  }

  // group progress -> time (inverse of the quadratic interpolation used by stateAt)
  function timeAtS(P, s) {
    let lo = 0, hi = P.K;
    while (hi - lo > 1) { const mid = (lo + hi) >> 1; if (P.S[mid] <= s) lo = mid; else hi = mid; }
    const v0 = P.V[lo], a = (P.V[lo + 1] - v0) / H, ds = s - P.S[lo];
    let u;
    if (Math.abs(a) < 1e-9) u = v0 > 1e-9 ? ds / v0 : 0;
    else u = (-v0 + Math.sqrt(Math.max(0, v0 * v0 + 2 * a * ds))) / a;
    return lo * H + clamp(u, 0, H);
  }

  function accept(gi, G, cand, k0, delay) {
    const { B, P } = cand;
    const t0 = k0 * H;
    const ev = [];
    for (let mi = 0; mi < B.members.length; mi++) {
      const m = B.members[mi];
      for (let j = 1; j < B.N; j++) {
        const a = m.z[j - 1] - line.z, b = m.z[j] - line.z;
        if ((a > 0) === (b > 0)) continue;
        const f = a / (a - b);
        ev.push({ t: t0 + timeAtS(P, (j - 1 + f) * DS), x: lerp(m.x[j - 1], m.x[j], f), dir: b < a ? 'in' : 'out' });
        break;
      }
    }
    // pre-roll groups that would cross before t = 0 are left out (counters start at 0)
    if (ev.some((e) => e.t < 0.2)) { stats.prerollSkipped++; return null; }
    reserve(cand.traj, k0, P.K, gi);
    stats.groups++;
    if (delay > 0) { stats.delayedGroups++; stats.totalDelay += delay; stats.maxDelay = Math.max(stats.maxDelay, delay); }
    stats.sidesteps += cand.bumps.length;
    stats.yields += cand.slows.length;
    if (P.jp > 0) stats.pauses++;
    if (G.slow) stats.slowWalkers++;
    const g = {
      id: gi, kind: G.kind, type: G.type, size: G.size, cruise: G.cruise, aud: G.plan.aud, edge: G.plan.edge, file: G.useFile,
      t0, t1: t0 + timeAtS(P, P.Lg - 1e-4), S: P.S, V: P.V, K: P.K, Lg: P.Lg, N: B.N, delay,
      pause: P.jp > 0 ? { t: t0 + P.pauseT, dur: G.pause.dur } : null, sidesteps: cand.bumps.length, yields: cand.slows.length, members: [],
    };
    groups.push(g);
    for (let mi = 0; mi < B.members.length; mi++) {
      const id = agents.length + 1;
      const a = {
        id,
        seed: Math.floor(hash2(seedBase ^ 0x5bd1e995, id) * 2147483647),
        kind: G.kind,
        group: gi,
        t0: g.t0,
        t1: g.t1,
        human: G.humans[mi],
        speed: Math.round(G.cruise * 1000) / 1000,
      };
      agents.push(a);
      g.members.push(id);
      const m = B.members[mi];
      // normalised stride distance on the time grid: integral of v / strideFactor(v)
      const RT = new Float32Array(P.K + 1), DN = new Float32Array(P.K + 1);
      for (let k = 0; k <= P.K; k++) {
        const f = clamp(P.S[k] / DS, 0, B.N - 1);
        let j = Math.floor(f); if (j >= B.N - 1) j = B.N - 2;
        const vm = P.V[k] * (m.l[j] + (m.l[j + 1] - m.l[j]) * (f - j));
        RT[k] = vm / strideFactor(vm);
        if (k) DN[k] = DN[k - 1] + 0.5 * (RT[k - 1] + RT[k]) * H;
      }
      priv.set(id, { g, m: { x: m.x, z: m.z, h: m.h, d: m.d, l: m.l, w: m.w, RT, DN } });
      events.push({ t: ev[mi].t, id, dir: ev[mi].dir, x: ev[mi].x, z: line.z });
    }
    return g;
  }

  // ------------------------------------------------------------------ arrivals
  {
    const ra = mulberry32((seedBase ^ 0xa5a5a5a5) >>> 0);
    const nb = (seedBase % 100000) + 17;
    // bursts and lulls: slow log-normal-ish modulation of the arrival rate
    const burst = (t) => Math.exp(0.45 * smoothNoise1(nb, t / 42) + 0.3 * smoothNoise1(nb + 1, t / 11));
    const T0 = -preroll, T1 = horizon;
    let mean = 0, cnt = 0;
    for (let t = T0; t <= T1; t += 1) { mean += burst(t); cnt++; }
    mean /= cnt;
    const lambda0 = LAMBDA_PERSONS / 1.88; // groups per second (mean group size ~1.88)
    // renewal process in "operational time" (cumulative rate): Gamma(2) gaps are more
    // regular than Poisson (fewer long empty stretches), the rate modulation makes bursts
    const DT_L = 0.25;
    let t = T0, gi = 0, acc = 0;
    let need = -Math.log((1 - ra() * 0.999999) * (1 - ra() * 0.999999)) / 2;
    while (t < T1) {
      const rate = (lambda0 * burst(t)) / mean;
      if (acc + rate * DT_L >= need) {
        t += (need - acc) / rate;
        acc = 0;
        need = -Math.log((1 - ra() * 0.999999) * (1 - ra() * 0.999999)) / 2;
        if (t < T1) planGroup(gi++, t, ra() < 0.66 ? 'in' : 'out');
      } else { acc += rate * DT_L; t += DT_L; }
    }
  }
  events.sort((a, b) => a.t - b.t || a.id - b.id);
  stats.agents = agents.length;
  // planning buffers are no longer needed
  reserv.length = 0;
  resBuckets.clear();

  // ------------------------------------------------------------------ index
  const SEC0 = Math.floor(-preroll) - 2;
  const buckets = [];
  for (const a of agents) {
    for (let k = Math.floor(a.t0); k <= Math.floor(a.t1); k++) (buckets[k - SEC0] ||= []).push(a);
  }

  function activeAt(t) {
    const b = buckets[Math.floor(t) - SEC0];
    if (!b) return [];
    const out = [];
    for (let i = 0; i < b.length; i++) { const a = b[i]; if (t >= a.t0 && t <= a.t1) out.push(a); }
    return out;
  }

  function stateAt(agent, t) {
    if (!agent || !(t >= agent.t0 && t <= agent.t1)) return null;
    const p = priv.get(agent.id);
    if (!p) return null;
    const g = p.g, m = p.m;
    const tau = t - g.t0;
    let k = Math.floor(tau / H);
    if (k >= g.K) k = g.K - 1;
    if (k < 0) k = 0;
    const u = clamp(tau - k * H, 0, H);
    const v0 = g.V[k], v1 = g.V[k + 1];
    const acc = (v1 - v0) / H;
    const s = clamp(g.S[k] + v0 * u + 0.5 * acc * u * u, 0, g.Lg);
    const vg = Math.max(0, v0 + acc * u);
    const f = s / DS;
    let j = Math.floor(f);
    if (j >= g.N - 1) j = g.N - 2;
    const w = f - j;
    const x = m.x[j] + (m.x[j + 1] - m.x[j]) * w;
    const z = m.z[j] + (m.z[j + 1] - m.z[j]) * w;
    const speed = vg * (m.l[j] + (m.l[j + 1] - m.l[j]) * w);
    const r0 = m.RT[k], r1 = m.RT[k + 1];
    const ndist = m.DN[k] + r0 * u + 0.5 * ((r1 - r0) / H) * u * u;
    return {
      x, z, ndist, strideK: strideFactor(speed),
      heading: wrapPi(m.h[j] + (m.h[j + 1] - m.h[j]) * w),
      speed,
      dist: m.d[j] + (m.d[j + 1] - m.d[j]) * w,
      turnRate: vg * (m.w[j] + (m.w[j + 1] - m.w[j]) * w),
      alpha: alphaAt(geo, x, z),
      y: floorY(geo, x, z),
    };
  }

  // read-only facts about a planned group (for tests, plots and debugging)
  function groupInfo(gid) {
    const g = groups[gid] && groups[gid].id === gid ? groups[gid] : groups.find((q) => q.id === gid);
    if (!g) return null;
    const { S, V, ...rest } = g;
    return { ...rest, members: [...g.members] };
  }

  return { agents, stateAt, activeAt, events, line, stats, groupInfo };
}
