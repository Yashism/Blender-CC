// Procedural textures for the cinema entrance. Everything is generated in code
// (seeded, deterministic), no image files. Each generator returns a set of
// THREE textures sized in metres via `tile` so materials can map them with
// world-scaled UVs (1 UV unit = 1 metre).
import * as THREE from 'three';
import { mulberry32 } from './rng.js';

// ---------------------------------------------------------------------------
// helpers

function makeCanvas(w, h) {
  if (typeof document === 'undefined' && typeof OffscreenCanvas !== 'undefined') return new OffscreenCanvas(w, h);
  const c = document.createElement('canvas');
  c.width = w; c.height = h;
  return c;
}

// Tileable value noise on an integer lattice of size `period`.
function periodicNoise(seed, period) {
  const n = period * period;
  const v = new Float32Array(n);
  const r = mulberry32(seed);
  for (let i = 0; i < n; i++) v[i] = r();
  return (x, y) => {
    const xi = Math.floor(x), yi = Math.floor(y);
    let fx = x - xi, fy = y - yi;
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
    const x0 = ((xi % period) + period) % period, y0 = ((yi % period) + period) % period;
    const x1 = (x0 + 1) % period, y1 = (y0 + 1) % period;
    const a = v[y0 * period + x0], b = v[y0 * period + x1], c = v[y1 * period + x0], d = v[y1 * period + x1];
    return (a + (b - a) * fx) + ((c + (d - c) * fx) - (a + (b - a) * fx)) * fy;
  };
}

// Tileable fBm over a W x H pixel grid; base lattice `cells` across the tile.
function fbmField(W, H, seed, cells, octaves = 4, gain = 0.5) {
  const out = new Float32Array(W * H);
  let amp = 1, total = 0;
  for (let o = 0; o < octaves; o++) {
    const p = cells << o;
    const nz = periodicNoise(seed + o * 101, p);
    const sx = p / W, sy = p / H;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) out[y * W + x] += amp * nz(x * sx, y * sy);
    total += amp; amp *= gain;
  }
  for (let i = 0; i < out.length; i++) out[i] /= total;
  return out;
}

// Normal map (tangent space, OpenGL convention) from a tileable height field.
function normalFromHeight(h, W, H, strength) {
  const c = makeCanvas(W, H), ctx = c.getContext('2d');
  const img = ctx.createImageData(W, H), d = img.data;
  for (let y = 0; y < H; y++) {
    const ym = ((y - 1 + H) % H) * W, yp = ((y + 1) % H) * W, y0 = y * W;
    for (let x = 0; x < W; x++) {
      const xm = (x - 1 + W) % W, xp = (x + 1) % W;
      const dx = (h[y0 + xp] - h[y0 + xm]) * strength;
      const dy = (h[ym + x] - h[yp + x]) * strength; // canvas y is down, uv v is up
      const inv = 1 / Math.sqrt(dx * dx + dy * dy + 1);
      const i = (y0 + x) * 4;
      d[i] = (-dx * inv * 0.5 + 0.5) * 255;
      d[i + 1] = (-dy * inv * 0.5 + 0.5) * 255;
      d[i + 2] = (inv * 0.5 + 0.5) * 255;
      d[i + 3] = 255;
    }
  }
  ctx.putImageData(img, 0, 0);
  return c;
}

function greyCanvas(v, W, H) {
  const c = makeCanvas(W, H), ctx = c.getContext('2d');
  const img = ctx.createImageData(W, H), d = img.data;
  for (let i = 0; i < W * H; i++) {
    const g = Math.max(0, Math.min(255, v[i] * 255));
    d[i * 4] = d[i * 4 + 1] = d[i * 4 + 2] = g; d[i * 4 + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
  return c;
}

function tex(canvas, { srgb = false, renderer = null, repeat = true } = {}) {
  const t = new THREE.CanvasTexture(canvas);
  t.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  if (repeat) t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = renderer ? Math.min(8, renderer.capabilities.getMaxAnisotropy()) : 4;
  t.generateMipmaps = true;
  t.minFilter = THREE.LinearMipmapLinearFilter;
  t.magFilter = THREE.LinearFilter;
  t.needsUpdate = true;
  return t;
}

function setTile(set, sx, sy) {
  for (const k of Object.keys(set)) if (set[k] && set[k].isTexture) set[k].repeat.set(1 / sx, 1 / sy);
  set.tile = [sx, sy];
  return set;
}

const clamp01 = (v) => (v < 0 ? 0 : v > 1 ? 1 : v);

const cache = new Map();
function cached(key, fn) {
  if (!cache.has(key)) cache.set(key, fn());
  return cache.get(key);
}

// ---------------------------------------------------------------------------
// Carpet: dark maroon cut pile with a small staggered tan "clover" motif and
// scattered flecks. Tile = 1.92 m (8 x 8 motif cells of 0.24 m, staggered).

export function carpetTextures(renderer) {
  return cached('carpet', () => {
    const W = 1024, H = 1024, CELLS = 8, cell = W / CELLS;
    const rnd = mulberry32(9001);
    const fib = new Float32Array(W * H);
    for (let i = 0; i < fib.length; i++) fib[i] = rnd();
    const mott = fbmField(W, H, 77, 4, 4, 0.55);
    const tuft = fbmField(W, H, 91, 128, 2, 0.5);   // tuft clusters (~8 px)
    const mid = fbmField(W, H, 93, 16, 3, 0.5);

    // motif mask: small irregular clover clusters on a staggered lattice
    const mc = makeCanvas(W, H), mx = mc.getContext('2d');
    mx.fillStyle = '#000'; mx.fillRect(0, 0, W, H);
    const drawMotif = (cx, cy, rot, sc, bright) => {
      const petals = rnd() < 0.35 ? 5 : 4;
      const jit = [];
      for (let k = 0; k < petals + 3; k++) jit.push(rnd());
      for (const ox of [-W, 0, W]) for (const oy of [-H, 0, H]) {
        const X = cx + ox, Y = cy + oy;
        if (X < -40 || X > W + 40 || Y < -40 || Y > H + 40) continue;
        mx.save();
        mx.translate(X, Y);
        mx.rotate(rot);
        mx.fillStyle = `rgba(255,255,255,${bright})`;
        for (let k = 0; k < petals; k++) {
          const a = (k / petals) * Math.PI * 2 + (jit[k] - 0.5) * 0.6;
          const r = (2.2 + 0.8 * jit[k]) * sc;
          const dd = (6.2 + 1.4 * jit[(k + 1) % jit.length]) * sc;
          mx.beginPath();
          mx.ellipse(Math.cos(a) * dd, Math.sin(a) * dd, r, r * 0.8, a, 0, Math.PI * 2);
          mx.fill();
        }
        mx.beginPath(); mx.arc(0, 0, 1.4 * sc, 0, Math.PI * 2); mx.fill();
        // a couple of loose dots around the cluster
        mx.fillStyle = `rgba(255,255,255,${0.7 * bright})`;
        for (let k = 0; k < 2; k++) {
          const a = jit[petals + k] * Math.PI * 2;
          mx.beginPath(); mx.arc(Math.cos(a) * 15 * sc, Math.sin(a) * 15 * sc, 1.8 * sc, 0, Math.PI * 2); mx.fill();
        }
        mx.restore();
      }
    };
    for (let j = 0; j < CELLS; j++) for (let i = 0; i < CELLS; i++) {
      for (const [ox, oy] of [[0.5, 0.5], [0, 0]]) {
        const jx = (rnd() - 0.5) * 6, jy = (rnd() - 0.5) * 6;
        drawMotif((i + ox) * cell + jx, (j + oy) * cell + jy, rnd() * Math.PI, 1.25 + rnd() * 0.25, 0.7 + rnd() * 0.3);
      }
    }
    // scattered light flecks (heathered yarn)
    for (let k = 0; k < 1800; k++) {
      const x = rnd() * W, y = rnd() * H, r = 0.6 + rnd() * 0.8;
      mx.fillStyle = `rgba(255,255,255,${0.45 + rnd() * 0.55})`;
      mx.beginPath(); mx.arc(x, y, r, 0, Math.PI * 2); mx.fill();
    }
    const mask = mx.getImageData(0, 0, W, H).data;

    const col = makeCanvas(W, H), cx = col.getContext('2d');
    const img = cx.createImageData(W, H), d = img.data;
    const height = new Float32Array(W * H);
    const rough = new Float32Array(W * H);
    for (let i = 0; i < W * H; i++) {
      const m = mask[i * 4] / 255;
      const f = fib[i], mo = mott[i], tu = tuft[i], md = mid[i];
      // base maroon: pile speckle + tuft clusters + broad mottle
      const shade = 0.70 + 0.44 * mo + 0.30 * (tu - 0.5) + 0.22 * (f - 0.5) + 0.22 * (md - 0.5);
      let r = 67 * shade, g = 31 * shade, b = 31 * shade;
      // motif yarn: muted tan, takes the pile texture too
      const ms = 0.8 + 0.35 * (f - 0.5) + 0.3 * (tu - 0.5);
      const mm = m * 0.95;
      r = r * (1 - mm) + 150 * ms * mm;
      g = g * (1 - mm) + 102 * ms * mm;
      b = b * (1 - mm) + 70 * ms * mm;
      d[i * 4] = Math.min(255, r); d[i * 4 + 1] = Math.min(255, g); d[i * 4 + 2] = Math.min(255, b); d[i * 4 + 3] = 255;
      height[i] = 0.5 * f + 0.7 * tu + 0.25 * m;
      rough[i] = clamp01(0.84 + 0.14 * f - 0.05 * m);
    }
    cx.putImageData(img, 0, 0);
    const set = {
      map: tex(col, { srgb: true, renderer }),
      normalMap: tex(normalFromHeight(height, W, H, 1.8), { renderer }),
      roughnessMap: tex(greyCanvas(rough, W, H), { renderer }),
    };
    return setTile(set, 1.92, 1.92);
  });
}

// ---------------------------------------------------------------------------
// Acoustic fabric wall panels: dark charcoal with an olive cast, felt-like.
// Tile 1.0 m.

export function fabricTextures(renderer) {
  return cached('fabric', () => {
    const W = 1024, H = 1024;
    const rnd = mulberry32(4242);
    const lo = fbmField(W, H, 13, 3, 4, 0.6);
    const hi = fbmField(W, H, 17, 96, 2, 0.5);
    // lumpy felt / sprayed acoustic finish: thousands of soft blobs (tileable)
    const bc = makeCanvas(W, H), bx = bc.getContext('2d');
    bx.fillStyle = '#000'; bx.fillRect(0, 0, W, H);
    bx.globalCompositeOperation = 'lighter';
    for (let k = 0; k < 7000; k++) {
      const x = rnd() * W, y = rnd() * H, r = 3 + rnd() * rnd() * 11, a = 0.10 + rnd() * 0.16;
      for (const ox of [-W, 0, W]) for (const oy of [-H, 0, H]) {
        const X = x + ox, Y = y + oy;
        if (X < -r || X > W + r || Y < -r || Y > H + r) continue;
        const g = bx.createRadialGradient(X, Y, 0, X, Y, r);
        g.addColorStop(0, `rgba(255,255,255,${a})`);
        g.addColorStop(1, 'rgba(255,255,255,0)');
        bx.fillStyle = g;
        bx.fillRect(X - r, Y - r, 2 * r, 2 * r);
      }
    }
    const blobs = bx.getImageData(0, 0, W, H).data;
    const col = makeCanvas(W, H), cx = col.getContext('2d');
    const img = cx.createImageData(W, H), d = img.data;
    const height = new Float32Array(W * H);
    for (let i = 0; i < W * H; i++) {
      const f = rnd();
      const b = blobs[i * 4] / 255;
      const s = 0.86 + 0.2 * lo[i] + 0.16 * (hi[i] - 0.5) + 0.14 * (f - 0.5) + 0.10 * (b - 0.4);
      d[i * 4] = 62 * s; d[i * 4 + 1] = 61 * s; d[i * 4 + 2] = 56 * s; d[i * 4 + 3] = 255;
      height[i] = 0.9 * b + 0.25 * hi[i] + 0.08 * f;
    }
    cx.putImageData(img, 0, 0);
    return setTile({
      map: tex(col, { srgb: true, renderer }),
      normalMap: tex(normalFromHeight(height, W, H, 3.2), { renderer }),
    }, 1.0, 1.0);
  });
}

// Darker velvet for auditorium seats / reveal lining.
export function velvetTextures(renderer) {
  return cached('velvet', () => {
    const W = 256, H = 256;
    const lo = fbmField(W, H, 5, 4, 3, 0.5);
    const rnd = mulberry32(55);
    const h = new Float32Array(W * H);
    for (let i = 0; i < W * H; i++) h[i] = 0.5 * lo[i] + 0.5 * rnd();
    return setTile({ normalMap: tex(normalFromHeight(h, W, H, 0.8), { renderer }) }, 0.5, 0.5);
  });
}

// ---------------------------------------------------------------------------
// Brushed brass: roughness + normal streaks along U (the trim's long axis).
// Tile 0.5 m along, 0.05 m across.

export function brassTextures(renderer) {
  return cached('brass', () => {
    const W = 1024, H = 64;
    const rnd = mulberry32(31337);
    const rowN = new Float32Array(H * 8);
    for (let i = 0; i < rowN.length; i++) rowN[i] = rnd();
    const lo = fbmField(W, H, 23, 4, 3, 0.5);
    const rough = new Float32Array(W * H), height = new Float32Array(W * H);
    const col = makeCanvas(W, H), cx = col.getContext('2d');
    const img = cx.createImageData(W, H), d = img.data;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x;
      // streaks: per-row noise stretched along x
      const k = Math.floor(x / W * 8);
      const s = rowN[y * 8 + k] * 0.6 + rnd() * 0.15 + 0.25 * lo[i];
      rough[i] = 0.26 + 0.18 * s;
      height[i] = s;
      // tarnish / patina variation in colour (multiplies material colour)
      const t = 0.88 + 0.16 * lo[i] + 0.06 * (s - 0.5);
      d[i * 4] = 255 * Math.min(1, t); d[i * 4 + 1] = 255 * Math.min(1, t * 0.98); d[i * 4 + 2] = 255 * Math.min(1, t * 0.94); d[i * 4 + 3] = 255;
    }
    cx.putImageData(img, 0, 0);
    return setTile({
      map: tex(col, { srgb: true, renderer }),
      roughnessMap: tex(greyCanvas(rough, W, H), { renderer }),
      normalMap: tex(normalFromHeight(height, W, H, 0.6), { renderer }),
    }, 0.5, 0.05);
  });
}

// ---------------------------------------------------------------------------
// Button-tufted upholstery for the door leaves (one texture = one whole leaf).
// Diamond tufting, covered buttons, a flat welted border.

export function tuftedTextures(renderer, leafW = 1.26, leafH = 2.56) {
  return cached('tufted', () => {
    const W = 512, H = 1024;
    const pxm = W / leafW; // px per metre
    const border = 0.07 * pxm;
    const sx = 0.18 * pxm, sy = 0.22 * pxm; // diamond lattice spacing
    const rnd = mulberry32(777);
    const fine = fbmField(W, H, 3, 64, 2, 0.5);
    const lo = fbmField(W, H, 8, 4, 3, 0.6);
    const height = new Float32Array(W * H);
    const ao = new Float32Array(W * H);
    const x0 = W / 2, y0 = border + sy * 0.5;
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x;
      const inBorder = x < border || x > W - border || y < border || y > H - border;
      // lattice coords: buttons at (i*sx, j*sy) with alternating half offsets
      const u = (x - x0) / sx, v = (y - y0) / sy;
      // distance to nearest button in a diamond lattice (two interleaved rect grids)
      const du1 = u - Math.round(u), dv1 = v - Math.round(v);
      const du2 = u - 0.5 - Math.round(u - 0.5), dv2 = v - 0.5 - Math.round(v - 0.5);
      const d1 = Math.hypot(du1 * sx, dv1 * sy), d2 = Math.hypot(du2 * sx, dv2 * sy);
      const dmin = Math.min(d1, d2) / pxm; // metres to the nearest button
      // cushion: rises with distance from buttons, creased along the diamond diagonals
      const diag = Math.min(Math.abs(Math.abs(du1) - Math.abs(dv1)), 1); // 0 on crease lines
      let hgt = Math.min(1, dmin / 0.09);
      hgt = Math.sqrt(hgt) * (0.75 + 0.25 * Math.min(1, diag * 5));
      let a = 0.78 + 0.22 * hgt;
      if (dmin < 0.011) { hgt = 0.35; a = 0.6; } // the covered button itself
      if (inBorder) {
        const e = Math.min(x, W - x, y, H - y);
        hgt = 0.6 + 0.2 * Math.min(1, e / 8);
        a = e < border - 3 ? 0.92 : 0.6;
      }
      height[i] = hgt + 0.03 * fine[i] + 0.02 * rnd();
      ao[i] = a;
    }
    const col = makeCanvas(W, H), cx = col.getContext('2d');
    const img = cx.createImageData(W, H), d = img.data;
    for (let i = 0; i < W * H; i++) {
      const s = ao[i] * (0.9 + 0.15 * lo[i] + 0.08 * (fine[i] - 0.5));
      d[i * 4] = 74 * s; d[i * 4 + 1] = 78 * s; d[i * 4 + 2] = 84 * s; d[i * 4 + 3] = 255;
    }
    cx.putImageData(img, 0, 0);
    const set = {
      map: tex(col, { srgb: true, renderer, repeat: false }),
      normalMap: tex(normalFromHeight(height, W, H, 4.5), { renderer, repeat: false }),
    };
    set.map.wrapS = set.map.wrapT = THREE.ClampToEdgeWrapping;
    set.normalMap.wrapS = set.normalMap.wrapT = THREE.ClampToEdgeWrapping;
    return set;
  });
}

// ---------------------------------------------------------------------------
// Walnut veneer (podium): vertical grain, pores, slight figure. Tile 0.6 x 1.2 m.

export function woodTextures(renderer) {
  return cached('wood', () => {
    const W = 512, H = 1024;
    const rnd = mulberry32(2024);
    const warp = fbmField(W, H, 41, 2, 3, 0.5);
    const lo = fbmField(W, H, 43, 3, 3, 0.5);
    const grainN = periodicNoise(47, 64);
    const col = makeCanvas(W, H), cx = col.getContext('2d');
    const img = cx.createImageData(W, H), d = img.data;
    const rough = new Float32Array(W * H), height = new Float32Array(W * H);
    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x;
      const u = x / W * 64 + warp[i] * 6;
      const g = grainN(u, y / H * 2);
      const ring = 0.5 + 0.5 * Math.sin(u * 2.3 + g * 3);
      const pore = rnd() < 0.05 ? 0.75 : 1;
      const s = (0.72 + 0.28 * ring + 0.2 * (lo[i] - 0.5)) * pore;
      d[i * 4] = 84 * s; d[i * 4 + 1] = 56 * s; d[i * 4 + 2] = 36 * s; d[i * 4 + 3] = 255;
      rough[i] = 0.42 + 0.12 * (1 - ring) + (pore < 1 ? 0.2 : 0);
      height[i] = ring * 0.3 + (pore < 1 ? -0.4 : 0);
    }
    cx.putImageData(img, 0, 0);
    return setTile({
      map: tex(col, { srgb: true, renderer }),
      roughnessMap: tex(greyCanvas(rough, W, H), { renderer }),
      normalMap: tex(normalFromHeight(height, W, H, 0.5), { renderer }),
    }, 0.6, 1.2);
  });
}

// ---------------------------------------------------------------------------
// Chrome: very subtle polishing marks (roughness), tile 0.3 m.

export function chromeTextures(renderer) {
  return cached('chrome', () => {
    const W = 256, H = 256;
    const lo = fbmField(W, H, 61, 4, 4, 0.55);
    const rnd = mulberry32(62);
    const r = new Float32Array(W * H);
    for (let i = 0; i < W * H; i++) r[i] = 0.07 + 0.08 * lo[i] + 0.03 * rnd();
    return setTile({ roughnessMap: tex(greyCanvas(r, W, H), { renderer }) }, 0.3, 0.3);
  });
}

// ---------------------------------------------------------------------------
// Ceiling plaster / paint: faint mottle. Tile 2 m.

export function plasterTextures(renderer) {
  return cached('plaster', () => {
    const W = 512, H = 512;
    const lo = fbmField(W, H, 71, 4, 5, 0.55);
    const rnd = mulberry32(72);
    const col = makeCanvas(W, H), cx = col.getContext('2d');
    const img = cx.createImageData(W, H), d = img.data;
    const h = new Float32Array(W * H);
    for (let i = 0; i < W * H; i++) {
      const f = rnd();
      const s = 0.92 + 0.12 * lo[i] + 0.04 * (f - 0.5);
      d[i * 4] = 128 * s; d[i * 4 + 1] = 126 * s; d[i * 4 + 2] = 122 * s; d[i * 4 + 3] = 255;
      h[i] = lo[i] * 0.5 + f * 0.5;
    }
    cx.putImageData(img, 0, 0);
    return setTile({ map: tex(col, { srgb: true, renderer }), normalMap: tex(normalFromHeight(h, W, H, 0.4), { renderer }) }, 2, 2);
  });
}

// ---------------------------------------------------------------------------
// Cinema screen content: pale blue pre-show slide, brighter towards the top
// centre (projector hot spot), subtle horizontal structure.

export function screenTexture(renderer) {
  return cached('screen', () => {
    const W = 512, H = 256;
    const c = makeCanvas(W, H), x = c.getContext('2d');
    const g = x.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#7092e0'); g.addColorStop(0.5, '#4a6cc4'); g.addColorStop(1, '#30509e');
    x.fillStyle = g; x.fillRect(0, 0, W, H);
    const rg = x.createRadialGradient(W * 0.52, H * 0.3, 10, W * 0.5, H * 0.45, W * 0.55);
    rg.addColorStop(0, 'rgba(200,220,255,0.7)'); rg.addColorStop(0.5, 'rgba(130,165,240,0.22)'); rg.addColorStop(1, 'rgba(0,0,30,0.0)');
    x.fillStyle = rg; x.fillRect(0, 0, W, H);
    // edge falloff
    const eg = x.createLinearGradient(0, 0, W, 0);
    eg.addColorStop(0, 'rgba(0,0,20,0.35)'); eg.addColorStop(0.12, 'rgba(0,0,20,0)'); eg.addColorStop(0.88, 'rgba(0,0,20,0)'); eg.addColorStop(1, 'rgba(0,0,20,0.35)');
    x.fillStyle = eg; x.fillRect(0, 0, W, H);
    // feathered border (projector edge softness + the masking's black velvet)
    const F = 7;
    for (const [x0, y0, x1, y1, w, h] of [[0, 0, F, 0, F, H], [W, 0, W - F, 0, F, H], [0, 0, 0, F, W, F], [0, H, 0, H - F, W, F]]) {
      const fg = x.createLinearGradient(x0, y0, x1, y1);
      fg.addColorStop(0, 'rgba(0,0,8,0.92)'); fg.addColorStop(1, 'rgba(0,0,8,0)');
      x.fillStyle = fg; x.fillRect(Math.min(x0, x1), Math.min(y0, y1), w, h);
    }
    const t = tex(c, { srgb: true, renderer, repeat: false });
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    return t;
  });
}

// Small tablet UI on the podium (booking app look: dark UI, a bright card).
export function tabletTexture(renderer) {
  return cached('tablet', () => {
    const W = 256, H = 192;
    const c = makeCanvas(W, H), x = c.getContext('2d');
    x.fillStyle = '#0d1420'; x.fillRect(0, 0, W, H);
    x.fillStyle = '#1d3b6a'; x.fillRect(0, 0, W, 26);
    x.fillStyle = '#e8eef8'; x.fillRect(18, 44, 140, 108);
    x.fillStyle = '#c33'; x.fillRect(172, 44, 66, 30);
    x.fillStyle = '#2a4f8a'; x.fillRect(172, 84, 66, 68);
    x.fillStyle = '#9ab'; for (let i = 0; i < 5; i++) x.fillRect(28, 56 + i * 18, 110 - i * 12, 7);
    const t = tex(c, { srgb: true, renderer, repeat: false });
    t.wrapS = t.wrapT = THREE.ClampToEdgeWrapping;
    return t;
  });
}

// Radial glow sprite (for step-light pools and lamp halos), linear alpha.
export function glowTexture() {
  return cached('glow', () => {
    const W = 128;
    const c = makeCanvas(W, W), x = c.getContext('2d');
    const g = x.createRadialGradient(W / 2, W / 2, 0, W / 2, W / 2, W / 2);
    g.addColorStop(0, 'rgba(255,255,255,1)');
    g.addColorStop(0.25, 'rgba(255,255,255,0.45)');
    g.addColorStop(0.6, 'rgba(255,255,255,0.10)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    x.fillStyle = g; x.fillRect(0, 0, W, W);
    const t = new THREE.CanvasTexture(c);
    t.colorSpace = THREE.NoColorSpace;
    t.needsUpdate = true;
    return t;
  });
}

