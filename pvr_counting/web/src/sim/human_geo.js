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
    this.cap = 12288;
    this.n = 0;
    this.pos = new Float32Array(this.cap * 3); this.nrm = new Float32Array(this.cap * 3);
    this.uv = new Float32Array(this.cap * 2); this.col = new Float32Array(this.cap * 3);
    this.si = new Uint16Array(this.cap * 4); this.sw = new Float32Array(this.cap * 4);
    this.idx = new Uint32Array(this.cap * 6); this.ni = 0;
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
  tri(a, b, c) {
    if (this.ni + 3 > this.idx.length) { const g = new Uint32Array(this.idx.length * 2); g.set(this.idx); this.idx = g; }
    this.idx[this.ni++] = a; this.idx[this.ni++] = b; this.idx[this.ni++] = c;
  }
  build() {
    const g = new THREE.BufferGeometry();
    const n = this.n;
    g.setAttribute('position', new THREE.BufferAttribute(this.pos.slice(0, n * 3), 3));
    g.setAttribute('normal', new THREE.BufferAttribute(this.nrm.slice(0, n * 3), 3));
    g.setAttribute('uv', new THREE.BufferAttribute(this.uv.slice(0, n * 2), 2));
    g.setAttribute('color', new THREE.BufferAttribute(this.col.slice(0, n * 3), 3));
    g.setAttribute('skinIndex', new THREE.BufferAttribute(this.si.slice(0, n * 4), 4));
    g.setAttribute('skinWeight', new THREE.BufferAttribute(this.sw.slice(0, n * 4), 4));
    const ix = this.idx.subarray(0, this.ni);
    g.setIndex(new THREE.BufferAttribute(n > 65535 ? ix.slice() : Uint16Array.from(ix), 1));
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
      const D = 10;
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
    const row = new Array(n + 1);
    N[k] = row;
    const ka = Math.max(0, k - 1), kb = Math.min(K - 1, k + 1);
    const Pk = P[k], Pa = P[ka], Pb = P[kb];
    const c = rings[k].c;
    for (let i = 0; i < n; i++) {
      const ia = i === 0 ? n - 1 : i - 1, ib = i === n - 1 ? 0 : i + 1;
      const tx = Pk[ib][0] - Pk[ia][0], ty = Pk[ib][1] - Pk[ia][1], tz = Pk[ib][2] - Pk[ia][2];
      let sx = Pb[i][0] - Pa[i][0], sy = Pb[i][1] - Pa[i][1], sz = Pb[i][2] - Pa[i][2];
      if (sx * sx + sy * sy + sz * sz < 1e-18) {
        const ax = rings[k].ax, az = rings[k].az;
        sx = ax[1] * az[2] - ax[2] * az[1]; sy = ax[2] * az[0] - ax[0] * az[2]; sz = ax[0] * az[1] - ax[1] * az[0];
      }
      let nx = sy * tz - sz * ty, ny = sz * tx - sx * tz, nz = sx * ty - sy * tx;
      let l = Math.sqrt(nx * nx + ny * ny + nz * nz);
      const px = Pk[i][0] - c[0], py = Pk[i][1] - c[1], pz = Pk[i][2] - c[2];
      if (l < 1e-12) { nx = px; ny = py; nz = pz; l = Math.sqrt(nx * nx + ny * ny + nz * nz) || 1; }
      nx /= l; ny /= l; nz /= l;
      row[i] = [nx, ny, nz];
      orient += nx * px + ny * py + nz * pz;
    }
  }
  if (orient < 0) for (let k = 0; k < K; k++) for (let i = 0; i < n; i++) { const q = N[k][i]; q[0] = -q[0]; q[1] = -q[1]; q[2] = -q[2]; }
  for (let k = 0; k < K; k++) N[k][n] = N[k][0];
  return N;
}

export function grid(B, P, TH, rings, opt) {
  const K = P.length, n = P[0].length - 1;
  const rect = opt.rect || [0, 0, 1, 1];
  let N = gridNormals(P, rings);
  if (opt.post) { opt.post(P, N); N = gridNormals(P, rings); }
  const vOf = (k) => (rings[k].v !== undefined ? rings[k].v : (K === 1 ? 0 : k / (K - 1)));
  const ru = rect[2] - rect[0], rv = rect[3] - rect[1];
  const white = [1, 1, 1];
  const ids = new Array(K);
  const uvb = [0, 0];
  for (let k = 0; k < K; k++) {
    const idk = new Array(n + 1);
    ids[k] = idk;
    const s = rings[k].s !== undefined ? rings[k].s : vOf(k);
    const vk = vOf(k);
    for (let i = 0; i <= n; i++) {
      const th = i === n ? TAU : TH[k][i];
      let u = opt.arc ? (i / n) : th / TAU;
      const p = P[k][i];
      let uv = opt.uvAt ? opt.uvAt(p, u, vk, s, th % TAU) : null;
      if (!uv) { if (opt.flipU) u = 1 - u; uvb[0] = rect[0] + ru * u; uvb[1] = rect[1] + rv * vk; uv = uvb; }
      const w = opt.weights(p, s, th % TAU);
      const c = opt.color ? opt.color(p, s, th % TAU, u) : white;
      idk[i] = B.vert(p, N[k][i], uv[0], uv[1], c, w);
    }
  }
  // winding: decide once per loft from the summed agreement of quad normals with vertex normals
  let agree = 0;
  for (let k = 0; k < K - 1; k++) {
    for (let i = 0; i < n; i++) {
      const pa = P[k][i], pb = P[k][i + 1], pc = P[k + 1][i + 1];
      const e1x = pb[0] - pa[0], e1y = pb[1] - pa[1], e1z = pb[2] - pa[2];
      const e2x = pc[0] - pa[0], e2y = pc[1] - pa[1], e2z = pc[2] - pa[2];
      const tx = e1y * e2z - e1z * e2y, ty = e1z * e2x - e1x * e2z, tz = e1x * e2y - e1y * e2x;
      const q = N[k][i];
      agree += tx * q[0] + ty * q[1] + tz * q[2];
    }
  }
  const ccw = agree > 0;
  for (let k = 0; k < K - 1; k++) {
    const r0 = ids[k], r1 = ids[k + 1];
    for (let i = 0; i < n; i++) {
      const a = r0[i], b = r0[i + 1], c = r1[i + 1], d = r1[i];
      if (ccw) { B.tri(a, b, c); B.tri(a, c, d); }
      else { B.tri(a, c, b); B.tri(a, d, c); }
    }
  }
  const cap = (k, bulge, end) => {
    if (bulge === null || bulge === undefined) return;
    const r = rings[k];
    let cx = 0, cy = 0, cz = 0;
    for (let i = 0; i < n; i++) { cx += P[k][i][0]; cy += P[k][i][1]; cz += P[k][i][2]; }
    cx /= n; cy /= n; cz /= n;
    const k2 = end ? Math.max(0, k - 1) : Math.min(K - 1, k + 1);
    let dx = 0, dy = 0, dz = 0;
    for (let i = 0; i < n; i++) { dx += P[k2][i][0]; dy += P[k2][i][1]; dz += P[k2][i][2]; }
    dx = cx - dx / n; dy = cy - dy / n; dz = cz - dz / n;
    let l = Math.sqrt(dx * dx + dy * dy + dz * dz);
    if (l < 1e-9) { const c2 = cross(r.ax, r.az); dx = c2[0]; dy = c2[1]; dz = c2[2]; l = Math.sqrt(dx * dx + dy * dy + dz * dz) || 1; }
    const dir = [dx / l, dy / l, dz / l];
    const pole = [cx + dir[0] * bulge, cy + dir[1] * bulge, cz + dir[2] * bulge];
    const s = r.s !== undefined ? r.s : vOf(k);
    let uv = opt.uvAt ? opt.uvAt(pole, 0.5, vOf(k), s, 0) : null;
    if (!uv) uv = [rect[0] + ru * 0.5, rect[1] + rv * vOf(k)];
    const pid = B.vert(pole, dir, uv[0], uv[1], opt.color ? opt.color(pole, s, 0, 0.5) : white, opt.weights(pole, s, 0));
    for (let i = 0; i < n; i++) {
      const a = ids[k][i], b = ids[k][i + 1];
      const pa = P[k][i], pb = P[k][i + 1];
      const e1x = pb[0] - pa[0], e1y = pb[1] - pa[1], e1z = pb[2] - pa[2];
      const e2x = pole[0] - pa[0], e2y = pole[1] - pa[1], e2z = pole[2] - pa[2];
      const tx = e1y * e2z - e1z * e2y, ty = e1z * e2x - e1x * e2z, tz = e1x * e2y - e1y * e2x;
      if (tx * dir[0] + ty * dir[1] + tz * dir[2] > 0) B.tri(a, b, pid); else B.tri(a, pid, b);
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
    const tk = k / (count - 1);
    return { c: smp.p, ax: side, az: nrm, f: opt.shape ? (a) => opt.shape(a, tk, ww, tt) : (a) => sellipse(a, ww / 2, tt / 2, opt.e || 6), s: tk };
  });
  return loft(B, rings, opt);
}

// Smooth 3-D value noise in [-1, 1] (deterministic, seeded). Used for cloth wrinkles / hair clumps.
function h3(seed, x, y, z) {
  let h = Math.imul(x | 0, 0x27d4eb2d) ^ Math.imul(y | 0, 0x165667b1) ^ Math.imul(z | 0, 0x9e3779b1) ^ Math.imul(seed | 0, 0x85ebca6b);
  h ^= h >>> 15; h = Math.imul(h, 0x2c1b3c6d); h ^= h >>> 12; h = Math.imul(h, 0x297a2d39); h ^= h >>> 15;
  return ((h >>> 0) / 4294967296) * 2 - 1;
}
export function noise3(seed, x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = x - xi, yf = y - yi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf), w = zf * zf * (3 - 2 * zf);
  const l = (a, b, t) => a + (b - a) * t;
  return l(
    l(l(h3(seed, xi, yi, zi), h3(seed, xi + 1, yi, zi), u), l(h3(seed, xi, yi + 1, zi), h3(seed, xi + 1, yi + 1, zi), u), v),
    l(l(h3(seed, xi, yi, zi + 1), h3(seed, xi + 1, yi, zi + 1), u), l(h3(seed, xi, yi + 1, zi + 1), h3(seed, xi + 1, yi + 1, zi + 1), u), v),
    w);
}
// Displace grid points along normals: amp(p) metres, scale = [sx, sy, sz] noise frequency (1/m).
export function wrinkle(P, N, seed, amp, scale, octaves = 2) {
  for (let k = 0; k < P.length; k++) {
    const row = P[k];
    for (let i = 0; i < row.length; i++) {
      const p = row[i];
      const a = amp(p, k, i);
      if (!a) continue;
      let n = 0, f = 1, g = 1, tot = 0;
      for (let o = 0; o < octaves; o++) {
        n += g * noise3(seed + o * 101, p[0] * scale[0] * f, p[1] * scale[1] * f, p[2] * scale[2] * f);
        tot += g; f *= 2.1; g *= 0.5;
      }
      n /= tot;
      const q = N[k][i];
      row[i] = [p[0] + q[0] * a * n, p[1] + q[1] * a * n, p[2] + q[2] * a * n];
    }
  }
}
