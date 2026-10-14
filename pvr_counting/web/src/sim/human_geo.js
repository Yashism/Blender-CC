// Geometry helpers for procedural people: a merged skinned-geometry builder and a
// "loft" (stack of closed cross-section rings) that every body part is made from.
//
// Conventions
// - Rest pose model space, metres, Y up, facing +Z, character's left = +X.
// - Each vertex carries up to 4 bone weights, a UV into the person's texture atlas
//   (rects are given in [0,1] canvas space: u right, v DOWN, flipped at the end)
//   and a vertex colour used as baked ambient occlusion.
import * as THREE from 'three';

const TAU = Math.PI * 2;

export function clamp(x, a, b) { return x < a ? a : x > b ? b : x; }
export function lerp(a, b, t) { return a + (b - a) * t; }
export function smooth(e0, e1, x) {
  const t = clamp((x - e0) / (e1 - e0), 0, 1);
  return t * t * (3 - 2 * t);
}
export function gauss(x, s) { const q = x / s; return q * q > 40 ? 0 : Math.exp(-0.5 * q * q); }
// wrap angle difference to [-pi, pi]
export function adiff(a, b) {
  let d = a - b;
  while (d > Math.PI) d -= TAU;
  while (d < -Math.PI) d += TAU;
  return d;
}

// Monotone cubic-ish interpolation of keyed tables: keys [[x, v0, v1, ...], ...] sorted by x.
// Returns a function x -> [v0, v1, ...] using Catmull-Rom with clamped ends.
export function keyed(keys) {
  const n = keys.length;
  const m = keys[0].length - 1;
  return function (x) {
    const out = new Array(m);
    if (x <= keys[0][0]) { for (let j = 0; j < m; j++) out[j] = keys[0][j + 1]; return out; }
    if (x >= keys[n - 1][0]) { for (let j = 0; j < m; j++) out[j] = keys[n - 1][j + 1]; return out; }
    let i = 0;
    while (i < n - 2 && x > keys[i + 1][0]) i++;
    const k0 = keys[Math.max(0, i - 1)], k1 = keys[i], k2 = keys[i + 1], k3 = keys[Math.min(n - 1, i + 2)];
    const t = (x - k1[0]) / (k2[0] - k1[0]);
    const t2 = t * t, t3 = t2 * t;
    for (let j = 1; j <= m; j++) {
      // Catmull-Rom with non-uniform spacing approximated by tangents scaled to the segment
      const d1 = (k2[0] - k1[0]);
      const m1 = (k1 === k0) ? (k2[j] - k1[j]) : (k2[j] - k0[j]) / (k2[0] - k0[0]) * d1;
      const m2 = (k3 === k2) ? (k2[j] - k1[j]) : (k3[j] - k1[j]) / (k3[0] - k1[0]) * d1;
      let v = (2 * t3 - 3 * t2 + 1) * k1[j] + (t3 - 2 * t2 + t) * m1 + (-2 * t3 + 3 * t2) * k2[j] + (t3 - t2) * m2;
      // keep monotone-ish: clamp to neighbour range to avoid overshoot bumps
      const lo = Math.min(k1[j], k2[j]), hi = Math.max(k1[j], k2[j]);
      const pad = (hi - lo) * 0.15;
      v = clamp(v, lo - pad, hi + pad);
      out[j - 1] = v;
    }
    return out;
  };
}

export class GeoBuilder {
  constructor() {
    this.cap = 4096;
    this.n = 0;
    this.pos = new Float32Array(this.cap * 3); this.nrm = new Float32Array(this.cap * 3);
    this.uv = new Float32Array(this.cap * 2); this.col = new Float32Array(this.cap * 3);
    this.si = new Uint16Array(this.cap * 4); this.sw = new Float32Array(this.cap * 4);
    this.idx = []; 
  }
  get count() { return this.n; }
  _grow() {
    const c = this.cap * 2;
    const g = (a, k) => { const b = new a.constructor(c * k); b.set(a); return b; };
    this.pos = g(this.pos, 3); this.nrm = g(this.nrm, 3); this.uv = g(this.uv, 2); this.col = g(this.col, 3);
    this.si = g(this.si, 4); this.sw = g(this.sw, 4);
    this.cap = c;
  }
  vert(p, n, u, v, c, w) {
    if (this.n >= this.cap) this._grow();
    const i = this.n;
    this.pos[i * 3] = p[0]; this.pos[i * 3 + 1] = p[1]; this.pos[i * 3 + 2] = p[2];
    this.nrm[i * 3] = n[0]; this.nrm[i * 3 + 1] = n[1]; this.nrm[i * 3 + 2] = n[2];
    this.uv[i * 2] = u; this.uv[i * 2 + 1] = 1 - v;
    this.col[i * 3] = c[0]; this.col[i * 3 + 1] = c[1]; this.col[i * 3 + 2] = c[2];
    // weights: [[bone, w], ...] -> top 4, normalised
    let m = w.length;
    let ws = w;
    if (m > 4) { ws = w.slice().sort((a, b) => b[1] - a[1]); m = 4; }
    let tot = 0;
    for (let k = 0; k < m; k++) tot += ws[k][1];
    for (let k = 0; k < 4; k++) {
      if (k < m && tot > 0) { this.si[i * 4 + k] = ws[k][0]; this.sw[i * 4 + k] = ws[k][1] / tot; }
      else { this.si[i * 4 + k] = 0; this.sw[i * 4 + k] = 0; }
    }
    this.n++;
    return i;
  }
  tri(a, b, c) { this.idx.push(a, b, c); }
  build() {
    const g = new THREE.BufferGeometry();
    const n = this.n;
    g.setAttribute('position', new THREE.BufferAttribute(this.pos.slice(0, n * 3), 3));
    g.setAttribute('normal', new THREE.BufferAttribute(this.nrm.slice(0, n * 3), 3));
    g.setAttribute('uv', new THREE.BufferAttribute(this.uv.slice(0, n * 2), 2));
    g.setAttribute('color', new THREE.BufferAttribute(this.col.slice(0, n * 3), 3));
    g.setAttribute('skinIndex', new THREE.BufferAttribute(this.si.slice(0, n * 4), 4));
    g.setAttribute('skinWeight', new THREE.BufferAttribute(this.sw.slice(0, n * 4), 4));
    g.setIndex(new THREE.BufferAttribute(n > 65535 ? new Uint32Array(this.idx) : new Uint16Array(this.idx), 1));
    g.computeBoundingSphere();
    return g;
  }
}

function sub(a, b) { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function cross(a, b) { return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]; }
function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function norm(a) { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }
export const v3 = { sub, cross, dot, norm };

// Loft: rings[k] = { c:[x,y,z], ax:[..], az:[..], f:(theta)=>[a,b], s: param, v: optional v }
// point(theta) = c + ax*a + az*b. theta in [0, 2pi). Ring order defines v (0..1 over rings
// unless ring.v given). Options:
//   n         segments around (multiple of 4 when arc)
//   arc       true: per-quadrant arc-length sampling (u = quadrant + fraction)/4
//   rect      [u0, v0, u1, v1] atlas rect (canvas space, v down)
//   uvAt      optional (p, u, v, s, th) -> [U, V] absolute atlas uv override (or null)
//   weights   (p, s, th) -> [[bone, w], ...]
//   color     (p, s, th, u) -> [r,g,b] (default white)
//   capStart / capEnd : number bulge (metres along the end direction) or null for open
//   flipU     mirror u
//   post      optional (P, N) -> void, may modify the grid points (e.g. offset) before building
export function loft(B, rings, opt) {
  const n = opt.n || 24;
  const K = rings.length;
  const P = new Array(K);
  const TH = new Array(K);
  for (let k = 0; k < K; k++) {
    const r = rings[k];
    const pts = new Array(n + 1);
    const ths = new Array(n + 1);
    if (opt.arc) {
      const D = 14;
      const q4 = n / 4;
      let idx = 0;
      for (let q = 0; q < 4; q++) {
        const th0 = q * Math.PI / 2;
        const cum = [0];
        let prev = r.f(th0);
        for (let j = 1; j <= D; j++) {
          const p = r.f(th0 + (j / D) * Math.PI / 2);
          cum.push(cum[j - 1] + Math.hypot(p[0] - prev[0], p[1] - prev[1]));
          prev = p;
        }
        const L = cum[D] || 1e-9;
        for (let m = 0; m < q4; m++) {
          const target = (m / q4) * L;
          let j = 0;
          while (j < D - 1 && cum[j + 1] < target) j++;
          const t = (target - cum[j]) / Math.max(1e-9, cum[j + 1] - cum[j]);
          ths[idx++] = th0 + ((j + t) / D) * Math.PI / 2;
        }
      }
      ths[n] = TAU;
    } else {
      for (let i = 0; i <= n; i++) ths[i] = (i / n) * TAU;
    }
    for (let i = 0; i <= n; i++) {
      const ab = r.f(i === n ? ths[0] : ths[i]);
      pts[i] = [
        r.c[0] + r.ax[0] * ab[0] + r.az[0] * ab[1],
        r.c[1] + r.ax[1] * ab[0] + r.az[1] * ab[1],
        r.c[2] + r.ax[2] * ab[0] + r.az[2] * ab[1],
      ];
    }
    P[k] = pts;
    TH[k] = ths;
  }
  return grid(B, P, TH, rings, opt);
}

// Normals of a ring grid by central differences (wrap around), oriented outward from ring centres.
export function gridNormals(P, rings) {
  const K = P.length, n = P[0].length - 1;
  const N = new Array(K);
  let orient = 0;
  for (let k = 0; k < K; k++) {
    N[k] = new Array(n + 1);
    const ka = Math.max(0, k - 1), kb = Math.min(K - 1, k + 1);
    for (let i = 0; i < n; i++) {
      const ia = (i - 1 + n) % n, ib = (i + 1) % n;
      const tth = sub(P[k][ib], P[k][ia]);
      let ts = sub(P[kb][i], P[ka][i]);
      if (Math.hypot(ts[0], ts[1], ts[2]) < 1e-9) ts = cross(rings[k].ax, rings[k].az);
      let nn = cross(ts, tth);
      if (Math.hypot(nn[0], nn[1], nn[2]) < 1e-12) nn = sub(P[k][i], rings[k].c);
      N[k][i] = norm(nn);
      orient += dot(N[k][i], sub(P[k][i], rings[k].c));
    }
  }
  const sgn = orient >= 0 ? 1 : -1;
  for (let k = 0; k < K; k++) {
    for (let i = 0; i < n; i++) { const q = N[k][i]; N[k][i] = [q[0] * sgn, q[1] * sgn, q[2] * sgn]; }
    N[k][n] = N[k][0];
  }
  return N;
}

export function grid(B, P, TH, rings, opt) {
  const K = P.length, n = P[0].length - 1;
  const rect = opt.rect || [0, 0, 1, 1];
  let N = gridNormals(P, rings);
  if (opt.post) { opt.post(P, N); N = gridNormals(P, rings); }
  const vOf = (k) => (rings[k].v !== undefined ? rings[k].v : (K === 1 ? 0 : k / (K - 1)));
  const toUV = (u, v) => {
    if (opt.flipU) u = 1 - u;
    return [rect[0] + (rect[2] - rect[0]) * u, rect[1] + (rect[3] - rect[1]) * v];
  };
  const white = [1, 1, 1];
  const ids = new Array(K);
  for (let k = 0; k < K; k++) {
    ids[k] = new Array(n + 1);
    const s = rings[k].s !== undefined ? rings[k].s : vOf(k);
    for (let i = 0; i <= n; i++) {
      const th = i === n ? TAU : TH[k][i];
      const u = opt.arc ? (i / n) : th / TAU;
      const p = P[k][i];
      let uv = opt.uvAt ? opt.uvAt(p, u, vOf(k), s, th % TAU) : null;
      if (!uv) uv = toUV(u, vOf(k));
      const w = opt.weights(p, s, th % TAU);
      const c = opt.color ? opt.color(p, s, th % TAU, u) : white;
      ids[k][i] = B.vert(p, N[k][i], uv[0], uv[1], c, w);
    }
  }
  for (let k = 0; k < K - 1; k++) {
    for (let i = 0; i < n; i++) {
      const a = ids[k][i], b = ids[k][i + 1], c = ids[k + 1][i + 1], d = ids[k + 1][i];
      const pa = P[k][i], pb = P[k][i + 1], pc = P[k + 1][i + 1], pd = P[k + 1][i];
      let tn = cross(sub(pb, pa), sub(pc, pa));
      if (Math.hypot(tn[0], tn[1], tn[2]) < 1e-14) tn = cross(sub(pc, pa), sub(pd, pa));
      const nn = [N[k][i][0] + N[k + 1][i + 1][0], N[k][i][1] + N[k + 1][i + 1][1], N[k][i][2] + N[k + 1][i + 1][2]];
      if (dot(tn, nn) < 0) { B.tri(a, b, c); B.tri(a, c, d); }
      else { B.tri(a, c, b); B.tri(a, d, c); }
    }
  }
  const cap = (k, bulge, end) => {
    if (bulge === null || bulge === undefined) return;
    const r = rings[k];
    let ctr = [0, 0, 0];
    for (let i = 0; i < n; i++) { ctr[0] += P[k][i][0]; ctr[1] += P[k][i][1]; ctr[2] += P[k][i][2]; }
    ctr = [ctr[0] / n, ctr[1] / n, ctr[2] / n];
    const k2 = end ? Math.max(0, k - 1) : Math.min(K - 1, k + 1);
    let c2 = [0, 0, 0];
    for (let i = 0; i < n; i++) { c2[0] += P[k2][i][0]; c2[1] += P[k2][i][1]; c2[2] += P[k2][i][2]; }
    c2 = [c2[0] / n, c2[1] / n, c2[2] / n];
    let dir = sub(ctr, c2);
    if (Math.hypot(dir[0], dir[1], dir[2]) < 1e-9) dir = cross(r.ax, r.az);
    dir = norm(dir);
    const pole = [ctr[0] + dir[0] * bulge, ctr[1] + dir[1] * bulge, ctr[2] + dir[2] * bulge];
    const s = r.s !== undefined ? r.s : vOf(k);
    let uv = opt.uvAt ? opt.uvAt(pole, 0.5, vOf(k), s, 0) : null;
    if (!uv) uv = toUV(0.5, vOf(k));
    const pid = B.vert(pole, dir, uv[0], uv[1], opt.color ? opt.color(pole, s, 0, 0.5) : white, opt.weights(pole, s, 0));
    for (let i = 0; i < n; i++) {
      const a = ids[k][i], b = ids[k][i + 1];
      const pa = P[k][i], pb = P[k][i + 1];
      const tn = cross(sub(pb, pa), sub(pole, pa));
      if (dot(tn, dir) > 0) B.tri(a, b, pid); else B.tri(a, pid, b);
    }
  };
  cap(0, opt.capStart, false);
  cap(K - 1, opt.capEnd, true);
  return { P, N, ids };
}

// Superellipse helper: returns [a, b] for angle th with half-sizes ra, rb and exponent e (2 = ellipse)
export function sellipse(th, ra, rb, e = 2) {
  const c = Math.cos(th), s = Math.sin(th);
  const p = 2 / e;
  return [ra * Math.sign(c) * Math.pow(Math.abs(c), p), rb * Math.sign(s) * Math.pow(Math.abs(s), p)];
}

// Ellipsoid made of rings stacked along `up`, closed with poles.
export function ellipsoid(B, center, radii, basis, opt) {
  // basis: { x:[..], y:[..], z:[..] } unit axes; radii [rx, ry, rz]
  const nLat = opt.nLat || 8;
  const rings = [];
  for (let j = 1; j < nLat; j++) {
    const lat = -Math.PI / 2 + (j / nLat) * Math.PI;
    const cy = Math.sin(lat) * radii[1];
    const cr = Math.cos(lat);
    const bump = opt.bump;
    rings.push({
      c: [center[0] + basis.y[0] * cy, center[1] + basis.y[1] * cy, center[2] + basis.y[2] * cy],
      ax: basis.x, az: basis.z,
      f: bump ? (th) => { const k = 1 + bump(th, lat); return [radii[0] * cr * Math.cos(th) * k, radii[2] * cr * Math.sin(th) * k]; }
        : (th) => [radii[0] * cr * Math.cos(th), radii[2] * cr * Math.sin(th)],
      s: j / nLat,
    });
  }
  const capLen = radii[1] * (1 - Math.cos(Math.PI / nLat));
  return loft(B, rings, Object.assign({}, opt, { capStart: capLen, capEnd: capLen }));
}

// Catmull-Rom path sampling: pts array of [x,y,z]; returns { p, t } samples
export function pathSample(pts, count) {
  const out = [];
  const n = pts.length;
  for (let i = 0; i < count; i++) {
    const f = (i / (count - 1)) * (n - 1);
    const seg = Math.min(n - 2, Math.floor(f));
    const t = f - seg;
    const p0 = pts[Math.max(0, seg - 1)], p1 = pts[seg], p2 = pts[seg + 1], p3 = pts[Math.min(n - 1, seg + 2)];
    const p = [0, 0, 0], d = [0, 0, 0];
    for (let j = 0; j < 3; j++) {
      const a = -0.5 * p0[j] + 1.5 * p1[j] - 1.5 * p2[j] + 0.5 * p3[j];
      const b = p0[j] - 2.5 * p1[j] + 2 * p2[j] - 0.5 * p3[j];
      const c = -0.5 * p0[j] + 0.5 * p2[j];
      p[j] = ((a * t + b) * t + c) * t + p1[j];
      d[j] = (3 * a * t + 2 * b) * t + c;
    }
    out.push({ p, t: norm(d) });
  }
  return out;
}

// Ribbon / strap along a path: flat rounded cross-section width w (along side) and thickness th.
// sideHint(p, t) returns a vector roughly along the strap width.
export function ribbon(B, pts, count, w, th, sideHint, opt) {
  const S = pathSample(pts, count);
  const rings = S.map((smp, k) => {
    let side = sideHint(smp.p, smp.t, k / (count - 1));
    // orthogonalise side against tangent
    const d = dot(side, smp.t);
    side = norm([side[0] - smp.t[0] * d, side[1] - smp.t[1] * d, side[2] - smp.t[2] * d]);
    const nrm = norm(cross(smp.t, side));
    const ww = typeof w === 'function' ? w(k / (count - 1)) : w;
    const tt = typeof th === 'function' ? th(k / (count - 1)) : th;
    return { c: smp.p, ax: side, az: nrm, f: (a) => sellipse(a, ww / 2, tt / 2, opt.e || 6), s: k / (count - 1) };
  });
  return loft(B, rings, opt);
}
