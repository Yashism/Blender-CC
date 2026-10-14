// Procedural people for the CCTV sim. createHuman(seed, opts) -> Human (see SPEC.md).
//
// One SkinnedMesh per person (merged geometry, one material with a painted 512px atlas),
// plus a tiny contact-shadow mesh. Body parts are lofts of sculpted cross-sections; the
// clothing is part of the surface (offsets + painted texture), hair is a shell around the
// head plus long-hair / braid / bun / ponytail volumes. Carried items are skinned to the
// hand. The walk is a procedural gait (human_gait.js) with planted feet.
import * as THREE from 'three';
import { GeoBuilder, loft, keyed, sellipse, ellipsoid, ribbon, clamp, lerp, smooth, gauss, v3 } from './human_geo.js';
import { sampleLook, paintAtlas, rectUV, swatchUV, itemUV, hairCoverage, canPaint, ATLAS } from './human_look.js';
import { Gait, BONES, BI, PARENT, CARRY } from './human_gait.js';

const PI = Math.PI, TAU = PI * 2;

// ------------------------------------------------------------------ measurements
function measure(look) {
  const H = look.H, f = look.sex === 'f';
  const k = look.child ? clamp((13.5 - look.age) / 9.5, 0, 1) : 0; // child-proportion amount
  const F = (a, c) => lerp(a, c, k);
  const sc = H / 1.7;
  const M = { H, k, sc, f };
  M.girth = 1 + look.mass * 0.12 + (look.child ? 0.04 : 0);
  M.headH = H * F(0.13, 0.182) * look.headScale;
  M.headB = M.headH * F(0.68, 0.74);
  M.headL = M.headH * F(0.86, 0.9);
  M.chinY = H - M.headH;
  M.headY = M.chinY + 0.3 * M.headH;
  M.headZ = -0.012 * sc;
  M.neckBaseY = H * F(0.838, 0.792);
  M.shoulderY = H * F(0.812, 0.768);
  M.chestY = H * F(0.72, 0.672);
  M.waistY = H * F(0.612, 0.585);
  M.hipY = H * F(0.515, 0.475) * look.legRatio;
  M.crotchY = M.hipY - H * F(0.045, 0.04);
  M.kneeY = H * F(0.284, 0.27) * look.legRatio;
  M.ankleY = H * F(0.044, 0.05) + 0.012;
  M.hipX = H * (f ? 0.054 : 0.051) * Math.sqrt(look.hip) * F(1, 1.04);
  M.footX = M.hipX * 0.68;
  M.shoulderX = H * (f ? 0.096 : 0.104) * look.shoulder * F(1, 0.93) * (1 + Math.max(0, look.mass) * 0.04);
  M.upperArm = H * F(0.186, 0.178);
  M.foreArm = H * F(0.146, 0.138);
  M.handLen = H * F(0.106, 0.1);
  M.armAbd0 = 0.12 + 0.05 * Math.max(0, look.mass);
  const shoe = look.outfit.shoes === 'sneaker' || look.outfit.shoes === 'formal';
  M.footLen = H * F(0.152, 0.158) + (shoe ? 0.018 : 0.008);
  M.heelBack = 0.2 * M.footLen;
  M.ballF = 0.53 * M.footLen;
  M.toeF = 0.8 * M.footLen;
  M.ballH = 0.024 * sc;
  M.soleH = look.outfit.shoes === 'sneaker' ? 0.024 : look.outfit.shoes === 'formal' ? 0.014 : 0.012;
  M.neckR = H * (f ? 0.0175 : 0.0205) * (1 + look.mass * 0.08) * F(1, 1.06);
  return M;
}

function restPositions(M, look) {
  const R = BONES.map(() => new THREE.Vector3());
  const set = (n, x, y, z) => R[BI[n]].set(x, y, z);
  const sc = M.sc;
  set('pelvis', 0, M.hipY, 0);
  set('spine', 0, M.waistY, -0.01 * sc);
  set('chest', 0, M.chestY, -0.012 * sc);
  set('neck', 0, M.neckBaseY, -0.03 * sc);
  set('head', 0, M.headY, M.headZ);
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R';
    set('clav' + L, s * 0.03 * sc, M.shoulderY + 0.012 * sc, -0.02 * sc);
    const sh = new THREE.Vector3(s * M.shoulderX, M.shoulderY, -0.015 * sc);
    set('upperArm' + L, sh.x, sh.y, sh.z);
    const dir = new THREE.Vector3(s * Math.sin(M.armAbd0), -Math.cos(M.armAbd0), 0);
    const el = sh.clone().addScaledVector(dir, M.upperArm);
    set('forearm' + L, el.x, el.y, el.z);
    const wr = el.clone().addScaledVector(dir, M.foreArm);
    set('hand' + L, wr.x, wr.y, wr.z);
    set('thigh' + L, s * M.hipX, M.hipY, 0);
    set('shin' + L, s * M.hipX, M.kneeY, 0);
    set('foot' + L, s * M.hipX, M.ankleY, 0);
    set('toe' + L, s * M.hipX, M.ballH, M.ballF);
  }
  set('tail', 0, M.headY + 0.05 * sc, M.headZ - 0.07 * sc);
  set('drape', 0.07 * sc, M.shoulderY + 0.03 * sc, -0.03 * sc);
  const bs = look.carrySide === 'L' ? 1 : -1;
  set('bag', bs * M.shoulderX * 0.75, M.shoulderY + 0.04 * sc, -0.015 * sc);
  return R;
}

// ------------------------------------------------------------------ torso shape
const TORSO = keyed([
  // adult fraction of H, half width, front depth, back depth, centre z  (all / H, male baseline)
  [0.455, 0.040, 0.026, 0.028, 0.0],
  [0.462, 0.062, 0.036, 0.040, 0.0],
  [0.47, 0.077, 0.044, 0.048, 0.0],
  [0.49, 0.093, 0.050, 0.056, 0.0],
  [0.515, 0.0985, 0.052, 0.061, -0.002],
  [0.55, 0.095, 0.052, 0.058, -0.002],
  [0.585, 0.0895, 0.052, 0.051, 0.0],
  [0.615, 0.087, 0.052, 0.048, 0.0],
  [0.65, 0.0895, 0.054, 0.050, 0.0],
  [0.69, 0.093, 0.058, 0.053, 0.0],
  [0.72, 0.097, 0.061, 0.056, 0.0],
  [0.75, 0.101, 0.058, 0.056, -0.003],
  [0.78, 0.105, 0.051, 0.053, -0.006],
  [0.80, 0.104, 0.043, 0.047, -0.009],
  [0.812, 0.094, 0.036, 0.041, -0.012],
  [0.824, 0.073, 0.031, 0.036, -0.014],
  [0.834, 0.051, 0.027, 0.031, -0.015],
  [0.843, 0.038, 0.025, 0.028, -0.015],
  [0.85, 0.03, 0.022, 0.025, -0.015],
]);
const LAND_A = [0.47, 0.515, 0.612, 0.72, 0.812, 0.838];

function makeTorso(M, look) {
  const H = M.H, f = M.f, o = look.outfit, sc = M.sc;
  const land = [M.crotchY, M.hipY, M.waistY, M.chestY, M.shoulderY, M.neckBaseY];
  const mapY = (fa) => {
    let i = 0;
    while (i < LAND_A.length - 2 && fa > LAND_A[i + 1]) i++;
    return land[i] + (fa - LAND_A[i]) * (land[i + 1] - land[i]) / (LAND_A[i + 1] - LAND_A[i]);
  };
  const invY = (y) => {
    let i = 0;
    while (i < land.length - 2 && y > land[i + 1]) i++;
    return LAND_A[i] + (y - land[i]) * (LAND_A[i + 1] - LAND_A[i]) / (land[i + 1] - land[i]);
  };
  const k = M.k;
  const sexW = keyed(f ? [[0.45, 1.06 * look.hip], [0.55, 1.07 * look.hip], [0.615, 0.86], [0.7, 0.92], [0.78, 0.9], [0.85, 0.86]]
    : [[0.45, 0.98 * look.hip], [0.55, 0.98 * look.hip], [0.615, 1.0], [0.72, 1.0], [0.79, look.shoulder], [0.85, 1.0]]);
  const kidW = keyed([[0.45, 0.96], [0.55, 0.97], [0.615, 1.08], [0.72, 1.0], [0.79, 0.9], [0.85, 0.95]]);
  const girth = M.girth;
  const belly = look.belly;
  // clothing offsets (top garment above hem, bottom garment below the belt)
  const topOff = { tee: 0.005, polo: 0.006, shirt: 0.008, hoodie: 0.016, jacket: 0.018, kurta: 0.01, kameez: 0.008, kurti: 0.008, top: 0.005, frock: 0.006, saree: 0.003 }[o.top] || 0.004;
  const botOff = { jeans: 0.006, chinos: 0.007, shorts: 0.008, salwar: 0.016, pyjama: 0.012, churidar: 0.004, leggings: 0.003, saree: 0.012, bare: 0.0 }[o.bottom] || 0.005;
  const isLong = o.top === 'kurta' || o.top === 'kameez' || o.top === 'kurti' || o.top === 'frock';
  const beltY = mapY(f ? 0.585 : 0.575);
  const hemY = o.top === 'saree' ? mapY(0.69) : isLong ? -1 : o.tucked ? beltY + 0.002 : Math.min(o.hemH * H, mapY(0.56));
  const sareeWaistY = mapY(0.6);
  const loose = o.top === 'hoodie' || o.top === 'kurta' || o.top === 'kameez' || o.top === 'kurti' || o.top === 'tee' || o.top === 'shirt' || o.top === 'jacket' || o.top === 'frock' || o.top === 'top';
  function dims(y) {
    const fa = invY(y);
    const T = TORSO(fa);
    const wk = lerp(1, kidW(fa)[0], k);
    let w = T[0] * H * sexW(fa)[0] * wk * (1 + (girth - 1) * 1.1);
    let df = T[1] * H * (1 + (girth - 1) * 0.9);
    let db = T[2] * H * (1 + (girth - 1) * 0.8);
    const cz = T[3] * H;
    // extra waist girth for heavier people
    const wz = gauss(fa - 0.6, 0.05);
    w *= 1 + Math.max(0, look.mass) * 0.08 * wz;
    if (f) db *= 1 + 0.06 * gauss(fa - 0.51, 0.04);
    return { fa, w, df, db, cz };
  }
  function cloth(y) {
    let off = 0;
    if (o.top === 'saree') {
      if (y > hemY) off = topOff; else if (y < sareeWaistY) off = botOff; else off = 0;
    } else if (isLong) off = topOff;
    else if (y > hemY) off = topOff;
    else off = botOff + (y > beltY - 0.04 * sc && y < beltY + 0.005 ? 0.003 : 0);
    return off;
  }
  const bustA = look.bust * 0.024 * sc * (1 + 0.2 * look.mass);
  const bustY = mapY(0.712);
  const bellyA = belly * 0.032 * sc;
  const bellyY = mapY(0.6);
  const gluteA = (f ? 0.02 : 0.013) * sc * (1 + 0.3 * look.mass);
  const gluteY = mapY(0.505);
  const pecA = f ? 0 : 0.006 * sc;
  const shapeAt = (y) => {
    const d = dims(y);
    const off = cloth(y);
    const tight = !loose || y < hemY;
    return (th) => {
      const c = Math.cos(th), s = Math.sin(th);
      const e = 2.35;
      let a = d.w * Math.sign(c) * Math.pow(Math.abs(c), 2 / e);
      let b = (s > 0 ? d.df : d.db) * Math.sign(s) * Math.pow(Math.abs(s), 2 / e);
      // bumps (radial push)
      const dF = Math.atan2(Math.sin(th - PI / 2), Math.cos(th - PI / 2)); // angle from front
      const dB = Math.atan2(Math.sin(th - 1.5 * PI), Math.cos(th - 1.5 * PI));
      let push = off;
      if (bustA > 0) {
        const gy = gauss(y - bustY, 0.045 * sc) * (y < bustY ? 1 : 0.85);
        const gl = gauss(dF - 0.43, 0.3), gr = gauss(dF + 0.43, 0.3);
        const bridge = (tight && o.top === 'saree') ? 0 : 0.78 * gauss(dF, 0.55);
        push += bustA * gy * Math.max(gl, gr, bridge);
      }
      if (bellyA > 0) push += bellyA * gauss(y - bellyY, 0.07 * sc) * gauss(dF, 0.75);
      {
        const gy = gauss(y - gluteY, 0.045 * sc);
        push += gluteA * gy * Math.max(gauss(dB - 0.42, 0.36), gauss(dB + 0.42, 0.36), 0.85 * gauss(dB, 0.5));
      }
      if (pecA > 0) push += pecA * gauss(y - mapY(0.735), 0.03 * sc) * Math.max(gauss(dF - 0.5, 0.4), gauss(dF + 0.5, 0.4));
      push += 0.006 * sc * gauss(y - mapY(0.765), 0.03 * sc) * Math.max(gauss(dB - 0.55, 0.35), gauss(dB + 0.55, 0.35));
      const L = Math.hypot(a, b) || 1;
      a += (a / L) * push; b += (b / L) * push;
      return [a, b + d.cz];
    };
  };
  const top = mapY(0.85), bot = mapY(0.455);
  return { mapY, invY, dims, cloth, shapeAt, top, bot, beltY, hemY, sareeWaistY, isLong, loose,
    point(y, th, extra = 0) {
      const ab = shapeAt(y)(th);
      const L = Math.hypot(ab[0], ab[1] - dims(y).cz) || 1;
      return [ab[0] + ab[0] / L * extra, y, ab[1] + (ab[1] - dims(y).cz) / L * extra];
    } };
}

// ------------------------------------------------------------------ weights helpers
function W(...pairs) { const out = []; for (let i = 0; i < pairs.length; i += 2) if (pairs[i + 1] > 1e-4) out.push([BI[pairs[i]], pairs[i + 1]]); return out.length ? out : [[BI[pairs[0]], 1]]; }

// ------------------------------------------------------------------ body build
function buildBody(B, look, M, R, T, items) {
  const o = look.outfit, sc = M.sc, H = M.H;
  const skinUV = swatchUV('skin');
  // ================================================= TORSO
  {
    const ys = [];
    const fr = [0.455, 0.459, 0.464, 0.47, 0.478, 0.488, 0.5, 0.515, 0.53, 0.55, 0.57, 0.59, 0.61, 0.63, 0.65, 0.67, 0.69, 0.71, 0.73, 0.75, 0.765, 0.78, 0.79, 0.8, 0.807, 0.814, 0.82, 0.826, 0.832, 0.838, 0.843, 0.847, 0.85];
    for (const a of fr) ys.push(T.mapY(a));
    const addEdge = (y) => { if (y > T.bot + 0.01 && y < T.top - 0.01) { ys.push(y + 0.004); ys.push(y - 0.0025); } };
    if (!T.isLong) addEdge(T.hemY);
    if (o.top === 'saree') addEdge(T.sareeWaistY);
    if (o.bottom !== 'saree' && o.bottom !== 'bare') addEdge(T.beltY - 0.04 * sc);
    ys.sort((a, b) => a - b);
    const rings = ys.map((y) => ({ c: [0, y, 0], ax: [1, 0, 0], az: [0, 0, 1], f: T.shapeAt(y), v: (T.top - y) / (T.top - T.bot), s: y }));
    const shX = M.shoulderX;
    loft(B, rings, {
      n: 44, arc: true, rect: rectUV('torso'), capStart: 0.012 * sc, capEnd: 0.006 * sc,
      weights: (p, y) => {
        const ax = Math.abs(p[0]);
        const wP = 1 - smooth(M.hipY + 0.01, M.waistY, y);
        const wC = smooth(M.waistY + 0.03, M.chestY, y);
        const wS = Math.max(0, 1 - wP - wC);
        const side = p[0] > 0 ? 'L' : 'R';
        // shoulders follow the arm a little
        const wArm = 0.45 * smooth(shX - 0.07 * sc, shX + 0.01, ax) * smooth(M.shoulderY - 0.1 * sc, M.shoulderY - 0.02 * sc, y);
        const wNeck = 0.5 * smooth(M.neckBaseY - 0.03 * sc, M.neckBaseY + 0.01, y) * (1 - smooth(0.05 * sc, 0.09 * sc, ax));
        // hips / crotch follow the thighs a little
        const wTh = 0.45 * (1 - smooth(M.crotchY, M.hipY + 0.02, y)) * smooth(0.0, M.hipX, ax) + 0.25 * (1 - smooth(M.hipY - 0.04, M.hipY + 0.03, y)) * smooth(M.hipX * 0.8, M.hipX * 1.8, ax);
        const base = 1 - wArm - wNeck - wTh;
        return W('pelvis', wP * base, 'spine', wS * base, 'chest', wC * base, 'upperArm' + side, wArm * 0.7, 'clav' + side, wArm * 0.3, 'neck', wNeck, 'thigh' + side, wTh);
      },
      color: (p, y) => {
        const ax = Math.abs(p[0]);
        let ao = 1;
        ao -= 0.35 * gauss(ax - (shX - 0.03 * sc), 0.035 * sc) * gauss(y - (M.shoulderY - 0.1 * sc), 0.045 * sc);
        ao -= 0.35 * (1 - smooth(M.crotchY - 0.01, M.crotchY + 0.05 * sc, y));
        if (!T.isLong && o.top !== 'saree' && y < T.hemY && y > T.hemY - 0.03) ao -= 0.25 * (1 - (T.hemY - y) / 0.03);
        return [ao, ao, ao];
      },
    });
  }
  // ================================================= NECK
  {
    const y0 = M.neckBaseY - 0.05 * sc, y1 = M.headY + 0.035 * sc;
    const rings = [];
    for (let i = 0; i <= 7; i++) {
      const y = lerp(y0, y1, i / 7);
      const r = M.neckR * (1 + 0.35 * (1 - smooth(M.neckBaseY - 0.05 * sc, M.neckBaseY + 0.015 * sc, y)));
      const z = lerp(-0.03 * sc, M.headZ - 0.012 * sc, i / 7);
      rings.push({ c: [0, y, z], ax: [1, 0, 0], az: [0, 0, 1], f: (th) => [r * 1.04 * Math.cos(th), r * 0.98 * Math.sin(th)], v: 0, s: y });
    }
    loft(B, rings, {
      n: 16, rect: rectUV('torso'), uvAt: () => skinUV,
      weights: (p, y) => {
        const wc = 1 - smooth(M.neckBaseY - 0.04 * sc, M.neckBaseY + 0.01, y);
        const wh = smooth(M.headY - 0.03 * sc, M.headY + 0.02 * sc, y);
        return W('chest', wc, 'neck', Math.max(0, 1 - wc - wh), 'head', wh);
      },
      color: (p, y) => { const fr = p[2] - M.headZ > 0 ? 1 : 0; const a = 1 - 0.3 * fr * smooth(M.headY - 0.06 * sc, M.headY + 0.01, y); return [a, a, a]; },
    });
  }
  // shirt / polo / kurta collar band
  if (o.top === 'shirt' || o.top === 'polo' || (o.top === 'kurta' && look.sex === 'm') || o.top === 'jacket') {
    const y0 = M.neckBaseY - 0.012 * sc, h = (o.top === 'kurta' ? 0.025 : 0.035) * sc;
    const rings = [];
    for (let i = 0; i <= 3; i++) {
      const t = i / 3;
      const y = y0 + h * t;
      const r = M.neckR * (o.top === 'jacket' ? 1.55 : 1.32) + 0.004 + t * 0.003;
      rings.push({ c: [0, y, -0.026 * sc + t * 0.006 * sc], ax: [1, 0, 0], az: [0, 0, 1], f: (th) => { const fr = Math.max(0, Math.sin(th)); return [r * 1.08 * Math.cos(th), r * Math.sin(th) + fr * fr * fr * 0.012 * sc * (1 - t)]; }, s: t });
    }
    const cuv = swatchUV(o.top === 'jacket' ? 'top' : 'collar');
    loft(B, rings, { n: 20, uvAt: () => cuv, weights: (p, t) => W('chest', 1 - t * 0.6, 'neck', t * 0.6), color: (p, t) => [0.75 + 0.25 * t, 0.75 + 0.25 * t, 0.75 + 0.25 * t] });
  }
  // hoodie hood bunched behind the neck
  if (o.top === 'hoodie') {
    const pts = [];
    for (let i = 0; i <= 8; i++) {
      const a = lerp(-1.05, 1.05, i / 8); // around the back
      const r = M.neckR + 0.035 * sc;
      pts.push([Math.sin(a) * r * 1.6, M.neckBaseY + 0.005 * sc - 0.02 * sc * Math.abs(Math.sin(a)), -0.03 * sc - Math.cos(a) * r * 1.1]);
    }
    const huv = swatchUV('top');
    ribbon(B, pts, 12, (t) => (0.07 - 0.02 * Math.abs(t - 0.5)) * sc, (t) => (0.045 + 0.02 * (1 - Math.abs(t - 0.5) * 2)) * sc, (p) => [0, 1, 0], {
      n: 12, e: 2.2, uvAt: () => huv, capStart: 0.01, capEnd: 0.01,
      weights: () => W('chest', 0.8, 'neck', 0.2), color: (p, s, th) => { const a = 0.8 + 0.2 * Math.sin(th); return [a, a, a]; },
    });
  }
  // ================================================= HEAD
  const face = buildHead(B, look, M);
  // ================================================= ARMS + HANDS
  for (const s of [1, -1]) buildArm(B, look, M, R, s, items);
  // ================================================= LEGS + FEET
  for (const s of [1, -1]) { buildLeg(B, look, M, R, T, s); buildFoot(B, look, M, R, s); }
  // ================================================= SKIRT
  if (o.skirtLen) buildSkirt(B, look, M, R, T);
  // ================================================= DRAPES
  if (o.dupatta || o.top === 'saree') buildDrape(B, look, M, R, T);
  // ================================================= BAGS
  if (look.carry === 'bag') buildBag(B, look, M, R, T);
  return face;
}

// ------------------------------------------------------------------ head, face, hair
const HEADP = keyed([
  // s, half-width (frac of B/2), front (frac of L), back (frac of L)
  [0.0, 0.12, 0.27, 0.16],
  [0.035, 0.27, 0.355, 0.04],
  [0.09, 0.44, 0.405, -0.05],
  [0.16, 0.585, 0.43, -0.13],
  [0.24, 0.72, 0.44, -0.23],
  [0.32, 0.82, 0.435, -0.34],
  [0.42, 0.905, 0.425, -0.45],
  [0.5, 0.96, 0.45, -0.51],
  [0.6, 0.995, 0.44, -0.54],
  [0.7, 0.99, 0.385, -0.55],
  [0.8, 0.935, 0.29, -0.51],
  [0.88, 0.8, 0.17, -0.43],
  [0.94, 0.6, 0.06, -0.31],
  [0.975, 0.37, -0.04, -0.2],
  [0.993, 0.15, -0.08, -0.13],
]);
function headFace(M, look) {
  const k = M.k;
  return {
    eyeS: lerp(0.425, 0.39, k), browS: lerp(0.5, 0.46, k), noseS: lerp(0.255, 0.24, k), mouthS: lerp(0.155, 0.15, k),
    hairS: lerp(0.7, 0.66, k), eyeDu: 0.074, child: k,
  };
}
function headShape(M, look, F, s, extraFn) {
  const P = HEADP(s);
  const k = M.k;
  // children: rounder cranium, smaller face
  const faceK = 1 - 0.12 * k * (1 - smooth(0.3, 0.6, s));
  const w = P[0] * M.headB / 2 * (1 + 0.04 * k * smooth(0.4, 0.8, s)) * faceK;
  const fr = P[1] * M.headL * (1 - 0.06 * k * (1 - smooth(0.3, 0.6, s)));
  const bk = P[2] * M.headL;
  const eF = s > 0.08 && s < 0.65 ? 2.7 : 2.2;
  const g = M.sc;
  return (th) => {
    const c = -Math.cos(th), sn = -Math.sin(th);
    const e = c > 0 ? eF : 2.1;
    let x = w * Math.sign(sn) * Math.pow(Math.abs(sn), 2 / e);
    // front uses fr (positive), back uses bk (negative) -> z negative behind the head axis
    const z0 = c > 0 ? fr * Math.pow(c, 2 / e) : bk * Math.pow(-c, 2 / e);
    let z = z0;
    // face sculpt (radial push in metres)
    const da = Math.atan2(Math.sin(th - PI), Math.cos(th - PI)); // 0 = front centre
    let push = 0;
    push -= 0.0055 * g * gauss(Math.abs(da) - 0.42, 0.17) * gauss(s - F.eyeS, 0.035);    // eye sockets
    push += 0.004 * g * gauss(da, 0.55) * gauss(s - F.browS, 0.03);                     // brow ridge
    push += 0.0035 * g * gauss(Math.abs(da) - 0.75, 0.22) * gauss(s - (F.noseS + 0.07), 0.05); // cheekbones
    push += 0.0035 * g * gauss(da, 0.22) * gauss(s - F.mouthS, 0.025);                  // lips
    push += 0.003 * g * gauss(da, 0.3) * gauss(s - 0.045, 0.03);                         // chin
    if (extraFn) push += extraFn(th, s, da);
    const L = Math.hypot(x, z) || 1;
    x += x / L * push; z += z / L * push;
    return [x, z];
  };
}
function headRings(M, look, F, s0, s1, nr, extraFn) {
  const rings = [];
  for (let i = 0; i <= nr; i++) {
    const t = i / nr;
    const s = lerp(s0, s1, Math.sin(t * PI / 2) * 0.35 + t * 0.65);
    rings.push({ c: [0, M.chinY + s * M.headH, M.headZ], ax: [1, 0, 0], az: [0, 0, 1], f: headShape(M, look, F, s, extraFn), v: 1 - s, s });
  }
  return rings;
}
function buildHead(B, look, M) {
  const F = headFace(M, look);
  const sc = M.sc;
  const beard = look.beard === 'full' ? (th, s, da) => 0.006 * sc * smooth(0.42, 0.3, s) * (1 - smooth(1.2, 1.7, Math.abs(da))) : null;
  const rings = headRings(M, look, F, 0.0, 0.993, 30, beard);
  loft(B, rings, {
    n: 36, rect: rectUV('head'), capStart: 0.004 * sc, capEnd: 0.002 * sc,
    weights: () => W('head', 1),
    color: (p, s, th) => { const a = 1 - 0.25 * (1 - smooth(0.0, 0.12, s)); return [a, a, a]; },
  });
  const headPt = (s, da, out = 0) => {
    const f = headShape(M, look, F, s);
    const th = PI + da;
    const ab = f(th);
    const L = Math.hypot(ab[0], ab[1]) || 1;
    return [ab[0] + ab[0] / L * out, M.chinY + s * M.headH, M.headZ + ab[1] + ab[1] / L * out];
  };
  // nose
  {
    const np = headPt(F.noseS + 0.075, 0, -0.004 * sc);
    const ny = norm3([0, 1, -0.42]);
    const nz = norm3([0, 0.42, 1]);
    const nuv = [(rectUV('head')[0] + rectUV('head')[2]) / 2, rectUV('head')[1] + (1 - F.noseS - 0.06) * (rectUV('head')[3] - rectUV('head')[1])];
    ellipsoid(B, np, [0.0105 * sc * (1 - 0.2 * M.k), 0.026 * sc * (1 - 0.25 * M.k), 0.0125 * sc * (1 - 0.25 * M.k)], { x: [1, 0, 0], y: ny, z: nz }, {
      n: 10, nLat: 6, uvAt: () => nuv, weights: () => W('head', 1), color: (p) => { const a = p[1] < np[1] - 0.012 * sc ? 0.75 : 1; return [a, a, a]; },
    });
    const wp = headPt(F.noseS + 0.01, 0, -0.002 * sc);
    ellipsoid(B, wp, [0.0165 * sc * (1 - 0.15 * M.k), 0.0085 * sc, 0.0105 * sc], { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] }, {
      n: 10, nLat: 5, uvAt: () => nuv, weights: () => W('head', 1), color: (p) => { const a = p[1] < wp[1] ? 0.7 : 0.95; return [a, a, a]; },
    });
  }
  // ears (unless covered by long / bob hair)
  const hidden = look.hair === 'long' || look.hair === 'bob';
  if (!hidden) {
    for (const s of [1, -1]) {
      const ep = headPt(F.eyeS - 0.07, s * PI / 2 + s * 0.08, -0.004 * sc);
      ep[2] -= 0.004 * sc;
      const a = 0.25;
      ellipsoid(B, ep, [0.011 * sc, 0.029 * sc * (1 - 0.15 * M.k), 0.017 * sc], { x: [Math.cos(a) * s, 0, Math.sin(a)], y: [0, 1, 0], z: [-Math.sin(a) * s, 0, Math.cos(a)] }, {
        n: 10, nLat: 6, uvAt: () => swatchUV('skin'), weights: () => W('head', 1), color: (p) => { const d = (p[0] - ep[0]) * s; const k = d < 0 ? 0.65 : 0.95; return [k, k, k]; },
      });
      if (look.sex === 'f') ellipsoid(B, [ep[0] + s * 0.004 * sc, ep[1] - 0.026 * sc, ep[2] + 0.004 * sc], [0.004 * sc, 0.004 * sc, 0.004 * sc], { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] }, { n: 6, nLat: 4, uvAt: () => swatchUV('earring'), weights: () => W('head', 1) });
    }
  }
  buildHair(B, look, M, F);
  if (look.glasses) {
    // thin frame ring across the eyes (rendered as a slim band in front of the face)
    const gp = headPt(F.eyeS, 0, 0.012 * sc);
    const w = M.headB * 0.47;
    const rings = [];
    for (let i = 0; i <= 2; i++) {
      const y = gp[1] - 0.012 * sc + i * 0.012 * sc;
      rings.push({ c: [0, y, M.headZ - 0.01 * sc], ax: [1, 0, 0], az: [0, 0, 1], f: (th) => { const p = headShape(M, look, F, (y - M.chinY) / M.headH)(th); const L = Math.hypot(p[0], p[1]) || 1; return [p[0] + p[0] / L * 0.006 * sc, p[1] + 0.01 * sc + p[1] / L * 0.006 * sc]; }, s: i });
    }
    // only the front arc is useful; build a thin full ring hugging the face (temples hidden by hair)
    loft(B, rings.slice(0, 1).concat(rings.slice(2)), { n: 28, uvAt: () => swatchUV('glass'), weights: () => W('head', 1) });
  }
  return F;
}
function norm3(a) { const l = Math.hypot(a[0], a[1], a[2]) || 1; return [a[0] / l, a[1] / l, a[2] / l]; }

function buildHair(B, look, M, F) {
  const sc = M.sc;
  const style = look.hair;
  const vol = look.hairVol;
  const huv = rectUV('hair');
  const tight = style === 'bun' || style === 'braid' || style === 'pony' || style === 'twoBraids';
  // thickness on the head (metres) as a function of (u, s)
  const thick = (u, s) => {
    const a = (u - 0.5) * TAU; // 0 front
    const top = smooth(0.55, 0.95, s);
    const front = Math.max(0, Math.cos(a));
    let t;
    switch (style) {
      case 'crop': t = 0.004 + 0.003 * top; break;
      case 'short': t = 0.005 + 0.011 * top * vol + 0.004 * front * top; break;
      case 'receding': t = 0.003 + 0.007 * top; break;
      case 'medium': t = 0.008 + 0.016 * top * vol + 0.006 * front * top; break;
      case 'quiff': t = 0.006 + 0.012 * top + 0.022 * front * smooth(0.65, 0.85, s) * vol; break;
      case 'bob': t = 0.01 + 0.008 * top + 0.012 * (1 - smooth(0.2, 0.5, s)); break;
      case 'long': t = 0.008 + 0.006 * top + 0.008 * (1 - smooth(0.25, 0.6, s)); break;
      default: t = 0.0045 + 0.004 * top; // pulled back
    }
    return t * sc * (M.k > 0 ? 0.85 : 1);
  };
  const s0 = style === 'long' || style === 'bob' ? 0.12 : 0.2;
  const rings = headRings(M, look, F, s0, 0.993, 30);
  // coverage: long hair & bob extend down the sides/back
  const cov = (u, s) => {
    let c = hairCoverage(look, F, u, s);
    if (style === 'long' || style === 'bob') {
      const a = Math.abs((u - 0.5) * TAU);
      if (a > 1.0) c = Math.max(c, smooth(0.12, 0.2, s));
    }
    return c;
  };
  const n = 40;
  loft(B, rings, {
    n, rect: huv, capEnd: (thick(0.5, 1) + 0.002 * sc),
    post: (P, N) => {
      for (let k = 0; k < P.length; k++) {
        const s = rings[k].s;
        for (let i = 0; i <= n; i++) {
          const u = i / n;
          const c = cov(u, s);
          const off = c * thick(u, s) - (1 - c) * 0.004 * sc + (c > 0 ? 0.0006 : 0);
          const p = P[k][i], q = N[k][i];
          P[k][i] = [p[0] + q[0] * off, p[1] + q[1] * off, p[2] + q[2] * off];
        }
      }
    },
    weights: () => W('head', 1),
    color: (p, s, th, u) => { const c = cov(u, s); const a = 0.55 + 0.45 * c * (0.7 + 0.3 * smooth(0.3, 0.9, s)); return [a, a, a]; },
  });
  const hairDir = [0, -1, 0];
  const backPt = (s, du = 0, out = 0) => {
    const f = headShape(M, look, F, s);
    const th = du; // th = 0 is the back
    const ab = f(th);
    const L = Math.hypot(ab[0], ab[1]) || 1;
    return [ab[0] + ab[0] / L * out, M.chinY + s * M.headH, M.headZ + ab[1] + ab[1] / L * out];
  };
  const tailW = (p) => {
    // top part with the head, hanging part with the tail bone and chest
    const y = p[1];
    const wh = smooth(M.headY - 0.02 * sc, M.headY + 0.04 * sc, y);
    const wc = (1 - wh) * smooth(M.headY - 0.05 * sc, M.chestY, y) * 0;
    return W('head', wh * 0.6, 'tail', 1 - wh * 0.6 - wc, 'chest', wc);
  };
  if (style === 'long') {
    // hair curtain down the back
    const len = look.hairLen * M.H / 1.6;
    const yTop = M.chinY + 0.62 * M.headH;
    const rings2 = [];
    const nr = 14;
    for (let i = 0; i <= nr; i++) {
      const t = i / nr;
      const y = yTop - t * (len + (yTop - M.neckBaseY));
      // follow the back of the head, then the upper back
      let zb;
      if (y > M.chinY + 0.2 * M.headH) { const s = (y - M.chinY) / M.headH; zb = backPt(s)[2] - 0.004 * sc; }
      else zb = Math.min(backPt(0.2)[2] - 0.004 * sc, -0.07 * sc - (M.neckBaseY - y > 0 ? 0.06 * sc * smooth(0, 0.15 * sc, M.neckBaseY - y) : 0));
      const w = (0.5 * M.headB * lerp(0.92, 1.0, smooth(0, 0.3, t)) + 0.04 * sc * smooth(0.3, 1, t)) * (1 - 0.25 * smooth(0.8, 1, t));
      const thk = (0.03 - 0.012 * t) * sc * vol;
      rings2.push({ c: [0, y, zb - thk * 0.3], ax: [1, 0, 0], az: [0, 0, 1], f: (th) => { const c = Math.cos(th), s = Math.sin(th); return [w * c, thk * s - 0.035 * sc * c * c * (1 - smooth(0.0, 0.25, t) * 0.4)]; }, v: t * 0.9, s: t });
    }
    loft(B, rings2, {
      n: 20, rect: huv, capEnd: 0.005 * sc,
      weights: (p) => { const y = p[1]; const wh = smooth(M.neckBaseY, M.chinY + 0.3 * M.headH, y); return W('head', wh, 'tail', (1 - wh) * 0.35, 'chest', (1 - wh) * 0.65); },
      color: (p, t, th) => { const a = 0.7 + 0.3 * Math.max(0, -Math.sin(th)); return [a, a, a]; },
    });
  }
  if (style === 'bun') {
    const bp = backPt(0.55, 0, 0.02 * sc);
    ellipsoid(B, bp, [0.042 * sc, 0.036 * sc, 0.028 * sc], { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] }, {
      n: 14, nLat: 8, rect: huv, weights: () => W('head', 1), bump: (th, lat) => 0.06 * Math.sin(th * 5 + lat * 3),
      color: (p) => { const a = 0.75 + 0.25 * clamp((p[1] - bp[1]) / (0.03 * sc) + 0.5, 0, 1); return [a, a, a]; },
    });
  }
  if (style === 'pony' || style === 'braid' || style === 'twoBraids') {
    const sides = style === 'twoBraids' ? [-1, 1] : [0];
    for (const side of sides) {
      const start = backPt(style === 'pony' ? 0.6 : 0.38, side * 0.9, 0.006 * sc);
      // tie
      ellipsoid(B, start, [0.014 * sc, 0.012 * sc, 0.012 * sc], { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] }, { n: 8, nLat: 5, uvAt: () => swatchUV('hairTie'), weights: () => W('head', 1) });
      const len = style === 'pony' ? (0.22 + 0.06 * vol) * sc : (look.hairLen || 0.4) * M.H / 1.6 * (style === 'twoBraids' ? 0.6 : 1);
      // path down the back of the head/neck then along the back
      const pts = [];
      const N = 8;
      for (let i = 0; i <= N; i++) {
        const t = i / N;
        const y = start[1] - t * len;
        let z;
        const s = (y - M.chinY) / M.headH;
        if (s > 0.25) z = backPt(s, side * 0.9, 0.012 * sc)[2]; else z = Math.min(backPt(0.25, side * 0.9)[2], -0.09 * sc + (y - M.neckBaseY) * 0.15) - 0.015 * sc;
        if (y < M.neckBaseY) z = Math.min(z, -0.085 * sc - 0.02 * sc * smooth(M.neckBaseY, M.chestY, y));
        const x = start[0] + side * 0.02 * sc * t;
        pts.push([x, y, z - (style === 'pony' ? 0.012 * sc * Math.sin(t * PI) : 0)]);
      }
      if (style === 'pony') {
        ribbon(B, pts, 12, (t) => (0.04 - 0.025 * t) * sc * vol, (t) => (0.03 - 0.02 * t) * sc * vol, () => [1, 0, 0], {
          n: 10, e: 2.2, rect: huv, capEnd: 0.008 * sc, capStart: 0.004 * sc,
          weights: (p) => tailW(p), color: (p, s, th) => { const a = 0.75 + 0.25 * Math.max(0, -Math.sin(th)); return [a, a, a]; },
        });
      } else {
        // braid: chain of small lobes
        const segs = Math.max(6, Math.round(len / (0.032 * sc)));
        const samples = pts;
        for (let i = 0; i < segs; i++) {
          const t = (i + 0.5) / segs;
          const f = t * (samples.length - 1);
          const j = Math.min(samples.length - 2, Math.floor(f));
          const q = f - j;
          const c = [lerp(samples[j][0], samples[j + 1][0], q), lerp(samples[j][1], samples[j + 1][1], q), lerp(samples[j][2], samples[j + 1][2], q)];
          const r = (0.019 - 0.007 * t) * sc * (style === 'twoBraids' ? 0.8 : 1);
          const tw = (i % 2 ? 1 : -1) * 0.35;
          ellipsoid(B, c, [r * 1.05, r * 1.25, r * 0.85], { x: [Math.cos(tw), 0, Math.sin(tw)], y: [0, 1, 0], z: [-Math.sin(tw), 0, Math.cos(tw)] }, {
            n: 8, nLat: 5, rect: huv, weights: (p) => tailW(p), color: (p) => { const a = 0.7 + 0.3 * clamp((p[1] - c[1]) / r + 0.5, 0, 1); return [a, a, a]; },
          });
        }
        const endP = pts[pts.length - 1];
        ellipsoid(B, [endP[0], endP[1] - 0.008 * sc, endP[2]], [0.012 * sc, 0.025 * sc, 0.01 * sc], { x: [1, 0, 0], y: [0, 1, 0], z: [0, 0, 1] }, { n: 8, nLat: 5, rect: huv, weights: (p) => tailW(p) });
      }
    }
  }
}

// ------------------------------------------------------------------ arms & hands
const ARMP = keyed([
  // d / upperArm (0 shoulder joint, 1 elbow, 2 wrist), medial-lateral radius, front-back radius (m at 1.7m male)
  [-0.2, 0.024, 0.03],
  [-0.12, 0.043, 0.045],
  [0.0, 0.05, 0.05],
  [0.18, 0.047, 0.046],
  [0.4, 0.04, 0.042],
  [0.65, 0.037, 0.041],
  [0.9, 0.034, 0.035],
  [1.0, 0.033, 0.033],
  [1.18, 0.034, 0.04],
  [1.4, 0.031, 0.036],
  [1.75, 0.022, 0.028],
  [2.0, 0.019, 0.026],
  [2.06, 0.018, 0.025],
]);
function buildArm(B, look, M, R, s, items) {
  const L = s > 0 ? 'L' : 'R';
  const o = look.outfit, sc = M.sc;
  const sh = R[BI['upperArm' + L]].toArray();
  const a0 = M.armAbd0;
  const dir = [s * Math.sin(a0), -Math.cos(a0), 0];
  const lat = [s * Math.cos(a0), Math.sin(a0), 0];
  const med = [-lat[0], -lat[1], -lat[2]];
  const Lua = M.upperArm, Lfa = M.foreArm;
  const armLen = Lua + Lfa;
  const g = M.girth * (M.f ? 0.88 : 1) * (M.k > 0 ? 0.95 : 1);
  const sleeve = o.sleeve || 0;
  const sleeveD = sleeve * armLen;
  const loose = { hoodie: 0.014, jacket: 0.016, kurta: 0.012, kameez: 0.01, kurti: 0.01, shirt: 0.01, tee: 0.012, polo: 0.01, top: 0.006, frock: 0.012, saree: 0.003 }[o.top] || 0.008;
  const dList = [];
  const pushD = (q) => dList.push(q);
  for (let q = -0.2; q <= 2.06 + 1e-9; q += 0.08) pushD(q);
  pushD(-0.16); pushD(-0.06); pushD(0.95); pushD(1.05); pushD(2.06);
  const sq = sleeveD / Lua;
  if (sleeve > 0 && sleeve < 0.98) { pushD(sq - 0.025); pushD(sq + 0.012); pushD(sq - 0.005); }
  dList.sort((a, b) => a - b);
  const qd = (q) => (q <= 1 ? q * Lua : Lua + (q - 1) * Lfa);
  const rings = [];
  for (const q of dList) {
    const d = qd(q);
    const P = ARMP(q);
    let ra = P[0] * sc * g, rb = P[1] * sc * g;
    let off = 0;
    if (sleeve > 0 && d <= sleeveD + 1e-6) {
      off = loose * sc * (1 + (sleeve < 0.5 ? 0.6 * smooth(0, sleeveD, d) : 0)) + (q < 0 ? 0.002 : 0);
      if (sleeve >= 0.98 && q > 1.8) off *= 1 - 0.6 * smooth(1.8, 2.0, q); // cuff
    }
    // deltoid: centre shifted outward/up near the top
    const cOff = 0.01 * sc * gauss(q + 0.05, 0.12);
    const c = [sh[0] + dir[0] * d + lat[0] * cOff, sh[1] + dir[1] * d + lat[1] * cOff, sh[2] + dir[2] * d];
    rings.push({ c, ax: med, az: [0, 0, 1], f: (th) => [(ra + off) * Math.cos(th), (rb + off) * Math.sin(th)], v: clamp(d / armLen, 0, 1), s: d });
  }
  loft(B, rings, {
    n: 18, arc: true, rect: rectUV('arms'), capStart: 0.012 * sc,
    weights: (p, d) => {
      const wTop = smooth(-0.06 * sc, 0.06 * sc, d);
      const wFa = smooth(Lua - 0.035 * sc, Lua + 0.035 * sc, d);
      const wH = smooth(armLen - 0.012 * sc, armLen + 0.02 * sc, d);
      const wUA = (1 - wFa) * (0.55 + 0.45 * wTop);
      const wCl = (1 - wFa) * (1 - wTop) * 0.45;
      return W('upperArm' + L, wUA, 'clav' + L, wCl, 'forearm' + L, wFa * (1 - wH), 'hand' + L, wH);
    },
    color: (p, d, th) => {
      const medial = Math.max(0, Math.cos(th));
      let a = 1 - 0.3 * medial * (1 - smooth(0.0, 0.14 * sc, d));
      if (sleeve > 0 && sleeve < 0.98 && d > sleeveD && d < sleeveD + 0.03) a -= 0.25 * (1 - (d - sleeveD) / 0.03);
      return [a, a, a];
    },
  });
  // ---- hand
  const W0 = R[BI['hand' + L]].toArray();
  const hl = M.handLen;
  const grip = items && items.gripSide === L;
  const curl = grip ? 0.6 : 0.25;
  const hs = sc * (M.f ? 0.92 : 1) * (M.k > 0 ? 0.95 : 1);
  const HP = keyed([[0, 0.019, 0.026], [0.12, 0.021, 0.036], [0.35, 0.017, 0.043], [0.55, 0.015, 0.044], [0.68, 0.014, 0.041], [0.85, 0.012, 0.036], [0.97, 0.01, 0.028], [1.0, 0.008, 0.02]]);
  const hrings = [];
  for (let i = 0; i <= 11; i++) {
    const t = i / 11;
    const d = t * hl;
    // curl fingers toward the palm (medial) beyond the knuckles
    const cu = Math.max(0, t - 0.5);
    const bend = curl * cu * cu * 4 * hl * 0.6;
    const ang = curl * smooth(0.5, 1, t) * 1.4;
    const c = [W0[0] + dir[0] * (d - bend * 0.3) + med[0] * bend, W0[1] + dir[1] * (d - bend * 0.3) + med[1] * bend, W0[2] + dir[2] * d];
    const P = HP(t);
    const axv = [med[0] * Math.cos(ang) - dir[0] * Math.sin(ang), med[1] * Math.cos(ang) - dir[1] * Math.sin(ang), 0];
    // a along ax (palm thickness, medial-lateral), b along az (palm width, front-back)
    hrings.push({ c, ax: axv, az: [0, 0, 1], f: (th) => sellipse(th, P[0] * hs, P[1] * hs, 2.6), v: t, s: d });
  }
  loft(B, hrings, {
    n: 14, rect: rectUV('hands'), capEnd: 0.006 * sc,
    weights: (p, d) => { const wh = smooth(-0.01 * sc, 0.015 * sc, d); return W('forearm' + L, 1 - wh, 'hand' + L, wh); },
    color: (p, d, th) => { const a = 1 - 0.2 * Math.max(0, Math.cos(th)) * smooth(0.3 * hl, 0.8 * hl, d); return [a, a, a]; },
  });
  // thumb: from the palm base, forward and down
  const tb = [W0[0] + dir[0] * hl * 0.18 + med[0] * 0.008 * hs, W0[1] + dir[1] * hl * 0.18, W0[2] + 0.024 * hs];
  const tdir = norm3([dir[0] * 0.8 + med[0] * (grip ? 0.45 : 0.25), dir[1] * 0.8, 0.55]);
  const tl = hl * 0.5;
  const trings = [];
  for (let i = 0; i <= 5; i++) {
    const t = i / 5;
    const r = (0.0115 - 0.003 * t) * hs;
    const c = [tb[0] + tdir[0] * tl * t, tb[1] + tdir[1] * tl * t, tb[2] + tdir[2] * tl * t];
    const ax = norm3(v3.cross(tdir, [0, 0, 1]).map((x) => x || 0.0001));
    const az = norm3(v3.cross(ax, tdir));
    trings.push({ c, ax, az, f: (th) => [r * Math.cos(th), r * 0.85 * Math.sin(th)], v: t, s: t });
  }
  loft(B, trings, { n: 8, rect: rectUV('hands'), capEnd: 0.005 * sc, capStart: 0.003 * sc, weights: () => W('hand' + L, 1) });
  // wrist accessory: watch / bangles as thin rings (geometry), only when wrist is bare
  if (look.wrist && sleeve < 0.95) {
    const d = armLen - 0.03 * sc;
    const P = ARMP(1.85);
    const rings2 = [];
    for (let i = 0; i <= 2; i++) {
      const dd = d + (i - 1) * (look.wrist === 'watch' ? 0.009 : 0.012) * sc;
      const c = [sh[0] + dir[0] * dd, sh[1] + dir[1] * dd, sh[2] + dir[2] * dd];
      rings2.push({ c, ax: med, az: [0, 0, 1], f: (th) => [(P[0] * sc * g + 0.0035) * Math.cos(th), (P[1] * sc * g + 0.0035) * Math.sin(th)], s: dd });
    }
    loft(B, rings2, { n: 12, uvAt: () => swatchUV(look.wrist === 'watch' ? 'watch' : 'earring'), weights: () => W('forearm' + L, 1) });
  }
}

// ------------------------------------------------------------------ legs & feet
const LEGP = keyed([
  // q (0 hip joint, 1 knee, 2 ankle), medial-lateral r, front-back r, centre z offset, centre x outward offset  (m at 1.7m)
  [-0.25, 0.066, 0.07, 0.0, 0.012],
  [0.0, 0.082, 0.087, 0.0, 0.01],
  [0.18, 0.08, 0.084, 0.002, 0.004],
  [0.45, 0.07, 0.074, 0.004, -0.002],
  [0.78, 0.056, 0.058, 0.004, -0.007],
  [1.0, 0.049, 0.051, 0.003, -0.009],
  [1.12, 0.049, 0.056, -0.004, -0.008],
  [1.3, 0.049, 0.058, -0.008, -0.007],
  [1.6, 0.039, 0.044, -0.004, -0.005],
  [1.85, 0.029, 0.032, 0.0, -0.004],
  [2.0, 0.027, 0.031, 0.0, -0.004],
  [2.1, 0.03, 0.04, 0.008, -0.004],
]);
function buildLeg(B, look, M, R, T, s) {
  const L = s > 0 ? 'L' : 'R';
  const o = look.outfit, sc = M.sc;
  const x0 = s * M.hipX;
  const Lt = M.hipY - M.kneeY, Ls = M.kneeY - M.ankleY;
  const yq = (q) => (q <= 1 ? M.hipY - q * Lt : M.kneeY - (q - 1) * Ls);
  const qy = (y) => (y >= M.kneeY ? (M.hipY - y) / Lt : 1 + (M.kneeY - y) / Ls);
  const g = M.girth * (M.f ? 1.05 : 1);
  const bottom = o.bottom;
  const skinLeg = bottom === 'saree' || bottom === 'bare';
  const shoes = o.shoes === 'sneaker' || o.shoes === 'formal';
  const trousers = bottom === 'jeans' || bottom === 'chinos' || bottom === 'pyjama' || bottom === 'salwar';
  // lowest y of the leg loft
  const yBot = trousers ? (bottom === 'salwar' ? M.ankleY - 0.0 : 0.03 * sc + M.soleH * 0.7) : shoes ? M.ankleY + 0.02 * sc : M.ankleY - 0.012 * sc;
  const ys = [];
  for (let q = -0.25; q <= 2.0; q += 0.1) ys.push(yq(q));
  ys.push(yq(0.95), yq(1.05), yq(1.9), yq(1.96));
  if (bottom === 'shorts') { ys.push(yq(0.86) + 0.003, yq(0.86) - 0.004); }
  if (bottom === 'churidar') for (let q = 1.55; q < 2.0; q += 0.035) ys.push(yq(q));
  const yTopV = M.hipY + 0.03 * sc;
  const filtered = ys.filter((y) => y >= yBot - 1e-6).concat([yBot]);
  filtered.sort((a, b) => b - a);
  const rings = [];
  for (const y of filtered) {
    const q = qy(y);
    const P = LEGP(q);
    let ra = P[0] * sc * g, rb = P[1] * sc * g;
    const cz = P[2] * sc, cx = s * P[3] * sc;
    let off = 0;
    if (bottom === 'jeans' || bottom === 'chinos') {
      off = 0.008 * sc;
      const straight = (bottom === 'jeans' ? 0.05 : 0.053) * sc * (0.9 + 0.1 * g);
      if (q > 1.0) { ra = Math.max(ra + off, straight); rb = Math.max(rb + off, straight * 1.04); off = 0; }
      if (y < 0.06 * sc) { ra += 0.004 * sc; rb += 0.008 * sc; }
    } else if (bottom === 'pyjama') {
      off = 0.016 * sc;
      if (q > 1.0) { ra = Math.max(ra + off, 0.06 * sc); rb = Math.max(rb + off, 0.062 * sc); off = 0; }
    } else if (bottom === 'salwar') {
      off = (0.03 + 0.03 * smooth(0, 1.4, q)) * sc * (1 - smooth(1.75, 1.98, q) * 0.85);
    } else if (bottom === 'churidar') {
      off = 0.004 * sc + (q > 1.55 ? 0.005 * sc * Math.abs(Math.sin((y / (0.017 * sc)) * PI)) : 0);
    } else if (bottom === 'leggings') {
      off = 0.003 * sc;
    } else if (bottom === 'shorts') {
      off = q < 0.86 ? (0.018 + 0.012 * smooth(0, 0.8, q)) * sc : 0;
    }
    rings.push({ c: [x0 + cx, y, cz], ax: [-s, 0, 0], az: [0, 0, 1], f: (th) => [(ra + off) * Math.cos(th), (rb + off) * Math.sin(th)], v: clamp((yTopV - y) / (yTopV - M.ankleY), 0, 1), s: y });
  }
  // trouser hem: inner lip
  let capEnd = 0.012 * sc;
  if (trousers) {
    const last = rings[rings.length - 1];
    const y = last.c[1] + 0.006 * sc;
    const f0 = last.f;
    rings.push({ c: [last.c[0], y, last.c[2]], ax: last.ax, az: last.az, f: (th) => { const q = f0(th); return [q[0] * 0.62, q[1] * 0.62]; }, v: 1, s: y });
    capEnd = 0.0;
  }
  loft(B, rings, {
    n: 22, arc: true, rect: rectUV('legs'), capEnd, capStart: 0.01 * sc,
    weights: (p, y) => {
      const wPel = 0.6 * smooth(M.hipY - 0.06 * sc, M.hipY + 0.07 * sc, y);
      const wSh = 1 - smooth(M.kneeY - 0.05 * sc, M.kneeY + 0.05 * sc, y);
      const wFt = trousers ? 0 : 1 - smooth(M.ankleY - 0.01, M.ankleY + 0.03 * sc, y);
      return W('pelvis', wPel, 'thigh' + L, (1 - wPel) * (1 - wSh), 'shin' + L, wSh * (1 - wFt), 'foot' + L, wFt);
    },
    color: (p, y, th) => {
      let a = 1;
      const medial = Math.max(0, Math.cos(th));
      a -= 0.3 * medial * (1 - smooth(M.crotchY - 0.12 * sc, M.crotchY, y));
      if (trousers && y < yBot + 0.008 * sc) a = 0.45;
      if (bottom === 'shorts' && y < yq(0.86) && y > yq(0.86) - 0.03) a -= 0.25;
      return [a, a, a];
    },
  });
}

const FOOTP = keyed([
  // t (heel back 0 .. toe tip 1), half width, top height  (m at 1.7m), for shoes
  [0.0, 0.019, 0.05],
  [0.04, 0.031, 0.072],
  [0.12, 0.037, 0.086],
  [0.25, 0.039, 0.094],
  [0.4, 0.042, 0.086],
  [0.55, 0.047, 0.067],
  [0.7, 0.05, 0.052],
  [0.82, 0.048, 0.044],
  [0.92, 0.04, 0.036],
  [1.0, 0.024, 0.026],
]);
const BAREP = keyed([
  [0.0, 0.018, 0.045],
  [0.05, 0.028, 0.062],
  [0.15, 0.032, 0.075],
  [0.3, 0.033, 0.078],
  [0.45, 0.038, 0.06],
  [0.6, 0.044, 0.042],
  [0.72, 0.046, 0.03],
  [0.85, 0.043, 0.024],
  [0.95, 0.036, 0.02],
  [1.0, 0.022, 0.014],
]);
function buildFoot(B, look, M, R, s) {
  const L = s > 0 ? 'L' : 'R';
  const o = look.outfit, sc = M.sc;
  const shoe = o.shoes === 'sneaker' || o.shoes === 'formal';
  const x0 = s * M.hipX;
  const zb = -M.heelBack * 1.05, zt = M.toeF;
  const fl = zt - zb;
  const sole = M.soleH;
  const fs = M.sc * (M.f ? 0.93 : 1) * (M.k > 0 ? 0.92 : 1);
  const footW = (wFn) => (p, t) => {
    const z = p[2];
    const wt = smooth(M.ballF - 0.02 * sc, M.ballF + 0.025 * sc, z);
    // shoe collar / ankle region follows the shin a bit
    const wsh = shoe ? 0 : 0.0;
    return W('foot' + L, (1 - wt) * (1 - wsh), 'toe' + L, wt, 'shin' + L, wsh);
  };
  const ringsFor = (P, y0, extraW, hMul) => {
    const rings = [];
    const n = 13;
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const z = zb + t * fl;
      const Q = P(t);
      const w = Q[0] * fs + extraW, h = Q[1] * fs * hMul;
      rings.push({
        c: [x0 + (t > 0.5 ? -s * 0.006 * sc * (t - 0.5) : 0), y0, z], ax: [1, 0, 0], az: [0, 1, 0], v: t, s: t,
        f: (th) => {
          // th = 0 bottom, pi/2 side (+X), pi top, 3pi/2 other side
          const c = -Math.cos(th), sn = Math.sin(th);
          const e = c < 0 ? 5 : 2.3;
          const x = w * Math.sign(sn) * Math.pow(Math.abs(sn), 2 / e);
          const y = h / 2 + h / 2 * Math.sign(c) * Math.pow(Math.abs(c), 2 / e);
          return [x, y];
        },
      });
    }
    return rings;
  };
  if (shoe) {
    const hMul = o.shoes === 'formal' ? 0.86 : 1;
    const rings = ringsFor(FOOTP, 0, 0.002, hMul);
    const suv = swatchUV('sole');
    loft(B, rings, {
      n: 20, arc: true, rect: rectUV('shoes'), capStart: 0.006 * sc, capEnd: 0.008 * sc,
      uvAt: (p) => (p[1] < sole ? suv : null),
      weights: footW(),
      color: (p) => { const a = p[1] < 0.004 ? 0.55 : p[1] < sole ? 0.9 : 1; return [a, a, a]; },
    });
  } else {
    // sole slab + bare/sandal foot on top
    const srings = [];
    const n = 11;
    for (let i = 0; i <= n; i++) {
      const t = i / n;
      const z = zb - 0.006 + t * (fl + 0.014);
      const Q = BAREP(t);
      const w = Q[0] * fs + 0.006;
      srings.push({ c: [x0, 0, z], ax: [1, 0, 0], az: [0, 1, 0], v: t, s: t, f: (th) => { const c = -Math.cos(th), sn = Math.sin(th); const x = w * Math.sign(sn) * Math.pow(Math.abs(sn), 0.4); const y = sole / 2 + sole / 2 * Math.sign(c) * Math.pow(Math.abs(c), 0.4); return [x, y]; } });
    }
    const suv = swatchUV('sole');
    loft(B, srings, { n: 16, uvAt: () => suv, capStart: 0.003, capEnd: 0.004, weights: footW(), color: (p) => { const a = p[1] < 0.004 ? 0.5 : 0.9; return [a, a, a]; } });
    const rings = ringsFor(BAREP, sole - 0.002, 0, o.shoes === 'flat' ? 1.05 : 1);
    loft(B, rings, { n: 16, arc: true, rect: rectUV('shoes'), capStart: 0.005 * sc, capEnd: 0.005 * sc, weights: footW(), color: (p) => { const a = p[1] < sole + 0.006 ? 0.8 : 1; return [a, a, a]; } });
  }
}

// ------------------------------------------------------------------ skirt (kurta / kameez / frock / saree)
function buildSkirt(B, look, M, R, T) {
  const o = look.outfit, sc = M.sc, H = M.H;
  const saree = o.top === 'saree';
  const yTop = saree ? T.sareeWaistY + 0.01 : T.mapY(0.54);
  const yHem = saree ? 0.025 * sc : Math.max(o.skirtLen * H, 0.12);
  const flare = saree ? 0.06 * sc : o.top === 'frock' ? 0.08 * sc : (o.top === 'kurta' && look.sex === 'm' ? 0.05 : 0.045) * sc;
  const top = T.shapeAt(yTop);
  const nr = 16;
  const rings = [];
  const hipFn = T.shapeAt(M.hipY - 0.01);
  for (let i = 0; i <= nr; i++) {
    const t = i / nr;
    const y = lerp(yTop, yHem, t);
    const add = 0.004 * sc + flare * Math.pow(t, 1.2) + (saree ? 0.006 * sc : 0);
    const tb = smooth(0, 0.25, t);
    rings.push({
      c: [0, y, -0.005 * sc * t], ax: [1, 0, 0], az: [0, 0, 1], v: t, s: t,
      f: (th) => {
        const a = top(th), b = hipFn(th);
        // below the hips keep at least the hip width
        let x = lerp(a[0], Math.sign(b[0]) * Math.max(Math.abs(a[0]), Math.abs(b[0])), tb);
        let z = lerp(a[1], Math.sign(b[1]) * Math.max(Math.abs(a[1]), Math.abs(b[1])), tb);
        // smooth to an ellipse lower down (drape hides the body shape)
        const ex = Math.cos(th) * Math.max(Math.abs(b[0]), 0.0001), ez = Math.sin(th) * (Math.sin(th) > 0 ? Math.abs(hipFn(PI / 2)[1]) : Math.abs(hipFn(1.5 * PI)[1]));
        const sm = smooth(0.2, 0.8, t);
        x = lerp(x, ex, sm); z = lerp(z, ez, sm);
        const L = Math.hypot(x, z) || 1;
        let push = add;
        if (saree) {
          const dF = Math.atan2(Math.sin(th - PI / 2), Math.cos(th - PI / 2));
          push += 0.007 * sc * Math.sin(dF * 16) * gauss(dF + 0.05, 0.3) * (0.4 + 0.6 * t);
        } else push += 0.004 * sc * Math.sin(th * 9 + 1) * smooth(0.3, 1, t);
        return [x + x / L * push, z + z / L * push];
      },
    });
  }
  // hem lip (turn inward)
  const last = rings[rings.length - 1];
  rings.push({ c: [0, yHem + 0.01 * sc, last.c[2]], ax: [1, 0, 0], az: [0, 0, 1], v: 1, s: 1.02, f: (th) => { const q = last.f(th); return [q[0] * 0.93, q[1] * 0.93]; } });
  const kmax = saree ? 0.85 : 0.82;
  loft(B, rings, {
    n: 48, arc: true, rect: rectUV('skirt'),
    weights: (p, t) => {
      const tt = Math.min(t, 1);
      const k = kmax * smooth(0.0, 0.85, tt);
      const side = clamp(p[0] / (M.hipX * 1.5), -1, 1);
      const wl = 0.5 + 0.5 * side;
      const ks = saree ? 0.28 * smooth(0.55, 1, tt) : 0;
      return W('pelvis', 1 - k, 'thighL', k * wl * (1 - ks), 'thighR', k * (1 - wl) * (1 - ks), 'shinL', k * wl * ks, 'shinR', k * (1 - wl) * ks);
    },
    color: (p, t) => { const a = t > 1 ? 0.45 : 1 - 0.15 * smooth(0.8, 1, t) * 0; return [a, a, a]; },
  });
}

// ------------------------------------------------------------------ drapes (dupatta, saree pallu)
function buildDrape(B, look, M, R, T) {
  const o = look.outfit, sc = M.sc;
  const F = (fa) => T.mapY(fa);
  const tp = (fa, th, off) => T.point(F(fa), th, off * sc);
  const shTop = (s, off = 0) => [s * M.shoulderX * 0.62, M.shoulderY + (0.05 + off) * sc, -0.012 * sc];
  const outward = (p) => {
    const r = [p[0], 0, p[2] + 0.01 * sc];
    const up = 3 * smooth(M.shoulderY - 0.02 * sc, M.shoulderY + 0.04 * sc, p[1]);
    return norm3([r[0], up, r[2]]);
  };
  const side = (p, t) => norm3(v3.cross(t, outward(p)));
  const duv = rectUV('drape');
  let pts, width, thick = 0.007 * sc;
  const BK = 1.5 * PI, FR = 0.5 * PI;
  if (o.top === 'saree') {
    pts = [tp(0.74, FR - 0.5, 0.02), tp(0.79, FR - 0.85, 0.02), shTop(1, 0.005), tp(0.785, BK + 0.75, 0.02), tp(0.7, BK + 0.45, 0.025), tp(0.6, BK + 0.3, 0.03),
      [0.07 * sc, F(0.5), T.point(F(0.5), BK + 0.25, 0.045 * sc)[2]], [0.06 * sc, F(0.42), T.point(F(0.5), BK + 0.2, 0.06 * sc)[2] - 0.01 * sc]];
    width = (t) => lerp(0.13, 0.33, smooth(0.15, 0.6, t)) * sc;
  } else if (o.dupattaStyle === 'one') {
    pts = [tp(0.56, FR - 0.55, 0.03), tp(0.66, FR - 0.6, 0.03), tp(0.75, FR - 0.75, 0.025), shTop(1, 0), tp(0.78, BK + 0.6, 0.02), tp(0.68, BK + 0.45, 0.025), tp(0.55, BK + 0.45, 0.03)];
    width = (t) => lerp(0.17, 0.1, gauss(t - 0.5, 0.12)) * sc;
  } else {
    pts = [tp(0.55, BK + 0.6, 0.03), tp(0.67, BK + 0.6, 0.025), tp(0.775, BK + 0.65, 0.02), shTop(1, 0), tp(0.765, FR - 0.75, 0.025), tp(0.705, FR - 0.25, 0.035), tp(0.7, FR, 0.04), tp(0.705, FR + 0.25, 0.035), tp(0.765, FR + 0.75, 0.025), shTop(-1, 0), tp(0.775, BK - 0.65, 0.02), tp(0.67, BK - 0.6, 0.025), tp(0.55, BK - 0.6, 0.03)];
    width = (t) => lerp(0.17, 0.09, Math.max(gauss(t - 0.25, 0.06), gauss(t - 0.75, 0.06), 0.5 * gauss(t - 0.5, 0.1))) * sc;
  }
  ribbon(B, pts, o.top === 'saree' ? 26 : 34, width, thick, side, {
    n: 12, e: 8, rect: duv, capStart: 0.0, capEnd: 0.0,
    weights: (p, t) => {
      const y = p[1];
      const wd = (1 - smooth(F(0.55), F(0.74), y)) * (p[2] < -0.02 ? 1 : 0.3);
      const sideL = p[0] > 0 ? 'L' : 'R';
      const wcl = 0.4 * smooth(M.shoulderY - 0.04 * sc, M.shoulderY + 0.03 * sc, y);
      const wp = o.top === 'saree' ? 0.5 * (1 - smooth(F(0.45), F(0.56), y)) : 0;
      return W('chest', (1 - wd) * (1 - wcl) * (1 - wp), 'clav' + sideL, (1 - wd) * wcl, 'drape', wd * (1 - wp), 'pelvis', wp);
    },
    color: (p, t, th) => { const a = 0.82 + 0.18 * Math.abs(Math.sin(th)); return [a, a, a]; },
  });
}

// ------------------------------------------------------------------ bags
function buildBag(B, look, M, R, T) {
  const sc = M.sc;
  const s = look.carrySide === 'L' ? 1 : -1;
  const sideL = s > 0 ? 'L' : 'R';
  const buv = itemUV('bag');
  const strapUV = swatchUV('strap');
  const F = (fa) => T.mapY(fa);
  const BK = 1.5 * PI, FR = 0.5 * PI;
  const box = (c, wx, hy, dz, weights, rnd = 3.5) => {
    const rings = [];
    const nr = 6;
    for (let i = 0; i <= nr; i++) {
      const t = i / nr;
      const y = c[1] - hy / 2 + hy * t;
      const k = 1 - 0.12 * Math.pow(Math.abs(t - 0.5) * 2, 4);
      rings.push({ c: [c[0], y, c[2]], ax: [1, 0, 0], az: [0, 0, 1], v: t, s: t, f: (th) => sellipse(th, wx / 2 * k, dz / 2 * k, rnd) });
    }
    loft(B, rings, { n: 16, rect: buv, capStart: 0.006 * sc, capEnd: 0.004 * sc, weights, color: (p) => { const a = p[1] < c[1] - hy * 0.4 ? 0.7 : 1; return [a, a, a]; } });
  };
  const strapW = (p) => {
    const y = p[1];
    const wb = 1 - smooth(F(0.6), F(0.72), y);
    return W('chest', (1 - wb), 'bag', wb);
  };
  if (look.bagStyle === 'shoulder') {
    const hipW = T.dims(M.hipY).w;
    const c = [s * (hipW + 0.05 * sc), M.hipY + 0.05 * sc, -0.015 * sc];
    box(c, 0.08 * sc, 0.2 * sc, 0.27 * sc, () => W('bag', 1));
    const pts = [[c[0], c[1] + 0.1 * sc, c[2] + 0.1 * sc], [s * (hipW + 0.035 * sc), F(0.66), 0.075 * sc], [s * M.shoulderX * 0.8, F(0.79), 0.05 * sc], [s * M.shoulderX * 0.78, M.shoulderY + 0.055 * sc, -0.015 * sc], [s * M.shoulderX * 0.8, F(0.79), -0.08 * sc], [s * (hipW + 0.035 * sc), F(0.66), -0.1 * sc], [c[0], c[1] + 0.1 * sc, c[2] - 0.1 * sc]];
    ribbon(B, pts, 20, 0.022 * sc, 0.006 * sc, (p, t) => norm3(v3.cross(t, [s, 0.4, 0])), { n: 6, e: 6, uvAt: () => strapUV, weights: (p) => { const y = p[1]; const wb = 1 - smooth(F(0.62), F(0.76), y); return W('clav' + sideL, (1 - wb) * 0.6, 'chest', (1 - wb) * 0.4, 'bag', wb); } });
  } else if (look.bagStyle === 'sling') {
    const o = -s; // strap over the opposite shoulder, bag at this side's hip front
    const c0 = T.point(F(0.56), FR - s * 0.75, 0.035 * sc);
    const c = [c0[0], c0[1], c0[2]];
    box(c, 0.17 * sc, 0.14 * sc, 0.055 * sc, () => W('spine', 0.5, 'pelvis', 0.5));
    const pts = [[c[0] - s * 0.07 * sc, c[1] + 0.06 * sc, c[2]], T.point(F(0.64), FR - s * 0.35, 0.02 * sc), T.point(F(0.72), FR + s * 0.25, 0.02 * sc), T.point(F(0.785), FR + s * 0.75, 0.015 * sc), [o * M.shoulderX * 0.7, M.shoulderY + 0.05 * sc, -0.012 * sc], T.point(F(0.78), BK - s * 0.75, 0.015 * sc), T.point(F(0.68), BK - s * 0.1, 0.02 * sc), T.point(F(0.59), BK + s * 0.6, 0.025 * sc), [c[0] + s * 0.02 * sc, c[1] + 0.05 * sc, c[2] - 0.05 * sc]];
    ribbon(B, pts, 30, 0.03 * sc, 0.006 * sc, (p, t) => { const r = norm3([p[0], 3 * smooth(M.shoulderY - 0.03 * sc, M.shoulderY + 0.04 * sc, p[1]), p[2]]); return norm3(v3.cross(t, r)); }, {
      n: 6, e: 6, uvAt: () => strapUV,
      weights: (p) => { const y = p[1]; const wp = 1 - smooth(F(0.55), F(0.63), y); const wc = smooth(F(0.62), F(0.72), y); return W('pelvis', wp, 'spine', Math.max(0, 1 - wp - wc), 'chest', wc); },
    });
  } else {
    // backpack
    const zBack = T.point(F(0.69), BK, 0)[2];
    const c = [0, F(0.67), zBack - 0.085 * sc];
    box(c, 0.3 * sc, 0.4 * sc, 0.15 * sc, () => W('chest', 0.85, 'spine', 0.15), 4);
    for (const q of [1, -1]) {
      const pts = [[q * 0.08 * sc, c[1] + 0.17 * sc, c[2] + 0.04 * sc], [q * M.shoulderX * 0.55, M.shoulderY + 0.05 * sc, -0.03 * sc], T.point(F(0.775), FR - q * 0.62, 0.016 * sc), T.point(F(0.69), FR - q * 0.82, 0.016 * sc), T.point(F(0.62), PI / 2 - q * 1.3, 0.018 * sc), [q * 0.12 * sc, c[1] - 0.17 * sc, c[2] + 0.06 * sc]];
      ribbon(B, pts, 20, 0.045 * sc, 0.012 * sc, (p, t) => { const r = norm3([p[0], 3 * smooth(M.shoulderY - 0.03 * sc, M.shoulderY + 0.04 * sc, p[1]), p[2]]); return norm3(v3.cross(t, r)); }, {
        n: 6, e: 4, uvAt: () => swatchUV('bagDark'), weights: () => W('chest', 1),
      });
    }
  }
}

// ------------------------------------------------------------------ hand-held items
// Built in the hand's local frame, using the hand's root-space transform in the carry pose.
function buildItem(B, look, M, R, hand) {
  const sc = M.sc;
  const kind = look.carry;
  const L = look.carrySide;
  const s = L === 'L' ? 1 : -1;
  const { pos, quat } = hand; // carry-pose root-space transform of the hand bone
  const inv = quat.clone().invert();
  const rest = R[BI['hand' + L]];
  const toRest = (p) => { const v = new THREE.Vector3(p[0], p[1], p[2]).sub(pos).applyQuaternion(inv).add(rest); return [v.x, v.y, v.z]; };
  const dirToLocal = (d) => { const v = new THREE.Vector3(d[0], d[1], d[2]).applyQuaternion(inv); return [v.x, v.y, v.z]; };
  const hl = M.handLen;
  const wts = () => W('hand' + L, 1);
  // useful carry-pose directions
  const palmN = new THREE.Vector3(-s, 0, 0).applyQuaternion(quat); // palm faces medial at rest
  const along = new THREE.Vector3(0, -1, 0).applyQuaternion(quat); // fingers
  const grip = new THREE.Vector3(0, -0.45 * hl, 0).applyQuaternion(quat).add(pos);
  const extra = {};
  if (kind === 'popcorn' || kind === 'cup') {
    const pop = kind === 'popcorn';
    const h = (pop ? 0.17 : 0.16) * Math.min(1, sc * 1.05), rb = (pop ? 0.058 : 0.034) * Math.min(1, sc * 1.1), rt = (pop ? 0.08 : 0.046) * Math.min(1, sc * 1.1);
    const pn = new THREE.Vector3(palmN.x, 0, palmN.z).normalize();
    const c = grip.clone().addScaledVector(pn, lerp(rb, rt, 0.4) + 0.012 * sc);
    c.y += h * 0.12;
    const up = [0, 1, 0];
    // rings in carry-pose root space, then mapped to rest space
    const ax = [1, 0, 0], az = [0, 0, 1];
    const rings = [];
    for (let i = 0; i <= 6; i++) {
      const t = i / 6;
      const r = lerp(rb, rt, t) + (t > 0.95 ? 0.003 : 0);
      const y = c.y - h / 2 + h * t;
      rings.push({ c: [c.x, y, c.z], ax, az, v: 1 - t, s: t, f: (th) => [r * Math.cos(th), r * Math.sin(th)] });
    }
    // rim roll
    rings.push({ c: [c.x, c.y + h / 2 + 0.004, c.z], ax, az, v: 0, s: 1.1, f: (th) => [(rt + 0.004) * Math.cos(th), (rt + 0.004) * Math.sin(th)] });
    rings.push({ c: [c.x, c.y + h / 2 + 0.006, c.z], ax, az, v: 0, s: 1.2, f: (th) => [(rt - 0.002) * Math.cos(th), (rt - 0.002) * Math.sin(th)] });
    for (const r of rings) { const c0 = r.c, f0 = r.f; r.c = toRest(c0); r.ax = dirToLocal(ax); r.az = dirToLocal(az); r.f = f0; }
    const cuv = itemUV(pop ? 'tub' : 'cup');
    loft(B, rings, { n: 20, rect: cuv, capStart: 0.0, weights: wts, uvAt: (p, u, v, sp) => (sp > 1 ? swatchUV(pop ? 'tubRim' : 'lid') : null), color: (p, sp) => { const a = sp < 0.05 ? 0.7 : 1; return [a, a, a]; } });
    const top = [c.x, c.y + h / 2 + 0.004, c.z];
    if (pop) {
      // heaped popcorn: bumpy dome
      const domeC = toRest(top);
      ellipsoid(B, domeC, [rt * 0.98, 0.045 * sc, rt * 0.98], { x: dirToLocal([1, 0, 0]), y: dirToLocal(up), z: dirToLocal([0, 0, 1]) }, {
        n: 22, nLat: 10, uvAt: () => swatchUV('popcorn'), weights: wts,
        bump: (th, lat) => (lat > -0.2 ? 0.14 * Math.pow(Math.abs(Math.sin(th * 7 + lat * 9) * Math.sin(th * 5 - lat * 11)), 0.6) - 0.05 : -0.2),
        color: (p) => { const k = 0.8 + 0.2 * Math.abs(Math.sin(p[0] * 900 + p[2] * 700)); return [k, k * 0.98, k * 0.92]; },
      });
      extra.top = [top[0], top[1] + 0.05 * sc, top[2]];
    } else {
      // lid dome + straw
      const lidC = toRest([top[0], top[1] + 0.002, top[2]]);
      ellipsoid(B, lidC, [rt * 0.98, 0.012, rt * 0.98], { x: dirToLocal([1, 0, 0]), y: dirToLocal(up), z: dirToLocal([0, 0, 1]) }, { n: 18, nLat: 6, uvAt: () => swatchUV('lid'), weights: wts });
      const sb = [top[0] + 0.006, top[1] - 0.02, top[2] - 0.004];
      const sdir = norm3([0.12, 1, -0.08]);
      const sl = 0.1 * sc + 0.02;
      const srings = [];
      for (let i = 0; i <= 2; i++) { const t = i / 2; srings.push({ c: toRest([sb[0] + sdir[0] * sl * t, sb[1] + sdir[1] * sl * t, sb[2] + sdir[2] * sl * t]), ax: dirToLocal([1, 0, 0]), az: dirToLocal([0, 0, 1]), s: t, f: (th) => [0.0042 * Math.cos(th), 0.0042 * Math.sin(th)] }); }
      loft(B, srings, { n: 8, uvAt: () => swatchUV('straw'), capEnd: 0.001, weights: wts });
      extra.top = [sb[0] + sdir[0] * sl, sb[1] + sdir[1] * sl, sb[2] + sdir[2] * sl];
    }
    extra.bottom = [c.x, c.y - h / 2, c.z];
  } else if (kind === 'phone') {
    // lies on the (supinated) palm, screen tilted towards the face
    const pw = 0.074, ph = 0.155, pt = 0.0085;
    const nrm = new THREE.Vector3(0, 0.82, -0.57).normalize();          // screen normal (towards eyes)
    let fw = along.clone().addScaledVector(nrm, -along.dot(nrm)).normalize(); // long axis roughly along fingers
    const sd = new THREE.Vector3().crossVectors(fw, nrm).normalize();
    const c = grip.clone().addScaledVector(palmN, 0.01).addScaledVector(fw, 0.02);
    const rings = [];
    for (let i = 0; i <= 3; i++) {
      const t = i / 3;
      const cc = c.clone().addScaledVector(fw, (t - 0.5) * ph);
      const k = (i === 0 || i === 3) ? 0.92 : 1;
      rings.push({ c: toRest([cc.x, cc.y, cc.z]), ax: dirToLocal([sd.x, sd.y, sd.z]), az: dirToLocal([nrm.x, nrm.y, nrm.z]), v: t, s: t, f: (th) => sellipse(th, pw / 2 * k, pt / 2, 6) });
    }
    const puv = itemUV('phone');
    loft(B, rings, {
      n: 16, capStart: 0.001, capEnd: 0.001, weights: wts,
      uvAt: (p, u, v, sp, th) => (Math.sin(th) > 0.7 ? [puv[0] + (puv[2] - puv[0]) * (0.5 + 0.5 * Math.cos(th)), puv[1] + (puv[3] - puv[1]) * v] : swatchUV('phoneCase')),
    });
    extra.top = [c.x + fw.x * ph / 2, c.y + fw.y * ph / 2, c.z + fw.z * ph / 2];
    extra.bottom = [c.x - fw.x * ph / 2, c.y - fw.y * ph / 2, c.z - fw.z * ph / 2];
  }
  // return extremes in rest space for the hand bone (box points)
  const out = [];
  if (extra.top) out.push(toRest(extra.top));
  if (extra.bottom) out.push(toRest(extra.bottom));
  return out;
}

// ------------------------------------------------------------------ shared resources
let BLOB_TEX = null;
function blobTexture() {
  if (BLOB_TEX) return BLOB_TEX;
  const N = 64;
  const data = new Uint8Array(N * N * 4);
  for (let y = 0; y < N; y++) for (let x = 0; x < N; x++) {
    const dx = (x + 0.5) / N * 2 - 1, dy = (y + 0.5) / N * 2 - 1;
    const r = Math.sqrt(dx * dx + dy * dy);
    const a = Math.pow(clamp(1 - r, 0, 1), 1.6);
    const i = (y * N + x) * 4;
    data[i] = 0; data[i + 1] = 0; data[i + 2] = 0; data[i + 3] = Math.round(a * 255);
  }
  BLOB_TEX = new THREE.DataTexture(data, N, N, THREE.RGBAFormat);
  BLOB_TEX.magFilter = THREE.LinearFilter; BLOB_TEX.minFilter = THREE.LinearMipmapLinearFilter; BLOB_TEX.generateMipmaps = true;
  BLOB_TEX.needsUpdate = true;
  return BLOB_TEX;
}

// ------------------------------------------------------------------ public API
export function createHuman(seed, opts = {}) {
  const look = sampleLook(seed, opts);
  const M = measure(look);
  const R = restPositions(M, look);
  const T = makeTorso(M, look);
  // bones
  const bones = BONES.map((n) => { const b = new THREE.Bone(); b.name = n; return b; });
  for (let i = 1; i < BONES.length; i++) {
    const pi = BI[PARENT[BONES[i]]];
    bones[pi].add(bones[i]);
    bones[i].position.copy(R[i]).sub(R[pi]);
  }
  const gait = new Gait(M, look, R);
  const carry = look.carry && CARRY[look.carry] ? { kind: look.carry, side: look.carrySide } : null;
  // carry-pose hand transform (root space) for item placement
  let hand = null;
  if (carry) {
    const pose = gait.pose(0, 0, 0, undefined, carry);
    applyPose(bones, pose);
    bones[0].updateMatrixWorld(true);
    const hb = bones[BI['hand' + carry.side]];
    hand = { pos: new THREE.Vector3(), quat: new THREE.Quaternion() };
    hb.matrixWorld.decompose(hand.pos, hand.quat, new THREE.Vector3());
    for (let i = 1; i < bones.length; i++) { bones[i].quaternion.identity(); bones[i].position.copy(R[i]).sub(R[BI[PARENT[BONES[i]]]]); }
    bones[0].updateMatrixWorld(true);
  }
  // geometry
  const B = new GeoBuilder();
  const items = { gripSide: carry ? carry.side : null };
  const face = buildBody(B, look, M, R, T, items);
  let itemPts = [];
  if (carry && hand) itemPts = buildItem(B, look, M, R, hand);
  const geom = B.build();
  // texture
  const geoInfo = { H: M.H, torsoTop: T.top, torsoBot: T.bot, waistY: M.waistY, hipY: M.hipY, chestY: M.chestY, crotchY: M.crotchY, beltY: T.beltY, sareeWaistY: T.sareeWaistY, blouseY: T.hemY, face };
  const painted = paintAtlas(look, geoInfo);
  const matOpts = { vertexColors: true, roughness: 1, metalness: 0, alphaHash: true };
  const disposables = [geom];
  if (painted) {
    const map = new THREE.CanvasTexture(painted.canvas);
    map.colorSpace = THREE.SRGBColorSpace;
    map.anisotropy = 4;
    map.generateMipmaps = true;
    map.minFilter = THREE.LinearMipmapLinearFilter;
    const rmap = new THREE.CanvasTexture(painted.rough);
    rmap.generateMipmaps = true;
    matOpts.map = map; matOpts.roughnessMap = rmap;
    disposables.push(map, rmap);
    if (look.carry === 'phone') {
      // emissive screen
      const ec = document.createElement('canvas');
      ec.width = 128; ec.height = 128;
      const eg = ec.getContext('2d');
      eg.fillStyle = '#000'; eg.fillRect(0, 0, 128, 128);
      const r = itemUV('phone');
      eg.fillStyle = 'rgb(150,175,210)';
      eg.fillRect(r[0] * 128 + 0.8, r[1] * 128 + 0.8, (r[2] - r[0]) * 128 - 1.6, (r[3] - r[1]) * 128 - 1.6);
      const em = new THREE.CanvasTexture(ec);
      em.colorSpace = THREE.SRGBColorSpace;
      matOpts.emissiveMap = em; matOpts.emissive = new THREE.Color(1, 1, 1); matOpts.emissiveIntensity = 0.9;
      disposables.push(em);
    }
  } else {
    matOpts.color = new THREE.Color().setRGB(look.outfit.topC[0] / 255, look.outfit.topC[1] / 255, look.outfit.topC[2] / 255, THREE.SRGBColorSpace);
  }
  const mat = new THREE.MeshStandardMaterial(matOpts);
  disposables.push(mat);
  const mesh = new THREE.SkinnedMesh(geom, mat);
  mesh.name = 'human';
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  mesh.add(bones[0]);
  mesh.updateMatrixWorld(true);
  const skeleton = new THREE.Skeleton(bones);
  mesh.bind(skeleton);
  // generous bounds for culling (pose changes)
  mesh.boundingSphere = new THREE.Sphere(new THREE.Vector3(0, M.H * 0.5, 0), M.H * 0.78);
  mesh.boundingBox = new THREE.Box3(new THREE.Vector3(-0.6, 0, -0.8), new THREE.Vector3(0.6, M.H + 0.1, 0.8));
  const object = new THREE.Group();
  object.name = 'person';
  object.add(mesh);
  // contact shadow (feet + body), updated in setPose
  const cg = new THREE.BufferGeometry();
  const cpos = new Float32Array(12 * 3);
  const ccol = new Float32Array(12 * 4);
  const cuv = new Float32Array([0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1]);
  cg.setAttribute('position', new THREE.BufferAttribute(cpos, 3));
  cg.setAttribute('color', new THREE.BufferAttribute(ccol, 4));
  cg.setAttribute('uv', new THREE.BufferAttribute(cuv, 2));
  cg.setIndex([0, 2, 1, 0, 3, 2, 4, 6, 5, 4, 7, 6, 8, 10, 9, 8, 11, 10]);
  const cmat = new THREE.MeshBasicMaterial({ map: blobTexture(), vertexColors: true, transparent: true, depthWrite: false, opacity: 1, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
  const contact = new THREE.Mesh(cg, cmat);
  contact.name = 'contactShadow';
  contact.frustumCulled = false;
  contact.renderOrder = 1;
  object.add(contact);
  disposables.push(cg, cmat);

  // --------------------------------------------------- box points (bone, rest point)
  const bp = [];
  const addBP = (bone, p) => bp.push({ bi: BI[bone], local: new THREE.Vector3(p[0], p[1], p[2]).sub(R[BI[bone]]) });
  const sc = M.sc;
  const hairTop = { short: 0.016, crop: 0.008, receding: 0.008, medium: 0.026, quiff: 0.03, bob: 0.02, long: 0.016 }[look.hair] || 0.01;
  addBP('head', [0, M.H + hairTop * sc + (look.hair === 'bun' ? 0.005 : 0), M.headZ - 0.01 * sc]);
  addBP('head', [0, M.chinY + 0.45 * M.headH, M.headZ + M.headL * 0.47]);
  addBP('head', [0, M.chinY + 0.55 * M.headH, M.headZ - M.headL * 0.56]);
  addBP('head', [M.headB * 0.52, M.chinY + 0.6 * M.headH, M.headZ]);
  addBP('head', [-M.headB * 0.52, M.chinY + 0.6 * M.headH, M.headZ]);
  addBP('head', [0, M.chinY - 0.005, M.headZ + M.headL * 0.3]);
  for (const s of [1, -1]) {
    const L = s > 0 ? 'L' : 'R';
    const sh = R[BI['upperArm' + L]], el = R[BI['forearm' + L]], wr = R[BI['hand' + L]];
    const a0 = M.armAbd0;
    const dir = [s * Math.sin(a0), -Math.cos(a0), 0];
    addBP('upperArm' + L, [sh.x + s * 0.055 * sc * M.girth, sh.y + 0.02 * sc, sh.z]);
    addBP('chest', [s * (M.shoulderX * 0.6), M.shoulderY + 0.05 * sc, -0.01 * sc]);
    addBP('forearm' + L, [el.x + s * 0.04 * sc, el.y, el.z]);
    addBP('forearm' + L, [el.x, el.y, el.z - 0.04 * sc]);
    addBP('hand' + L, [wr.x + dir[0] * M.handLen * 0.5, wr.y + dir[1] * M.handLen * 0.5, wr.z + 0.03 * sc]);
    addBP('hand' + L, [wr.x + dir[0] * M.handLen, wr.y + dir[1] * M.handLen, wr.z]);
    addBP('shin' + L, [s * M.hipX, M.kneeY, 0.055 * sc]);
    addBP('shin' + L, [s * (M.hipX + 0.05 * sc), M.kneeY, 0]);
    addBP('toe' + L, [s * M.hipX, 0.012, M.toeF + 0.01]);
    addBP('foot' + L, [s * M.hipX, 0.005, -M.heelBack * 1.05 - 0.005]);
    addBP('foot' + L, [s * (M.hipX + 0.05 * sc), 0.02, M.ballF * 0.6]);
    addBP('pelvis', [s * (T.dims(M.hipY).w + 0.01 * sc), M.hipY, 0]);
    addBP('chest', [s * (T.dims(M.chestY).w + 0.01), M.chestY, 0]);
  }
  addBP('spine', [0, M.waistY, T.dims(M.waistY).df + 0.02 * sc + look.belly * 0.03 * sc]);
  addBP('spine', [0, M.waistY, -T.dims(M.waistY).db - 0.01 * sc]);
  addBP('pelvis', [0, M.hipY - 0.03, -T.dims(M.hipY).db - 0.03 * sc]);
  if (look.outfit.skirtLen) {
    const yh = look.outfit.top === 'saree' ? 0.03 : look.outfit.skirtLen * M.H;
    const w = T.dims(M.hipY).w + 0.06 * sc;
    addBP('thighL', [w, yh, 0.0]); addBP('thighR', [-w, yh, 0.0]);
    addBP('thighL', [0.05, yh, 0.16 * sc]); addBP('thighR', [-0.05, yh, -0.16 * sc]);
  }
  if (look.hair === 'long' || look.hair === 'braid' || look.hair === 'pony') addBP('tail', [0, M.chestY - 0.05, -0.12 * sc]);
  if (look.outfit.top === 'saree' || look.outfit.dupatta) addBP('drape', [0.06 * sc, T.mapY(0.45), -0.15 * sc]);
  if (look.carry === 'bag') {
    if (look.bagStyle === 'backpack') { addBP('chest', [0.16 * sc, T.mapY(0.6), -0.3 * sc]); addBP('chest', [-0.16 * sc, T.mapY(0.6), -0.3 * sc]); }
    else { const s = look.carrySide === 'L' ? 1 : -1; addBP('bag', [s * (T.dims(M.hipY).w + 0.1 * sc), M.hipY - 0.06 * sc, 0]); }
  }
  for (const p of itemPts) addBP('hand' + look.carrySide, p);

  // --------------------------------------------------- Human
  const tmp = new THREE.Vector3();
  let alpha = 1;
  const human = {
    object,
    mesh,
    contactShadow: contact,
    height: M.H,
    strideLength: gait.S,
    look,
    seed,
    setPose(phase, speed, turnRate, t) {
      const pose = gait.pose(phase, speed, turnRate, t, carry);
      applyPose(bones, pose);
      updateContact(pose);
    },
    boxPoints(out) {
      const n = bp.length;
      for (let i = 0; i < n; i++) {
        if (!out[i]) out[i] = new THREE.Vector3();
        out[i].copy(bp[i].local).applyMatrix4(bones[bp[i].bi].matrixWorld);
      }
      out.length = n;
      return out;
    },
    setAlpha(a) {
      alpha = clamp(a, 0, 1);
      mat.opacity = alpha;
      cmat.opacity = alpha;
      object.visible = alpha > 0.002;
    },
    dispose() {
      object.removeFromParent();
      for (const d of disposables) d.dispose();
      skeleton.dispose();
    },
    _gait: gait, _bones: bones, _M: M, _R: R,
  };
  const footLen = M.footLen;
  function quad(i, cx, cz, ux, uz, hw, hl, a) {
    // centre (cx, cz), forward dir (ux, uz), half width hw, half length hl
    const vx = -uz, vz = ux;
    const P = [[-hw, -hl], [hw, -hl], [hw, hl], [-hw, hl]];
    for (let k = 0; k < 4; k++) {
      const j = i * 4 + k;
      cpos[j * 3] = cx + vx * P[k][0] + ux * P[k][1];
      cpos[j * 3 + 1] = 0.004;
      cpos[j * 3 + 2] = cz + vz * P[k][0] + uz * P[k][1];
      ccol[j * 4] = 1; ccol[j * 4 + 1] = 1; ccol[j * 4 + 2] = 1; ccol[j * 4 + 3] = a;
    }
  }
  function updateContact(pose) {
    for (let s = 0; s < 2; s++) {
      const A = pose.ankle[s];
      const yaw = pose.footYaw[s];
      const lift = clamp((A.y - M.ankleY) / 0.12, 0, 1);
      const ux = Math.sin(yaw), uz = Math.cos(yaw);
      const off = footLen * 0.3 - M.heelBack;
      quad(s, A.x + ux * off, A.z + uz * off, ux, uz, 0.075 * sc * (1 + lift * 0.6), footLen * 0.62 * (1 + lift * 0.3), 0.62 * (1 - lift * 0.75));
    }
    const p = pose.pelvisPos;
    quad(2, p.x * 0.6 + (pose.ankle[0].x + pose.ankle[1].x) * 0.2, (pose.ankle[0].z + pose.ankle[1].z) * 0.35 + p.z * 0.3, 0, 1, (look.outfit.skirtLen && look.outfit.top === 'saree' ? 0.3 : 0.26) * sc * M.girth, 0.3 * sc, 0.4);
    cg.attributes.position.needsUpdate = true;
    cg.attributes.color.needsUpdate = true;
  }
  human.setPose(0, 0, 0);
  return human;
}

function applyPose(bones, pose) {
  for (let i = 1; i < bones.length; i++) bones[i].quaternion.copy(pose.local[i]);
  bones[BI.pelvis].position.copy(pose.pelvisPos);
}

// exposed for tests
export const _internal = { measure, sampleLook, BONES, BI };
