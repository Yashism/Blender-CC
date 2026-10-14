// Procedural CCTV feed: the room (environment.js), the CCTV look (cctv_pass.js), the
// planned crowd (crowd.js) and the people (humans.js) put together behind the Feed
// interface the dashboard uses (see SPEC.md).
//
//   const feed = await createSimFeed(host, { seed = 7, quality = 'high' });
//   feed.render(T)    draws the camera image for time T (pure function of T and seed)
//   feed.people(T)    tight detector-like boxes in 1920x1080 image px
//   feed.footAt(id,t) the foot point on the floor in image px (see footWorld)
//   feed.events(T)    line crossings with t <= T, in image px
//
// The camera is a true 25 fps camera: render(T) and people(T) show the frame at
// floor(T * 25) / 25 (in live mode the GPU only redraws when that frame changes), with
// motion blur from averaged shutter sub-frames when exporting (opts.motionBlur; live mode
// skips it to keep the frame rate). Export video at 25 fps for the cleanest motion.
//
// Extra fields beyond SPEC (the dashboard does not need them): feed.linePoints (the
// counting line as a polyline; it bends a little under the lens distortion),
// feed.duration (length of the crowd plan; time keeps running past it, the plan repeats
// with fresh ids), feed.resize() (call when the host's CSS scale changes: a transform does
// not fire ResizeObserver), feed.stats() (render timing), feed.dispose(). Boxes also carry
// `a` (0..1 box opacity, fades as a person walks into the dark or behind somebody).
import * as THREE from 'three';
import { buildEnvironment, projectToImage, LINE, DOOR } from './environment.js';
import { createCCTVPasses } from './cctv_pass.js';
import { createCrowd } from './crowd.js';
import { createHuman } from './humans.js';
import { hash2, smoothNoise1 } from './rng.js';

const IMG_W = 1920, IMG_H = 1080;
const FPS = 25;            // the camera's frame rate
const SHUTTER = 0.014;     // s: spread of the shutter sub-frames (close enough to read as a smear)
const clamp = (x, a, b) => (x < a ? a : x > b ? b : x);
const sstep = (a, b, x) => { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); };
const frameT = (T) => Math.floor(T * FPS + 1e-6) / FPS;

const QUALITY = {
  // env: environment quality; renderScale: internal render size relative to the canvas;
  // samples: MSAA of the HDR scene target; blur: live motion-blur sub-frames (0 = off)
  high: { env: 'high', renderScale: 1.25, samples: 4, blur: 0 },
  medium: { env: 'high', renderScale: 1.0, samples: 2, blur: 0 },
  low: { env: 'low', renderScale: 0.85, samples: 0, blur: 0 },
};
const LADDER = ['high', 'medium', 'low'];

// opts.motionBlur: sub-frames per exported frame (default 2: each costs a full scene render; 0/1 = off). Live mode uses the
// quality level's setting.
export async function createSimFeed(host, { seed = 7, quality = 'high', horizon = 3600, motionBlur = 2 } = {}) {
  const tick = () => new Promise((r) => setTimeout(r, 0));
  let level = Math.max(0, LADDER.indexOf(quality));
  let Q = QUALITY[LADDER[level]];

  // ---------------------------------------------------------------- renderer
  const renderer = new THREE.WebGLRenderer({ antialias: false, preserveDrawingBuffer: true, powerPreference: 'high-performance', alpha: false });
  renderer.setPixelRatio(1);
  const canvas = renderer.domElement;
  canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block';
  host.appendChild(canvas);
  // drawn size: the host as it appears on screen (getBoundingClientRect includes CSS transforms
  // such as the slide's scale(--s); clientWidth does not) x devicePixelRatio, max 1920
  const sizeFor = () => {
    const dpr = window.devicePixelRatio || 1;
    let cw = 0;
    try { cw = host.getBoundingClientRect().width; } catch (e) { cw = 0; }
    if (!(cw > 0)) cw = host.clientWidth || IMG_W;
    const w = Math.max(320, Math.min(IMG_W, Math.round(cw * dpr)));
    return [w, Math.round((w * 9) / 16)];
  };
  let [W, H] = sizeFor();
  renderer.setSize(W, H, false);

  const scene = new THREE.Scene();
  const env = buildEnvironment(scene, renderer, { quality: Q.env });
  const camera = env.camera;
  camera.updateMatrixWorld(true);
  const passes = createCCTVPasses(renderer, scene, camera, W, H, { renderScale: Q.renderScale, samples: Q.samples });
  await tick();

  // ---------------------------------------------------------------- crowd
  const crowd = createCrowd({ seed, horizon });
  const P = horizon;                       // the plan repeats every P seconds with fresh ids
  const N = crowd.agents.reduce((m, a) => Math.max(m, a.id), 0);
  const ID_STRIDE = N;                     // global id = local id + loop * N (ids keep growing)
  const agentById = new Map(crowd.agents.map((a) => [a.id, a]));
  const minT0 = crowd.agents.reduce((m, a) => Math.min(m, a.t0), 0); // pre-roll agents start before 0
  const loopOf = (T) => Math.max(0, Math.floor(T / P));
  const gidOf = (k, id) => id + k * ID_STRIDE;
  const splitId = (g) => { const k = Math.floor((g - 1) / ID_STRIDE); return [k, g - k * ID_STRIDE]; };

  // agents present at T: [{ gid, agent, t }] (t = plan time). The previous loop's
  // stragglers stay until they are done; the next loop's pre-roll agents (t0 < 0) walk in
  // before the loop starts, as they do before T = 0.
  function activeList(T) {
    const out = [];
    if (!Number.isFinite(T)) return out;
    if (T < 0) { for (const a of crowd.activeAt(T)) out.push({ gid: a.id, agent: a, t: T }); return out; }
    const k = loopOf(T);
    const t = T - k * P;
    for (const a of crowd.activeAt(t)) out.push({ gid: gidOf(k, a.id), agent: a, t });
    if (k > 0) for (const a of crowd.activeAt(t + P)) if (a.t0 < P) out.push({ gid: gidOf(k - 1, a.id), agent: a, t: t + P });
    if (t > P + minT0) for (const a of crowd.activeAt(t - P)) if (a.t0 < 0) out.push({ gid: gidOf(k + 1, a.id), agent: a, t: t - P });
    return out;
  }
  function stateOf(gid, T) {
    const [k, id] = splitId(gid);
    const a = agentById.get(id);
    return a ? crowd.stateAt(a, T - k * P) : null;
  }

  // walking companions fall into a rhythm: adults of one group are given phase offsets so
  // that, around the counting line, their inner arms swing together instead of crossing
  const groupAdults = new Map();
  for (const a of crowd.agents) if (a.human && a.human.kind !== 'child') { let l = groupAdults.get(a.group); if (!l) groupAdults.set(a.group, (l = [])); l.push(a); }
  const evTimeOf = new Map(crowd.events.map((e) => [e.id, e.t]));
  const phaseOff = new Map(); // agent id -> offset (needs the person's stride, so computed lazily)
  function phaseOffset(agent, S) {
    let o = phaseOff.get(agent.id);
    if (o !== undefined) return o;
    o = 0;
    const l = groupAdults.get(agent.group);
    if (l && l.length > 1) {
      const rank = l.indexOf(agent);
      const tm = evTimeOf.get(l[0].id);
      const st = tm !== undefined ? crowd.stateAt(agent, tm) : null;
      if (rank >= 0 && st) {
        const want = (rank % 2) * 0.5 + 0.08 * hash2(agent.id, 77);
        o = want - st.ndist / S;
        o -= Math.floor(o);
      }
    }
    phaseOff.set(agent.id, o);
    return o;
  }

  // ---------------------------------------------------------------- image-space geometry
  const proj = (x, y, z) => projectToImage(camera, [x, y, z]);
  const lineImg = [proj(LINE.x0, 0, LINE.z), proj(LINE.x1, 0, LINE.z)];
  const linePoints = [];
  for (let i = 0; i <= 16; i++) linePoints.push(proj(LINE.x0 + ((LINE.x1 - LINE.x0) * i) / 16, 0, LINE.z));

  // the doorway as the camera sees it: body points behind the door wall are only visible
  // through it (people on the cross-aisle landing are hidden by the wall)
  const doorPoly = [];
  {
    const zf = DOOR.z, x0 = DOOR.x0, x1 = DOOR.x1, h = DOOR.height, n = 12;
    for (let i = 0; i <= n; i++) doorPoly.push(proj(x0 + ((x1 - x0) * i) / n, 0, zf));
    for (let i = 1; i <= n; i++) doorPoly.push(proj(x1, (h * i) / n, zf));
    for (let i = 1; i <= n; i++) doorPoly.push(proj(x1 - ((x1 - x0) * i) / n, h, zf));
    for (let i = 1; i < n; i++) doorPoly.push(proj(x0, h - (h * i) / n, zf));
  }
  function inPoly(px, py, poly) {
    let c = false;
    for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
      const [xi, yi] = poly[i], [xj, yj] = poly[j];
      if ((yi > py) !== (yj > py) && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) c = !c;
    }
    return c;
  }

  // The foot point. A detector box ends at the foot nearest the camera, which on average
  // lies about a quarter metre from the body centre toward the camera while walking
  // (measured over the gait cycle by tests/feed_footcal.js); a person standing still has both
  // feet under the body. The foot point is that spot on the floor, so the dashboard's trail
  // (footAt) meets the box bottom, and a count fires exactly when the trail crosses the line.
  const camX = camera.position.x, camZ = camera.position.z;
  function footWorld(agent, s) {
    const ux = camX - s.x, uz = camZ - s.z;
    const L = Math.hypot(ux, uz) || 1;
    const c = (agent.human && agent.human.kind === 'child' ? 0.19 : 0.26) * sstep(0.06, 0.45, s.speed || 0);
    return [s.x + (ux / L) * c, s.y || 0, s.z + (uz / L) * c];
  }
  // crowd events are body-centre crossings; re-time them to the foot-point crossing
  function footCrossing(e) {
    const a = agentById.get(e.id);
    const f = (t) => { const st = crowd.stateAt(a, t); return st ? footWorld(a, st)[2] - LINE.z : NaN; };
    const sgn = e.dir === 'in' ? 1 : -1; // 'in': foot z goes from > line to < line
    let lo = NaN, hi = NaN;
    for (let t = Math.max(a.t0, e.t - 2.5); t <= Math.min(a.t1, e.t + 2.5) - 0.05; t += 0.05) {
      if (f(t) * sgn > 0 && f(t + 0.05) * sgn <= 0) { lo = t; hi = t + 0.05; break; }
    }
    if (!(lo === lo)) { const [x, y] = proj(e.x, 0, e.z); return { t: e.t, id: e.id, dir: e.dir, x, y }; }
    for (let i = 0; i < 30; i++) { const m = (lo + hi) / 2; if (f(m) * sgn > 0) lo = m; else hi = m; }
    const w = footWorld(a, crowd.stateAt(a, hi));
    const [x, y] = proj(w[0], 0, LINE.z);
    return { t: hi, id: e.id, dir: e.dir, x, y };
  }
  const loopEvents = crowd.events.map(footCrossing).sort((p, q) => p.t - q.t);
  const crossT = new Map(loopEvents.map((e) => [e.id, e.t]));
  // the tracker holds on to a track while it crosses the line, even through occlusion
  const nearCrossing = (gid, T) => { const [k, id] = splitId(gid); const t = crossT.get(id); return t !== undefined && Math.abs(T - (t + k * P)) < 0.8; };
  // all loops merged in time order, grown one loop at a time (a loop's last events may spill
  // a little past the next loop's first ones, so each new loop is merged, not appended)
  let merged = [], mergedLoops = 0;
  function growTo(kMax) {
    while (mergedLoops <= kMax) {
      const kk = mergedLoops++;
      const add = loopEvents.map((e) => ({ t: e.t + kk * P, id: gidOf(kk, e.id), dir: e.dir, x: e.x, y: e.y }));
      if (!merged.length) { merged = add; continue; }
      const out = new Array(merged.length + add.length);
      let i = 0, j = 0, n = 0;
      while (i < merged.length && j < add.length) out[n++] = merged[i].t <= add[j].t ? merged[i++] : add[j++];
      while (i < merged.length) out[n++] = merged[i++];
      while (j < add.length) out[n++] = add[j++];
      merged = out;
    }
  }
  let evLastN = -1, evLast = [];
  // all events with t <= T, sorted by t. Memoised: the same array comes back until a new
  // event happens.
  function eventsUpTo(T) {
    if (!Number.isFinite(T) || T <= 0) return [];
    growTo(loopOf(T) + 1);
    let lo = 0, hi = merged.length;
    while (lo < hi) { const m = (lo + hi) >> 1; if (merged[m].t <= T) lo = m + 1; else hi = m; }
    if (lo !== evLastN) { evLastN = lo; evLast = merged.slice(0, lo); }
    return evLast;
  }

  // ---------------------------------------------------------------- people
  const peopleRoot = new THREE.Group();
  peopleRoot.name = 'people';
  scene.add(peopleRoot);
  const pool = new Map(); // gid -> human
  const lastUsed = new Map(); // gid -> last plan-independent T it was active (lazy disposal)
  const prewarmed = new Set();
  let live = false, tStart = 0;
  let createBudget = Infinity; // live mode: at most one person built per frame
  let pendingBuild = false;
  function dressHuman(h) {
    // a little more of the room's bounce on people than on the room itself, so the shadow
    // sides keep some detail instead of crushing to black
    const m = h.mesh.material;
    if (scene.environment) { m.envMap = scene.environment; m.envMapIntensity = 0.14; }
  }
  function humanFor(gid, agent) {
    let h = pool.get(gid);
    if (!h) {
      h = createHuman(agent.seed, agent.human);
      dressHuman(h);
      peopleRoot.add(h.object);
      pool.set(gid, h);
    }
    return h;
  }
  // One person who is never shown or disposed keeps the people's shader programs alive, so
  // nothing is recompiled mid-playback when the corridor empties and fills again.
  const keeper = createHuman(12345, { kind: 'adult', sex: 'm', carry: 'phone' });
  dressHuman(keeper);
  keeper.object.position.set(0, -100, 0);
  keeper.object.traverse((o) => { o.frustumCulled = true; });
  peopleRoot.add(keeper.object);

  // How much corridor light reaches a person (1 in the corridor, ~0 two metres into the
  // auditorium), and how opaque they are: the crowd's alpha, with its z fade pushed
  // deeper, since darkening does most of the work and a see-through person looks wrong.
  const lightAt = (s) => sstep(-7.4, -5.15, s.z);
  function fadeAt(s) {
    const zPart = sstep(-8.25, -5.6, s.z);
    const side = zPart > 0.02 ? clamp(s.alpha / zPart, 0, 1) : 1;
    return side * sstep(-8.4, -7.5, s.z);
  }

  let posedT = NaN;
  let posed = []; // [{ gid, h, s, L }]
  let boxCacheT = NaN, boxCache = [];
  // put everybody where they are at T (creates people as they arrive; people who left are
  // hidden, and disposed once they have been gone for a while)
  function poseAt(T) {
    if (T === posedT) return posed;
    const list = activeList(T);
    const keep = new Set();
    const res = [];
    for (const { gid, agent, t } of list) {
      const s = crowd.stateAt(agent, t);
      if (!s) continue;
      if (!pool.has(gid)) {
        if (createBudget <= 0) { pendingBuild = true; continue; }
        createBudget--;
      }
      keep.add(gid);
      const h = humanFor(gid, agent);
      h.object.position.set(s.x, s.y || 0, s.z);
      h.object.rotation.set(0, s.heading, 0);
      const S = h.strideLength;
      h.setPose(s.ndist / S + phaseOffset(agent, S), s.speed, s.turnRate, T, s.strideK);
      const L = lightAt(s);
      h.setAlpha(fadeAt(s));
      // past the doorway people sink into the dark and keep a faint cool cast from the screen
      h.mesh.material.color.setRGB(0.05 + 0.95 * L, 0.055 + 0.945 * L, 0.075 + 0.925 * L);
      lastUsed.set(gid, T);
      res.push({ gid, h, s, L });
    }
    for (const gid of prewarmed) if (keep.has(gid)) prewarmed.delete(gid);
    for (const [gid, h] of pool) {
      if (keep.has(gid)) continue;
      h.object.visible = false;
      if (prewarmed.has(gid)) continue;
      const lu = lastUsed.get(gid);
      if (lu === undefined || Math.abs(T - lu) > 1.0) { h.dispose(); pool.delete(gid); lastUsed.delete(gid); }
    }
    peopleRoot.updateMatrixWorld(true);
    posedT = T;
    posed = res;
    boxCacheT = NaN;
    return res;
  }

  // live mode: build the people who arrive in the next few seconds ahead of time, a few
  // per idle slot, so a ~40 ms createHuman never lands inside a frame
  function prewarm(T, horizonS = 4, budget = 1, from = 0.5) {
    let made = 0;
    for (let dt = from; dt <= horizonS && made < budget; dt += 0.5) {
      for (const { gid, agent } of activeList(T + dt)) {
        if (pool.has(gid)) continue;
        const h = humanFor(gid, agent);
        h.object.visible = false;
        prewarmed.add(gid);
        if (++made >= budget) break;
      }
    }
    // forget prewarmed people that will not show soon (after a seek)
    for (const gid of prewarmed) {
      const [k, id] = splitId(gid);
      const a = agentById.get(id);
      const t = T - k * P;
      if (!a || t > a.t1 || a.t0 - t > horizonS + 2) { const h = pool.get(gid); if (h) h.dispose(); pool.delete(gid); prewarmed.delete(gid); }
    }
    return made;
  }

  // ---------------------------------------------------------------- boxes
  const pts = [];
  const e = camera.matrixWorldInverse.elements;
  // convex hull (Andrew's monotone chain) of a flat [x0, y0, x1, y1, ...] array
  function hull(xy) {
    const n = xy.length / 2;
    const idx = Array.from({ length: n }, (_, i) => i).sort((a, b) => xy[2 * a] - xy[2 * b] || xy[2 * a + 1] - xy[2 * b + 1]);
    const cross = (o, a, b) => (xy[2 * a] - xy[2 * o]) * (xy[2 * b + 1] - xy[2 * o + 1]) - (xy[2 * a + 1] - xy[2 * o + 1]) * (xy[2 * b] - xy[2 * o]);
    const lower = [], upper = [];
    for (const i of idx) { while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], i) <= 0) lower.pop(); lower.push(i); }
    for (let k = idx.length - 1; k >= 0; k--) { const i = idx[k]; while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], i) <= 0) upper.pop(); upper.push(i); }
    const hi = lower.slice(0, -1).concat(upper.slice(0, -1));
    const out = new Float64Array(hi.length * 2);
    hi.forEach((i, k) => { out[2 * k] = xy[2 * i]; out[2 * k + 1] = xy[2 * i + 1]; });
    return out;
  }
  function inHull(hv, x, y) { // counter-clockwise hull from hull()
    const n = hv.length / 2;
    if (n < 3) return false;
    for (let i = 0; i < n; i++) {
      const j = (i + 1) % n;
      if ((hv[2 * j] - hv[2 * i]) * (y - hv[2 * i + 1]) - (hv[2 * j + 1] - hv[2 * i + 1]) * (x - hv[2 * i]) < -0.5) return false;
    }
    return true;
  }
  // box of the given points: x extent from points inside the frame vertically, y extent
  // from points inside the frame horizontally (a body cut by the frame edge gets a box
  // that ends where its visible part does), then clamped to the frame
  function frameBox(xy, use) {
    let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
    for (let i = 0; i < xy.length / 2; i++) {
      if (use && !use[i]) continue;
      const px = xy[2 * i], py = xy[2 * i + 1];
      if (py >= -2 && py <= IMG_H + 2) { if (px < x0) x0 = px; if (px > x1) x1 = px; }
      if (px >= -2 && px <= IMG_W + 2) { if (py < y0) y0 = py; if (py > y1) y1 = py; }
    }
    if (!(x1 > x0) || !(y1 > y0)) return null;
    return [clamp(x0, 0, IMG_W), clamp(y0, 0, IMG_H), clamp(x1, 0, IMG_W), clamp(y1, 0, IMG_H)];
  }
  function people(Tin) {
    if (!Number.isFinite(Tin)) return [];
    const T = frameT(Tin);
    if (T === boxCacheT) return boxCache;
    const list = poseAt(T);
    const frame = Math.round(T * FPS); // detector runs at the camera's 25 fps
    const cand = [];
    for (const { gid, h, s, L } of list) {
      if (L < 0.12 || fadeAt(s) < 0.5) continue;
      h.boxPoints(pts);
      let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
      let seen = 0, behind = 0;
      const total = pts.length;
      const xy = [];
      for (let i = 0; i < total; i++) {
        const q = pts[i];
        // camera-space depth: points at or behind the lens are out of view
        const cz = e[2] * q.x + e[6] * q.y + e[10] * q.z + e[14];
        if (cz > -0.15) { behind++; continue; }
        const [px, py] = projectToImage(camera, q);
        if (q.z < DOOR.z - 0.02 && !inPoly(px, py, doorPoly)) continue; // hidden by the door wall
        seen++;
        xy.push(px, py);
        if (px < x0) x0 = px; if (px > x1) x1 = px;
        if (py < y0) y0 = py; if (py > y1) y1 = py;
      }
      if (seen < 8) continue;
      const fb = frameBox(xy, null);
      if (!fb) continue;
      const cw = fb[2] - fb[0], ch = fb[3] - fb[1];
      if (cw < 6 || ch < 12) continue;
      // how much of the body is inside the frame (unclipped extent)
      const fullW = x1 - x0, fullH = y1 - y0;
      const areaFrac = (cw * ch) / Math.max(1, fullW * fullH);
      const vis = Math.min(areaFrac, clamp((seen / total) * 1.15, 0, 1)) * (1 - behind / total);
      // ... and how far into the dark auditorium they are (a slow fade, in step with the body)
      const quality = vis * sstep(-7.0, -5.2, s.z);
      if (quality < 0.15 || ch < 40) continue;
      cand.push({ gid, s, xy, fb, quality, dist: Math.hypot(camX - s.x, camZ - s.z), hull: null });
    }
    // occlusion by people nearer the camera: a body mostly hidden behind somebody gets no
    // box (or a fading one); a partly hidden one gets a box around its visible part
    const out = [];
    for (const p of cand) {
      const n = p.xy.length / 2;
      const free = new Uint8Array(n).fill(1);
      let nFree = n;
      for (const q of cand) {
        if (q === p || q.dist >= p.dist) continue;
        if (q.fb[0] > p.fb[2] || q.fb[2] < p.fb[0] || q.fb[1] > p.fb[3] || q.fb[3] < p.fb[1]) continue;
        if (!q.hull) q.hull = hull(q.xy);
        for (let i = 0; i < n; i++) if (free[i] && inHull(q.hull, p.xy[2 * i], p.xy[2 * i + 1])) { free[i] = 0; nFree--; }
      }
      const held = nearCrossing(p.gid, T);
      const visFrac = held ? Math.max(0.45, nFree / n) : nFree / n;
      if (visFrac < 0.2) continue;
      let fb = p.fb;
      if (!held && visFrac < 0.75 && nFree >= 8) { const b = frameBox(p.xy, free); if (b && b[3] - b[1] >= 30 && b[2] - b[0] >= 6) fb = b; }
      const cw = fb[2] - fb[0], ch = fb[3] - fb[1];
      // detector-like wobble: slow drift per edge plus a small per-frame twitch, pure in (id, T)
      const gid = p.gid;
      const sz = Math.min(cw, ch);
      const jit = (k) => smoothNoise1(gid * 8 + k, T * 1.9) * 0.011 * sz + (hash2(gid * 8 + k, frame) - 0.5) * 0.008 * sz;
      const bx0 = clamp(fb[0] - 1.5 + jit(0), 0, IMG_W), bx1 = clamp(fb[2] + 1.5 + jit(1), 0, IMG_W);
      const by0 = clamp(fb[1] - 1.5 + jit(2), 0, IMG_H), by1 = clamp(fb[3] + 1.0 + jit(3) * 0.6, 0, IMG_H);
      const small = sstep(40, 140, ch);
      let c = 0.80 + 0.18 * clamp(0.62 + 0.15 * smoothNoise1(gid * 8 + 6, T * 0.7) + 0.25 * (p.quality - 0.7) + 0.1 * (small - 1), 0, 1);
      c -= 0.16 * (1 - visFrac);
      const a = sstep(0.15, 0.6, p.quality) * sstep(0.2, 0.45, visFrac);
      if (a < 0.15) continue; // invisible boxes are not reported (TRACKING n = boxes on screen)
      out.push({ id: gid, x: bx0, y: by0, w: bx1 - bx0, h: by1 - by0, conf: Math.round(clamp(c, 0.8, 0.98) * 1000) / 1000, a });
    }
    out.sort((p, q) => p.id - q.id);
    boxCacheT = T;
    boxCache = out;
    return out;
  }

  function footAt(gid, t) {
    if (!Number.isFinite(t)) return null;
    const [k, id] = splitId(gid);
    const a = agentById.get(id);
    if (!a) return null;
    const s = crowd.stateAt(a, t - k * P);
    if (!s || fadeAt(s) <= 0.02) return null;
    const p = projectToImage(camera, footWorld(a, s));
    return p[0] === p[0] ? p : null;
  }

  // ---------------------------------------------------------------- render
  let renderMs = [];
  let drawnT = NaN, dirty = true;
  function blurFor() { return live ? Q.blur : (motionBlur > 1 ? Math.round(motionBlur) : 0); }
  function render(Tin) {
    const T = frameT(Number.isFinite(Tin) ? Tin : 0);
    if (live) {
      // a 25 fps camera: nothing new to draw until the next frame (or a late arrival is built)
      if (T === drawnT && !dirty && !pendingBuild) { afterLiveFrame(false); return; }
      createBudget = 1;
    }
    pendingBuild = false;
    const t0 = performance.now();
    env.update(T);
    const n = blurFor();
    if (n > 1) passes.render(T, null, { n, at: (i) => poseAt(T + SHUTTER * (i / (n - 1) - 0.5)) });
    else { poseAt(T); passes.render(T); }
    // between frames (people() from the dashboard) nobody new is built in live mode
    createBudget = live ? 0 : Infinity;
    drawnT = T; dirty = false;
    const ms = performance.now() - t0;
    renderMs.push(ms);
    if (renderMs.length > 240) renderMs = renderMs.slice(-120);
    if (live) afterLiveFrame(true, ms);
  }

  // ---------------------------------------------------------------- size
  function resize() {
    const [w, h] = sizeFor();
    if (w === W && h === H) return;
    W = w; H = h;
    renderer.setSize(W, H, false);
    passes.setSize(W, H);
    dirty = true;
  }
  let ro = null;
  if (typeof ResizeObserver !== 'undefined') { ro = new ResizeObserver(resize); ro.observe(host); }
  // the slide scales its stage with a CSS transform on window resize, which ResizeObserver
  // does not see: re-measure on the next frame (after the slide has applied its new scale)
  const onWinResize = () => requestAnimationFrame(resize);
  if (typeof window !== 'undefined') window.addEventListener('resize', onWinResize);

  // ---------------------------------------------------------------- live clock + adaptive quality
  // The feed watches its own delivered frame rate: a 25 fps camera needs a new frame every
  // 40 ms. Display refresh caps (30 Hz screens, battery saver) do not trigger a step down,
  // since 30 Hz still delivers ~25 new frames a second. A level that turned out too slow is
  // not retried; one that was left needlessly may be retried once after a long good spell.
  let winStart = 0, winFrames = 0, winCost = 0, lastSwitch = 0, idleQueued = false, decisions = 0;
  const failed = new Set();
  let goodSince = 0;
  function setLevel(l) {
    level = clamp(l, 0, LADDER.length - 1);
    Q = QUALITY[LADDER[level]];
    passes.setQuality(Q.renderScale, Q.samples);
    dirty = true;
  }
  function afterLiveFrame(drew, ms = 0) {
    const now = performance.now();
    if (!winStart) winStart = now;
    if (drew) { winFrames++; winCost += ms; }
    const span = now - winStart;
    const need = decisions === 0 ? 1500 : 4000;
    if (span >= need && !document.hidden) {
      const fps = (winFrames * 1000) / span;
      const cost = winFrames ? winCost / winFrames : 0;
      decisions++;
      winStart = now; winFrames = 0; winCost = 0;
      if (fps < 20 && level < LADDER.length - 1 && now - lastSwitch > 1200) {
        failed.add(level); setLevel(level + 1); lastSwitch = now; goodSince = 0;
      } else if (fps >= 24 && cost < 12 && level > 0 && !failed.has(level - 1)) {
        if (!goodSince) goodSince = now;
        if (now - goodSince > 30000) { setLevel(level - 1); lastSwitch = now; goodSince = 0; }
      } else goodSince = 0;
    }
    if (!idleQueued) {
      idleQueued = true;
      const run = () => { idleQueued = false; prewarm(clock(), 4, 1); };
      if (typeof requestIdleCallback === 'function') requestIdleCallback(run, { timeout: 250 }); else setTimeout(run, 0);
    }
  }
  function clock() { return live ? (performance.now() - tStart) / 1000 : 0; }
  // back from a hidden tab: time has jumped; build the people now on screen in idle slots
  // (the frame loop also builds at most one per frame), and restart the rate window
  function onVisibility() {
    if (document.hidden || !live) return;
    winStart = 0; winFrames = 0; winCost = 0;
    let n = 0;
    const step = () => { if (prewarm(clock(), 2, 1, 0) && ++n < 30) (typeof requestIdleCallback === 'function' ? requestIdleCallback(step, { timeout: 100 }) : setTimeout(step, 0)); };
    step();
  }
  if (typeof document !== 'undefined') document.addEventListener('visibilitychange', onVisibility);

  // compile every shader before the first visible frame (with the people of T = 0), for
  // the target the scene is really drawn into (half-float, linear output)
  poseAt(0);
  prewarm(0, 3, 4);
  for (const [, h] of pool) h.object.visible = true;
  renderer.setRenderTarget(passes.sceneTarget);
  renderer.compile(scene, camera);
  renderer.setRenderTarget(null);
  posedT = NaN;
  poseAt(0);
  passes.render(0);
  await tick();

  return {
    kind: 'sim',
    width: IMG_W, height: IMG_H,
    line: lineImg,
    linePoints,
    canvas,
    duration: P,
    clock,
    start() {
      if (!live) { live = true; tStart = performance.now(); winStart = 0; winFrames = 0; dirty = true; createBudget = 0; }
      resize(); // the slide has applied its CSS scale by now
      return Promise.resolve(true);
    },
    async seek(T) {
      // export mode: build everybody needed for T (and its shutter sub-frames), yielding
      // between the expensive builds
      if (!Number.isFinite(T)) return;
      const Tf = frameT(T);
      for (const tt of [Tf - SHUTTER / 2, Tf, Tf + SHUTTER / 2]) {
        for (const { gid, agent } of activeList(tt)) {
          if (!pool.has(gid)) { humanFor(gid, agent); lastUsed.set(gid, Tf); posedT = NaN; await tick(); }
        }
      }
    },
    render,
    people,
    footAt,
    events: eventsUpTo,
    resize,
    stats() {
      const s = renderMs.slice().sort((a, b) => a - b);
      return { level: LADDER[level], canvas: [W, H], render: passes.renderSize, people: pool.size, medianMs: s[s.length >> 1] || 0, calls: renderer.info.render.calls, triangles: renderer.info.render.triangles, programs: renderer.info.programs ? renderer.info.programs.length : 0 };
    },
    dispose() {
      if (ro) ro.disconnect();
      if (typeof window !== 'undefined') window.removeEventListener('resize', onWinResize);
      if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVisibility);
      for (const [, h] of pool) h.dispose();
      pool.clear();
      keeper.dispose();
      passes.dispose();
      renderer.dispose();
      canvas.remove();
    },
    _internal: { stateOf, renderer, scene, camera, env, crowd, pool, poseAt, setLevel, footWorld, activeList, passes, phaseOffset },
  };
}
