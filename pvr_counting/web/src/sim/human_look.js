// Appearance of a procedural person: body measurements, skin, hair and an outfit
// sampled from a seed, plus the painter that turns them into the person's texture
// atlas (CanvasTexture) and roughness map. Everything is deterministic in the seed.
import { mulberry32 } from './rng.js';
import { clamp, lerp } from './human_geo.js';

export const ATLAS = 512;
// Atlas regions in pixels [x0, y0, x1, y1] (canvas space, y down)
export const REG = {
  torso: [0, 0, 512, 168],
  skirt: [0, 168, 512, 264],
  legs: [0, 264, 256, 408],
  arms: [256, 264, 384, 408],
  head: [384, 264, 512, 392],
  hair: [384, 392, 512, 456],
  shoes: [0, 408, 128, 472],
  hands: [128, 408, 192, 472],
  drape: [192, 408, 384, 472],
  items: [384, 456, 512, 512],
  sw: [0, 472, 384, 512],
};
export function rectUV(name) {
  const r = REG[name];
  const p = 0.75;
  return [(r[0] + p) / ATLAS, (r[1] + p) / ATLAS, (r[2] - p) / ATLAS, (r[3] - p) / ATLAS];
}
// Item sub-rects inside REG.items (128 x 56): tub sides, cup side, bag, phone
export const ITEM_REG = {
  tub: [384, 456, 448, 512],
  cup: [448, 456, 480, 512],
  bag: [480, 456, 512, 484],
  phone: [480, 484, 512, 512],
};
export function itemUV(name) {
  const r = ITEM_REG[name];
  const p = 1;
  return [(r[0] + p) / ATLAS, (r[1] + p) / ATLAS, (r[2] - p) / ATLAS, (r[3] - p) / ATLAS];
}

const SW_CELL = 16;
const SW_COLS = 24;
export const SWATCH = [
  'skin', 'skinShade', 'hair', 'sole', 'shoe', 'shoe2', 'strap', 'bag', 'bagDark', 'metal',
  'popcorn', 'tubRim', 'lid', 'straw', 'phone', 'screen', 'top', 'top2', 'bottom', 'drape',
  'collar', 'cuff', 'lip', 'nail', 'white', 'black', 'cupLiquid', 'hairTie', 'glass', 'bindi',
  'sock', 'skirt', 'skirtBorder', 'belt', 'buckle', 'phoneCase', 'earring', 'watch',
];
export function swatchUV(name) {
  const i = SWATCH.indexOf(name);
  const cx = (i % SW_COLS) * SW_CELL + SW_CELL / 2 + REG.sw[0];
  const cy = Math.floor(i / SW_COLS) * SW_CELL + SW_CELL / 2 + REG.sw[1];
  return [cx / ATLAS, cy / ATLAS];
}

// ---------------------------------------------------------------- colour utils
function hex(h) { return [parseInt(h.slice(1, 3), 16), parseInt(h.slice(3, 5), 16), parseInt(h.slice(5, 7), 16)]; }
function rgb(c, a) { return a === undefined ? `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})` : `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${a})`; }
function mix(a, b, t) { return [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)]; }
function mul(a, k) { return [clamp(a[0] * k, 0, 255), clamp(a[1] * k, 0, 255), clamp(a[2] * k, 0, 255)]; }
function jitter(c, rng, amt) {
  const k = 1 + (rng() - 0.5) * amt;
  return [clamp(c[0] * k * (1 + (rng() - 0.5) * amt * 0.4), 0, 255), clamp(c[1] * k, 0, 255), clamp(c[2] * k * (1 + (rng() - 0.5) * amt * 0.4), 0, 255)];
}

// ---------------------------------------------------------------- palettes
const P = {
  tee: ['#1c1c1e', '#2c2d31', '#1f2a44', '#e6e3dc', '#8b8c8e', '#4a5033', '#5a2028', '#b48a32', '#22585c', '#203b2f', '#c4b496', '#7a9cc0', '#9e2c2c', '#2b4c9c', '#c98199', '#3b3f52', '#6b4a3a', '#d8d2c2'],
  shirt: ['#e9e7e2', '#a7bfd9', '#dcb6b4', '#a3a6aa', '#3f5f86', '#d9d3c4', '#1d1e22', '#7d93a8', '#5f7f6a', '#c9c2e0'],
  check: [['#1f2c4a', '#d8d6d0', '#8a2e2e'], ['#7a1f24', '#1a1a1a', '#c9c0b0'], ['#2f4f73', '#9cb7d1', '#ffffff'], ['#355e3b', '#1d2b45', '#c8c49b'], ['#5b6670', '#d1d4d6', '#2a2f35'], ['#8a5a2b', '#2b241f', '#d9c7a5']],
  jeans: ['#1d2840', '#26375a', '#3b5579', '#5f7da3', '#1c1d21', '#3f4246', '#2a3b5e'],
  chino: ['#a8936c', '#c0ab88', '#53583e', '#262e44', '#1e1f22', '#56585c', '#7d6a55', '#3e3a36'],
  kurtaM: ['#ece8df', '#e1d4ba', '#a9c0d8', '#6a2330', '#be8b2f', '#1f2b48', '#171719', '#a6bf9f', '#d9cfc0', '#7b5c8a'],
  kurtaF: ['#a8305f', '#1e7a78', '#d0a033', '#e1a78a', '#9ccdb5', '#2d48a0', '#6e2232', '#151517', '#e48cad', '#d46a2c', '#6a3d8c', '#efe7d7', '#355c3a', '#c74343', '#6f8fb8'],
  saree: [['#9e1c2b', '#d4a640'], ['#1f6a45', '#d6ac4a'], ['#22448c', '#c9c9cf'], ['#c4467a', '#e2b75a'], ['#d06a1e', '#7a1424'], ['#5d2a7a', '#d8b04f'], ['#ede5d0', '#a51f2b'], ['#1b6f72', '#e0b850'], ['#7a1630', '#e3c069'], ['#2a2a2e', '#c99a3a'], ['#e3a8b5', '#8a2c4c']],
  legging: ['#efeae0', '#151517', '#d8cdb5', '#3a2d4a', '#8a1f33', '#1f3557'],
  hoodie: ['#8e8f92', '#1d1e21', '#22304d', '#5c1f2a', '#4b5136', '#6c6f75', '#b9b2a4', '#2e4a5e'],
  jacket: ['#3d5778', '#25262a', '#4a3a2c', '#5a5d48', '#2c3346'],
  top: ['#e9e3d6', '#141416', '#b13a52', '#e7c5c5', '#4b6fa8', '#d9b84a', '#7c9b7f', '#9a4a3c', '#c7c9d9', '#2e2e3e', '#d77a5c', '#f0d9e0'],
  sneaker: [['#e9e8e4', '#d9d8d2'], ['#1e1e20', '#e2e0da'], ['#8c8d90', '#e6e4de'], ['#1f2b44', '#e6e4de'], ['#c8c3b6', '#9c9688'], ['#e9e8e4', '#a83232']],
  formal: [['#2a1c15', '#1a1412'], ['#141414', '#0e0e0e'], ['#5a3a24', '#2d1f17']],
  sandal: [['#4a2f1e', '#2e2016'], ['#1b1b1b', '#2a2a2a'], ['#8a6038', '#5a3e25'], ['#b8915a', '#7d6040'], ['#3a3330', '#5a4e44']],
  flat: [['#c9a35a', '#7d6040'], ['#1b1b1b', '#2a2a2a'], ['#8a3a3a', '#3a2a22'], ['#d9c3a5', '#9a8466'], ['#5a4030', '#2e2016']],
  tub: [['#c4232b', '#f2efe8'], ['#1f3f8f', '#f2efe8'], ['#e2b021', '#b3202a'], ['#202024', '#d6a63a']],
  cup: [['#f1efe9', '#c4232b'], ['#f1efe9', '#1f4fa0'], ['#d42a2e', '#f1efe9'], ['#1a1a1c', '#d6a63a']],
  bag: ['#2a1d17', '#141416', '#6b4429', '#8a6a4a', '#5a1f25', '#c8b49a', '#2b3247', '#4a4a4d'],
};
const pk = (rng, arr) => arr[Math.floor(rng() * arr.length) % arr.length];

// South-Asian skin tones (sRGB albedo), light wheatish -> deep brown
const SKIN = [[0, '#c99d80'], [0.35, '#b08166'], [0.65, '#8f664d'], [1, '#62453a']];
function skinTone(t, warm) {
  let i = 0;
  while (i < SKIN.length - 2 && t > SKIN[i + 1][0]) i++;
  const a = SKIN[i], b = SKIN[i + 1];
  const c = mix(hex(a[1]), hex(b[1]), (t - a[0]) / (b[0] - a[0]));
  return [c[0] * (1 + warm * 0.04), c[1], c[2] * (1 - warm * 0.06)];
}

// ---------------------------------------------------------------- look sampling
export function sampleLook(seed, opts = {}) {
  const rng = mulberry32((seed * 2654435761) ^ 0x5bd1e995);
  const r = () => rng();
  const nrm = () => (r() + r() + r() - 1.5) * 1.15; // ~N(0, 0.58)
  const kind = opts.kind === 'child' ? 'child' : 'adult';
  const sex = opts.sex === 'm' || opts.sex === 'f' ? opts.sex : (r() < 0.5 ? 'm' : 'f');
  const child = kind === 'child';
  const age = child ? 4 + r() * 8 : 18 + Math.pow(r(), 2) * 47;
  let H;
  if (child) H = 1.02 + (age - 4) * 0.058 + nrm() * 0.06;
  else H = (sex === 'm' ? 1.69 : 1.555) + nrm() * (sex === 'm' ? 0.105 : 0.085);
  H = clamp(H, child ? 0.95 : 1.45, child ? 1.5 : 1.9);
  const ageMass = child ? 0 : clamp((age - 25) / 40, 0, 1) * 0.35;
  const mass = clamp(nrm() * 0.9 + ageMass + (child ? -0.1 : 0.05), -0.9, 1.1); // -1 slim .. +1 heavy
  const look = {
    seed, kind, sex, age, H, child,
    mass,
    shoulder: 1 + nrm() * 0.06 + (sex === 'm' && !child ? mass * 0.03 : 0),
    hip: 1 + nrm() * 0.06 + (sex === 'f' ? 0.04 + mass * 0.05 : mass * 0.03),
    belly: clamp(mass * 0.9 + nrm() * 0.25 + ageMass * 0.6, 0, 1.2),
    bust: sex === 'f' && !child ? clamp(0.55 + nrm() * 0.35 + mass * 0.3, 0.15, 1.3) : 0,
    legRatio: 1 + nrm() * 0.03,
    headScale: 1 + nrm() * 0.04,
    rng: null,
  };
  // skin
  const st = clamp(0.45 + nrm() * 0.42, 0.02, 0.98);
  look.skin = jitter(skinTone(st, r() - 0.5), rng, 0.04);
  look.skinT = st;
  // hair
  const grey = !child && age > 45 ? clamp((age - 45) / 25 + nrm() * 0.25, 0, 1) : 0;
  const hennaed = !child && sex === 'f' && age > 40 && r() < 0.25;
  let hairC = mix(hex('#17120f'), hex('#33241b'), r() * (r() < 0.25 ? 1 : 0.45));
  if (hennaed) hairC = mix(hairC, hex('#5a2416'), 0.6);
  if (grey > 0) hairC = mix(hairC, hex('#8d8a86'), grey * 0.62);
  look.hairColor = hairC;
  look.grey = grey;
  if (sex === 'm') {
    if (child) look.hair = pk(rng, ['short', 'short', 'crop', 'medium']);
    else if (age > 42 && r() < 0.28) look.hair = 'receding';
    else look.hair = pk(rng, ['short', 'short', 'short', 'crop', 'medium', 'medium', 'quiff']);
    const b = r();
    look.beard = child ? 'none' : (b < 0.33 ? 'none' : b < 0.58 ? 'stubble' : b < 0.75 ? 'moustache' : 'full');
  } else {
    if (child) look.hair = pk(rng, ['pony', 'twoBraids', 'bob', 'pony', 'braid']);
    else look.hair = pk(rng, ['long', 'long', 'braid', 'braid', 'bun', 'bun', 'pony', 'pony', 'bob']);
    look.beard = 'none';
    look.parting = r() < 0.75 ? 'center' : 'side';
    look.sindoor = !child && age > 24 && r() < 0.35;
    look.bindi = !child && r() < 0.45;
  }
  look.hairLen = look.hair === 'long' ? lerp(0.3, 0.55, r()) : look.hair === 'braid' ? lerp(0.35, 0.6, r()) : 0;
  look.hairVol = 0.8 + r() * 0.5;
  look.glasses = !child && r() < (age > 40 ? 0.45 : 0.2);
  look.glassesColor = pk(rng, [[20, 20, 22], [40, 30, 25], [70, 70, 75], [25, 25, 30]]);

  // --------------------------------------------------------------- outfit
  const o = {};
  look.outfit = o;
  const Ht = (x) => x; // fractions of H used directly by the geometry
  if (child) {
    if (sex === 'm') {
      o.top = r() < 0.8 ? 'tee' : 'shirt';
      o.bottom = r() < 0.55 ? 'shorts' : 'jeans';
      o.shoes = r() < 0.8 ? 'sneaker' : 'sandal';
    } else {
      const k = r();
      if (k < 0.4) { o.top = 'frock'; o.bottom = r() < 0.5 ? 'leggings' : 'bare'; }
      else if (k < 0.7) { o.top = 'tee'; o.bottom = 'jeans'; }
      else { o.top = 'kurta'; o.bottom = 'leggings'; }
      o.shoes = r() < 0.6 ? 'sneaker' : 'flat';
    }
  } else if (sex === 'm') {
    const k = r();
    o.top = k < 0.3 ? 'tee' : k < 0.53 ? 'shirt' : k < 0.63 ? 'polo' : k < 0.75 ? 'hoodie' : k < 0.88 ? 'kurta' : 'jacket';
    if (o.top === 'kurta') o.bottom = r() < 0.55 ? 'jeans' : (r() < 0.5 ? 'churidar' : 'pyjama');
    else o.bottom = r() < 0.58 ? 'jeans' : 'chinos';
    const s = r();
    if (o.top === 'kurta') o.shoes = s < 0.6 ? 'sandal' : 'formal';
    else o.shoes = s < 0.52 ? 'sneaker' : s < 0.72 ? 'formal' : 'sandal';
  } else {
    const k = r();
    if (k < 0.2) { o.top = 'saree'; o.bottom = 'saree'; }
    else if (k < 0.5) { o.top = 'kameez'; o.bottom = r() < 0.5 ? 'salwar' : 'churidar'; o.dupatta = r() < 0.8; }
    else if (k < 0.68) { o.top = 'kurti'; o.bottom = r() < 0.55 ? 'jeans' : 'leggings'; o.dupatta = r() < 0.25; }
    else if (k < 0.9) { o.top = r() < 0.5 ? 'top' : 'tee'; o.bottom = 'jeans'; }
    else { o.top = 'hoodie'; o.bottom = 'jeans'; }
    const s = r();
    o.shoes = (o.top === 'saree' || o.top === 'kameez') ? (s < 0.75 ? 'flat' : 'sandal') : (s < 0.45 ? 'sneaker' : s < 0.8 ? 'flat' : 'sandal');
  }
  // colours and patterns
  const muted = 0.1 + r() * 0.22; // per-person garment desaturation (worn, dyed fabric)
  const C = (h) => { const c = jitter(hex(h), rng, 0.08); const l = c[0] * 0.3 + c[1] * 0.55 + c[2] * 0.15; return mix(c, [l, l, l], muted); };
  o.pattern = 'plain';
  switch (o.top) {
    case 'tee': o.topC = C(pk(rng, P.tee)); o.pattern = r() < 0.3 ? 'graphic' : r() < 0.2 ? 'stripes' : 'plain'; o.top2C = C(pk(rng, P.tee)); o.sleeve = child ? 0.32 : 0.3 + r() * 0.08; break;
    case 'polo': o.topC = C(pk(rng, P.tee)); o.top2C = mul(o.topC, 0.8); o.sleeve = 0.3; break;
    case 'shirt': {
      if (r() < 0.45) { const ch = pk(rng, P.check); o.topC = C(ch[0]); o.top2C = C(ch[1]); o.top3C = C(ch[2]); o.pattern = 'checks'; }
      else { o.topC = C(pk(rng, P.shirt)); o.top2C = mul(o.topC, 0.82); o.pattern = r() < 0.3 ? 'pinstripe' : 'plain'; }
      o.sleeve = r() < 0.4 ? 0.32 : r() < 0.5 ? 1.0 : 0.62; // short, full, rolled
      o.tucked = !child && r() < 0.35;
      break;
    }
    case 'hoodie': o.topC = C(pk(rng, P.hoodie)); o.top2C = mul(o.topC, 0.85); o.sleeve = 1.0; o.pattern = r() < 0.3 ? 'graphic' : 'plain'; o.melange = r() < 0.5; break;
    case 'jacket': o.topC = C(pk(rng, P.jacket)); o.top2C = C(pk(rng, P.tee)); o.sleeve = 1.0; break;
    case 'kurta': {
      o.topC = C(child && sex === 'f' ? pk(rng, P.kurtaF) : (sex === 'm' ? pk(rng, P.kurtaM) : pk(rng, P.kurtaF)));
      o.top2C = sex === 'm' ? mul(o.topC, 0.85) : C(pk(rng, P.kurtaF));
      o.pattern = sex === 'f' ? (r() < 0.7 ? 'print' : 'plain') : (r() < 0.25 ? 'chikan' : 'plain');
      o.sleeve = sex === 'm' ? (r() < 0.7 ? 1.0 : 0.62) : 0.75;
      o.skirtLen = sex === 'm' ? 0.33 : 0.36; // hem height as fraction of H
      break;
    }
    case 'kameez': case 'kurti': {
      o.topC = C(pk(rng, P.kurtaF)); o.top2C = mix(C(pk(rng, P.kurtaF)), o.topC, 0.25); o.top3C = mix(C(pk(rng, P.kurtaF)), [235, 225, 205], 0.3);
      o.pattern = r() < 0.75 ? 'print' : 'plain';
      o.sleeve = r() < 0.6 ? 0.72 : r() < 0.5 ? 1.0 : 0.4;
      o.skirtLen = o.top === 'kameez' ? lerp(0.27, 0.33, r()) : lerp(0.36, 0.42, r());
      break;
    }
    case 'top': o.topC = C(pk(rng, P.top)); o.top2C = C(pk(rng, P.top)); o.pattern = r() < 0.4 ? 'print' : r() < 0.2 ? 'stripes' : 'plain'; o.sleeve = r() < 0.5 ? 0.25 : r() < 0.5 ? 0.62 : 1.0; break;
    case 'frock': o.topC = C(pk(rng, P.kurtaF)); o.top2C = C(pk(rng, P.top)); o.pattern = r() < 0.6 ? 'print' : 'plain'; o.sleeve = 0.2; o.skirtLen = 0.3; break;
    case 'saree': {
      const s = pk(rng, P.saree);
      o.topC = C(s[0]); o.borderC = C(s[1]);
      o.blouseC = r() < 0.6 ? mul(o.topC, 0.8 + r() * 0.3) : C(s[1]);
      o.top2C = o.borderC;
      o.sleeve = 0.24;
      o.skirtLen = 0.02;
      o.pattern = r() < 0.5 ? 'buti' : 'plain';
      break;
    }
  }
  switch (o.bottom) {
    case 'jeans': o.bottomC = C(pk(rng, P.jeans)); break;
    case 'chinos': o.bottomC = C(pk(rng, P.chino)); break;
    case 'shorts': o.bottomC = C(pk(rng, ['#2a3b5e', '#6b6a5a', '#1d1e22', '#7a8a9a', '#5a4632'])); break;
    case 'churidar': case 'leggings': o.bottomC = r() < 0.5 ? C(pk(rng, P.legging)) : mul(o.top2C || o.topC, 0.95); break;
    case 'salwar': o.bottomC = r() < 0.5 ? mul(o.topC, 0.95) : C(pk(rng, P.kurtaF)); break;
    case 'pyjama': o.bottomC = C(pk(rng, ['#efebe2', '#e3dac8', '#d9d4ca'])); break;
    case 'saree': o.bottomC = o.topC; break;
    case 'bare': o.bottomC = look.skin; break;
  }
  if (o.dupatta) {
    o.drapeC = r() < 0.5 ? (o.top2C || o.topC) : C(pk(rng, P.kurtaF));
    o.drapeBorderC = r() < 0.6 ? C(pk(rng, ['#d6ac4a', '#e9e3d6', '#c9c9cf', '#9e1c2b'])) : o.drapeC;
    o.dupattaStyle = r() < 0.4 ? 'both' : 'one';
  }
  if (o.top === 'saree') { o.drapeC = o.topC; o.drapeBorderC = o.borderC; }
  // shoes
  if (o.shoes === 'sneaker') { const s = pk(rng, P.sneaker); o.shoeC = C(s[0]); o.soleC = C(s[1]); }
  else if (o.shoes === 'formal') { const s = pk(rng, P.formal); o.shoeC = C(s[0]); o.soleC = C(s[1]); }
  else if (o.shoes === 'sandal') { const s = pk(rng, P.sandal); o.shoeC = C(s[0]); o.soleC = C(s[1]); }
  else { const s = pk(rng, P.flat); o.shoeC = C(s[0]); o.soleC = C(s[1]); }
  // keep albedos physical: bright whites and pale shoes otherwise glow under the downlights
  const cap = (c, m) => { if (!c) return c; const mx = Math.max(c[0], c[1], c[2]); return mx > m ? mul(c, m / mx) : c; };
  for (const k of ['topC', 'top2C', 'top3C', 'bottomC', 'drapeC', 'drapeBorderC', 'blouseC', 'borderC']) o[k] = cap(o[k], 195);
  o.shoeC = cap(o.shoeC, 165); o.soleC = cap(o.soleC, 165);
  // tops that cover the hips (untucked)
  o.hemH = o.tucked ? null : (o.top === 'hoodie' ? 0.505 : o.top === 'jacket' ? 0.51 : o.top === 'top' ? 0.55 : 0.515);

  // carry
  const carry = opts.carry === undefined ? (r() < 0.3 ? pk(rng, ['popcorn', 'cup', 'phone', 'bag']) : null) : opts.carry;
  look.carry = carry;
  look.carrySide = r() < 0.7 ? 'R' : 'L';
  look.bagStyle = carry === 'bag' ? (sex === 'f' && !child ? (r() < 0.7 ? 'shoulder' : 'sling') : (r() < 0.55 ? 'backpack' : 'sling')) : null;
  look.bagC = C(pk(rng, P.bag));
  look.tubC = pk(rng, P.tub).map(hex);
  look.cupC = pk(rng, P.cup).map(hex);
  look.cupClear = r() < 0.3;
  look.phoneC = C(pk(rng, ['#1a1a1c', '#2a2c33', '#c9c4bd', '#3a5070', '#7a2a35']));
  look.holdStrap = r() < 0.5;
  // gait personality
  look.gait = {
    armSwing: 0.85 + r() * 0.35,
    lean: (r() - 0.3) * 0.05,
    bob: 0.9 + r() * 0.25,
    toeOut: 0.06 + r() * 0.1,
    lookDown: carry === 'phone' ? 0.42 + r() * 0.12 : r() * 0.1,
    sway: (sex === 'f' ? 1.15 : 0.95) + r() * 0.2,
    idleLeg: r() < 0.5 ? 1 : -1,
    noiseSeed: (seed * 31 + 7) | 0,
    slouch: clamp(nrm() * 0.6 + (child ? -0.2 : 0.2) + Math.max(0, age - 45) / 40, -0.4, 1),
    droop: (r() - 0.5) * 0.06,
  };
  look.wrist = r() < 0.4 ? (sex === 'f' ? 'bangles' : 'watch') : null;
  return look;
}

// ---------------------------------------------------------------- shared noise tiles
let TILES = null;
function makeCanvas(w, h) {
  if (typeof document !== 'undefined') { const c = document.createElement('canvas'); c.width = w; c.height = h; return c; }
  if (typeof OffscreenCanvas !== 'undefined') return new OffscreenCanvas(w, h);
  return null;
}
export function canPaint() { return typeof document !== 'undefined' || typeof OffscreenCanvas !== 'undefined'; }
function tileFrom(w, h, fn) {
  const c = makeCanvas(w, h);
  const g = c.getContext('2d');
  const im = g.createImageData(w, h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const [R, G, B, A] = fn(x, y);
    const i = (y * w + x) * 4;
    im.data[i] = R; im.data[i + 1] = G; im.data[i + 2] = B; im.data[i + 3] = A === undefined ? 255 : A;
  }
  g.putImageData(im, 0, 0);
  return c;
}
function tiles() {
  if (TILES) return TILES;
  const rng = mulberry32(911);
  const N = 64;
  const val = new Float32Array(N * N);
  for (let i = 0; i < N * N; i++) val[i] = rng();
  const sm = (x, y) => {
    let s = 0;
    for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) s += val[((y + dy + N) % N) * N + ((x + dx + N) % N)];
    return s / 9;
  };
  TILES = {
    weave: tileFrom(N, N, (x, y) => {
      const v = 228 + (val[y * N + x] - 0.5) * 40 + ((x + y) % 2 ? 6 : -6) + (sm(x, y) - 0.5) * 30;
      return [v, v, v];
    }),
    denim: tileFrom(N, N, (x, y) => {
      const tw = ((x + y * 2) % 4 < 2) ? 14 : -14;
      const v = 222 + tw + (val[y * N + x] - 0.5) * 36 + (val[((y * 7) % N) * N + ((x * 3) % N)] - 0.5) * 20;
      return [v, v, v];
    }),
    knit: tileFrom(N, N, (x, y) => {
      const v = 232 + (Math.sin(x * Math.PI) * 0 + ((y % 3) === 0 ? -10 : 4)) + (val[y * N + x] - 0.5) * 30;
      return [v, v, v];
    }),
    speck: tileFrom(N, N, (x, y) => {
      const a = val[y * N + x];
      return a > 0.82 ? [255, 255, 255, 70] : a < 0.15 ? [0, 0, 0, 60] : [0, 0, 0, 0];
    }),
    skin: tileFrom(N, N, (x, y) => {
      const v = 240 + (sm(x, y) - 0.5) * 30 + (val[y * N + x] - 0.5) * 10;
      return [v, v * 0.995, v * 0.99];
    }),
    hair: (() => {
      const W = 256, Hh = 64;
      const cols = new Float32Array(W);
      for (let i = 0; i < W; i++) cols[i] = rng();
      const sm = new Float32Array(W);
      for (let i = 0; i < W; i++) sm[i] = (cols[i] * 2 + cols[(i + 1) % W] + cols[(i + W - 1) % W]) / 4;
      return tileFrom(W, Hh, (x, y) => {
        const s = sm[x] * 0.7 + cols[x] * 0.3;
        const v = 214 + (s - 0.5) * 52 + Math.sin(y * 0.2 + cols[(x * 7) % W] * 6) * 6;
        return [v, v, v];
      });
    })(),
    greyStrands: (() => {
      const W = 128, Hh = 64;
      const cols = new Float32Array(W);
      for (let i = 0; i < W; i++) cols[i] = rng();
      return tileFrom(W, Hh, (x, y) => {
        const a = cols[x] > 0.55 ? (cols[x] - 0.55) * 2.2 : 0;
        return [215, 212, 208, Math.round(a * 150 * (0.7 + 0.3 * Math.sin(y * 0.3 + x)))];
      });
    })(),
  };
  return TILES;
}

// ---------------------------------------------------------------- painter
// Paints the atlas for a look. `geo` holds the body measurements the painter needs
// to place things by height: { H, torsoTop, torsoBot, waistY, hipY, chestY, legTop, legBot,
// armLen, sleeve, hemSkirtTop, skirtBot }
export function paintAtlas(look, geo) {
  if (!canPaint()) return null;
  const T = tiles();
  const rng = mulberry32(look.seed * 7 + 3);
  const r = () => rng();
  const cv = makeCanvas(ATLAS, ATLAS);
  const g = cv.getContext('2d');
  const rc = makeCanvas(ATLAS / 4, ATLAS / 4); // roughness
  const gr = rc.getContext('2d');
  const o = look.outfit;
  g.fillStyle = '#808080'; g.fillRect(0, 0, ATLAS, ATLAS);
  gr.fillStyle = 'rgb(230,230,230)'; gr.fillRect(0, 0, ATLAS / 4, ATLAS / 4);
  const rough = (reg, v, x0, y0, x1, y1) => {
    const R = REG[reg];
    const X0 = x0 === undefined ? R[0] : x0, Y0 = y0 === undefined ? R[1] : y0;
    const X1 = x1 === undefined ? R[2] : x1, Y1 = y1 === undefined ? R[3] : y1;
    gr.fillStyle = `rgb(${v * 255 | 0},${v * 255 | 0},${v * 255 | 0})`;
    gr.fillRect(X0 / 4, Y0 / 4, (X1 - X0) / 4, (Y1 - Y0) / 4);
  };
  const clipRect = (R) => { g.save(); g.beginPath(); g.rect(R[0], R[1], R[2] - R[0], R[3] - R[1]); g.clip(); };
  const fill = (c, x, y, w, h, a) => { g.fillStyle = rgb(c, a); g.fillRect(x, y, w, h); };
  const tex = (tile, x, y, w, h, mode = 'multiply', alpha = 1) => {
    g.save();
    g.globalCompositeOperation = mode;
    g.globalAlpha = alpha;
    g.fillStyle = g.createPattern(tile, 'repeat');
    g.fillRect(x, y, w, h);
    g.restore();
  };
  const skin = look.skin;
  const skinSh = mul(skin, 0.82);
  const H = look.H;

  // ---- swatches
  const sw = (name, c) => {
    const i = SWATCH.indexOf(name);
    const x = (i % SW_COLS) * SW_CELL + REG.sw[0], y = Math.floor(i / SW_COLS) * SW_CELL + REG.sw[1];
    fill(c, x, y, SW_CELL, SW_CELL);
  };
  sw('skin', skin); sw('skinShade', skinSh); sw('hair', look.hairColor);
  sw('sole', o.soleC); sw('shoe', o.shoeC); sw('shoe2', mul(o.shoeC, 0.8));
  sw('strap', mul(look.bagC, 0.8)); sw('bag', look.bagC); sw('bagDark', mul(look.bagC, 0.6));
  sw('metal', [176, 160, 120]); sw('popcorn', [236, 214, 160]); sw('tubRim', look.tubC[1]);
  sw('lid', look.cupClear ? [215, 215, 210] : look.cupC[0]); sw('straw', mix(look.cupC[1], [255, 255, 255], 0.2));
  sw('phone', look.phoneC); sw('screen', [40, 60, 90]);
  sw('top', o.topC); sw('top2', o.top2C || o.topC); sw('bottom', o.bottomC);
  sw('drape', o.drapeC || o.topC); sw('collar', o.top === 'polo' ? o.topC : (o.top2C && o.pattern === 'checks' ? o.topC : o.topC));
  sw('cuff', mul(o.topC, 0.9)); sw('lip', mix(skin, [110, 40, 45], 0.45)); sw('nail', mix(skin, [255, 230, 220], 0.35));
  sw('white', [235, 233, 228]); sw('black', [18, 18, 20]); sw('cupLiquid', [50, 22, 14]);
  sw('hairTie', look.sex === 'f' ? [120, 30, 50] : [20, 20, 20]); sw('glass', look.glassesColor); sw('bindi', [140, 20, 30]);
  sw('sock', o.shoes === 'sneaker' ? [225, 223, 218] : [30, 30, 32]);
  sw('skirt', o.topC); sw('skirtBorder', o.borderC || o.top2C || o.topC);
  sw('belt', [36, 26, 20]); sw('buckle', [150, 140, 120]); sw('phoneCase', look.phoneC);
  sw('earring', [200, 170, 90]); sw('watch', [40, 40, 44]);
  rough('sw', 0.85);

  // ---- helpers to map torso heights to pixels
  const TR = REG.torso;
  const ty = (y) => TR[1] + (geo.torsoTop - y) / (geo.torsoTop - geo.torsoBot) * (TR[3] - TR[1]);
  const tu = (u) => TR[0] + u * (TR[2] - TR[0]); // u: 0 left side, .25 front, .5 right, .75 back
  const TW = TR[2] - TR[0];

  // ---------- pattern fillers
  const fabric = (x, y, w, h, base, opt = {}) => {
    fill(base, x, y, w, h);
    const pat = opt.pattern || 'plain';
    g.save();
    g.beginPath(); g.rect(x, y, w, h); g.clip();
    if (pat === 'checks') {
      const per = opt.per || 16;
      const c2 = opt.c2, c3 = opt.c3;
      for (let i = x - (x % per); i < x + w + per; i += per) { fill(c2, i, y, per * 0.45, h, 0.55); fill(c3, i + per * 0.62, y, 2, h, 0.6); }
      for (let j = y - (y % per); j < y + h + per; j += per) { fill(c2, x, j, w, per * 0.45, 0.45); fill(c3, x, j + per * 0.62, w, 2, 0.5); }
    } else if (pat === 'stripes') {
      const per = opt.per || 10;
      for (let j = y; j < y + h; j += per) fill(opt.c2, x, j, w, per * 0.4, 0.85);
    } else if (pat === 'pinstripe') {
      const per = opt.per || 6;
      for (let i = x; i < x + w; i += per) fill(opt.c2, i, y, 1, h, 0.5);
    } else if (pat === 'print') {
      // block-print style motifs: small flowers / paisleys / dots with jitter, 2-3 colours
      const per = opt.per || 15;
      const c2 = opt.c2, c3 = opt.c3 || opt.c2;
      const style = opt.printStyle || 0;
      const pr = mulberry32(opt.seed || 7);
      let row = 0;
      for (let j = y + 2; j < y + h + per; j += per * 0.86, row++) {
        for (let i = x + (row % 2 ? per / 2 : 0); i < x + w + per; i += per) {
          const jx = i + (pr() - 0.5) * per * 0.25, jy = j + (pr() - 0.5) * per * 0.25;
          const rot = pr() * Math.PI * 2;
          g.save(); g.translate(jx, jy); g.rotate(rot);
          if (style === 0) { // five-petal flower
            g.fillStyle = rgb(c2, 0.85);
            for (let q = 0; q < 5; q++) { const a = q * 1.2566; g.beginPath(); g.ellipse(Math.cos(a) * per * 0.16, Math.sin(a) * per * 0.16, per * 0.12, per * 0.07, a, 0, Math.PI * 2); g.fill(); }
            g.fillStyle = rgb(c3, 0.95); g.beginPath(); g.arc(0, 0, per * 0.07, 0, Math.PI * 2); g.fill();
          } else if (style === 1) { // paisley
            g.fillStyle = rgb(c2, 0.85);
            g.beginPath(); g.moveTo(0, -per * 0.3); g.bezierCurveTo(per * 0.3, -per * 0.15, per * 0.2, per * 0.3, 0, per * 0.18); g.bezierCurveTo(-per * 0.2, per * 0.1, -per * 0.1, -per * 0.1, 0, -per * 0.3); g.fill();
            g.fillStyle = rgb(c3, 0.9); g.beginPath(); g.arc(per * 0.04, per * 0.05, per * 0.06, 0, Math.PI * 2); g.fill();
          } else { // leafy sprig
            g.strokeStyle = rgb(c2, 0.85); g.lineWidth = 1.2; g.beginPath(); g.moveTo(-per * 0.25, 0); g.quadraticCurveTo(0, -per * 0.12, per * 0.25, 0); g.stroke();
            g.fillStyle = rgb(c3, 0.85); for (let q = -1; q <= 1; q++) { g.beginPath(); g.ellipse(q * per * 0.13, -per * 0.07, per * 0.07, per * 0.035, 0.6 * q, 0, Math.PI * 2); g.fill(); }
          }
          g.restore();
        }
      }
    } else if (pat === 'buti') {
      const per = opt.per || 18;
      let row = 0;
      for (let j = y + 4; j < y + h; j += per * 0.8, row++) for (let i = x + (row % 2 ? per / 2 : 0); i < x + w + per; i += per) {
        g.fillStyle = rgb(opt.c2, 0.85); g.beginPath(); g.arc(i, j, 1.6, 0, Math.PI * 2); g.fill();
      }
    } else if (pat === 'chikan') {
      const per = opt.per || 12;
      for (let j = y + 4; j < y + h; j += per) for (let i = x + ((j / per) % 2 ? per / 2 : 0); i < x + w; i += per) {
        g.strokeStyle = rgb(mul(base, 0.88), 0.9); g.lineWidth = 1;
        g.beginPath(); g.arc(i, j, 2.5, 0, Math.PI * 2); g.stroke();
      }
    }
    g.restore();
    const tile = opt.tile || T.weave;
    tex(tile, x, y, w, h, 'multiply', opt.texAlpha === undefined ? 0.9 : opt.texAlpha);
    if (opt.melange) tex(T.speck, x, y, w, h, 'source-over', 1);
  };
  // soft fold strokes (wrinkles)
  const folds = (x, y, w, h, n, dir, strength = 0.12, len = 0.6) => {
    g.save(); g.beginPath(); g.rect(x, y, w, h); g.clip();
    for (let i = 0; i < n; i++) {
      const cx = x + r() * w, cy = y + r() * h;
      const L = (dir === 'h' ? w : h) * len * (0.3 + r() * 0.7) * 0.25;
      const dark = r() < 0.6;
      g.strokeStyle = dark ? `rgba(0,0,0,${strength * (0.5 + r() * 0.5)})` : `rgba(255,255,255,${strength * 0.5 * (0.5 + r() * 0.5)})`;
      g.lineWidth = 1 + r() * 2.5;
      g.lineCap = 'round';
      g.beginPath();
      if (dir === 'h') { g.moveTo(cx - L, cy + (r() - 0.5) * 4); g.quadraticCurveTo(cx, cy + (r() - 0.5) * 6, cx + L, cy + (r() - 0.5) * 4); }
      else { g.moveTo(cx + (r() - 0.5) * 4, cy - L); g.quadraticCurveTo(cx + (r() - 0.5) * 6, cy, cx + (r() - 0.5) * 4, cy + L); }
      g.stroke();
    }
    g.restore();
  };
  // large soft fold shading (blurred multiply strokes): diagonal pull lines from the armpits
  // to the waist, compression at the waist, vertical drape shadows on long skirts
  const clothFolds = (x, y, w, h, kind, isLong = false) => {
    g.save(); g.beginPath(); g.rect(x, y, w, h); g.clip();
    g.filter = 'blur(3px)';
    g.globalCompositeOperation = 'multiply';
    g.lineCap = 'round';
    const stroke = (pts, width, k) => { g.strokeStyle = `rgba(${255 * k | 0},${255 * k | 0},${255 * k | 0},1)`; g.lineWidth = width; g.beginPath(); g.moveTo(pts[0], pts[1]); g.quadraticCurveTo(pts[2], pts[3], pts[4], pts[5]); g.stroke(); };
    if (kind === 'torso') {
      const yA = ty(geo.chestY + 0.07), yW = ty(geo.waistY);
      for (const [u, s] of [[0.0, 1], [0.5, -1], [0.5, 1], [1.0, -1]]) {
        // from under the arm (side seam) diagonally toward the waist front / back
        for (let i = 0; i < 2; i++) {
          const x0 = tu(u) + s * (4 + i * 6), x1 = tu(u) + s * (34 + 16 * i + r() * 10);
          stroke([x0, yA + i * 6, (x0 + x1) / 2, (yA + yW) / 2, x1, yW + 6 + r() * 6], 5 + r() * 3, 0.8 + 0.06 * r());
        }
      }
      // horizontal compression at the waist
      for (let i = 0; i < 3; i++) { const yy = ty(geo.waistY + 0.01) + (r() - 0.5) * 10; const xx = x + r() * w; stroke([xx - 30, yy, xx, yy + (r() - 0.5) * 6, xx + 30, yy], 4, 0.84); }
      if (isLong) for (let i = 0; i < 5; i++) { const xx = x + r() * w; stroke([xx, ty(geo.waistY - 0.02), xx + (r() - 0.5) * 8, (ty(geo.waistY) + y + h) / 2, xx + (r() - 0.5) * 12, y + h], 6 + r() * 4, 0.82); }
    } else if (kind === 'skirt') {
      for (let i = 0; i < 5; i++) { const xx = x + (i + 0.3 + 0.4 * r()) * w / 5; stroke([xx, y, xx + (r() - 0.5) * 10, y + h * 0.5, xx + (r() - 0.5) * 18, y + h], 7 + r() * 5, 0.8); }
    } else if (kind === 'sleeve') {
      for (let i = 0; i < 3; i++) { const yy = y + h * (0.55 + 0.1 * i) ; stroke([x, yy, x + w * 0.5, yy + 3, x + w, yy], 3, 0.86); }
    } else if (kind === 'knee') {
      for (let i = 0; i < 3; i++) { const yy = y + h * 0.45 + i * 5; stroke([x + w * 0.62, yy, x + w * 0.75, yy + 2, x + w * 0.88, yy], 3, 0.84); }
    }
    g.restore();
  };
  const line = (x0, y0, x1, y1, c, a, w = 1) => { g.strokeStyle = rgb(c, a); g.lineWidth = w; g.beginPath(); g.moveTo(x0, y0); g.lineTo(x1, y1); g.stroke(); };
  const vgrad = (x, y, w, h, c0, a0, c1, a1) => {
    const gg = g.createLinearGradient(0, y, 0, y + h);
    gg.addColorStop(0, rgb(c0, a0)); gg.addColorStop(1, rgb(c1, a1));
    g.fillStyle = gg; g.fillRect(x, y, w, h);
  };
  const skinFill = (x, y, w, h) => { fill(skin, x, y, w, h); tex(T.skin, x, y, w, h, 'multiply', 1); };

  // ======================================================= TORSO
  const topOpt = { pattern: o.pattern, c2: o.top2C, c3: o.top3C || o.top2C, melange: o.melange, seed: look.seed, printStyle: Math.floor(r() * 3), per: o.pattern === 'checks' ? TW / Math.round(TW / (14 + r() * 8)) : o.pattern === 'print' ? 13 + r() * 8 : undefined };
  if (o.top === 'hoodie' || o.top === 'tee' || o.top === 'polo') topOpt.tile = T.knit;
  const waistY = geo.waistY, hipY = geo.hipY;
  const beltY = geo.beltY;
  const bottomTile = o.bottom === 'jeans' || o.bottom === 'shorts' ? T.denim : T.weave;
  // skin everywhere first (neckline, midriff)
  skinFill(TR[0], TR[1], TW, TR[3] - TR[1]);
  // lower garment on torso (from belt line down)
  if (o.bottom !== 'saree' && o.bottom !== 'bare') {
    const y0 = ty(beltY);
    fabric(TR[0], y0, TW, TR[3] - y0, o.bottomC, { tile: bottomTile });
    if (o.bottom === 'jeans' || o.bottom === 'chinos' || o.bottom === 'shorts') {
      // waistband
      fill(mul(o.bottomC, 0.85), TR[0], y0, TW, 7);
      line(TR[0], y0 + 7, TR[2], y0 + 7, mul(o.bottomC, 1.35), 0.5);
      // belt (if tucked or visible) - drawn later after the top
      // fly and pockets
      const fx = tu(0.25);
      const flyC = o.bottom === 'jeans' ? [190, 140, 80] : mul(o.bottomC, 0.75);
      line(fx, y0 + 7, fx, y0 + 34, mul(o.bottomC, 0.6), 0.8, 1.5);
      g.strokeStyle = rgb(flyC, 0.6); g.lineWidth = 1; g.beginPath(); g.moveTo(fx + 6, y0 + 7); g.lineTo(fx + 6, y0 + 28); g.quadraticCurveTo(fx + 6, y0 + 34, fx, y0 + 36); g.stroke();
      for (const s of [-1, 1]) {
        const px = tu(0.25 + s * 0.085);
        g.strokeStyle = rgb(mul(o.bottomC, 0.6), 0.85); g.lineWidth = 1.5;
        g.beginPath(); g.moveTo(px, y0 + 7); g.quadraticCurveTo(px + s * 4, y0 + 22, px + s * 22, y0 + 26); g.stroke();
        // back pockets
        const bx = tu(0.75 + s * 0.065), by = y0 + 18;
        g.fillStyle = rgb(mul(o.bottomC, 0.93));
        g.beginPath(); g.moveTo(bx - 13, by); g.lineTo(bx + 13, by); g.lineTo(bx + 12, by + 22); g.lineTo(bx, by + 27); g.lineTo(bx - 12, by + 22); g.closePath(); g.fill();
        g.strokeStyle = rgb(o.bottom === 'jeans' ? [180, 130, 75] : mul(o.bottomC, 0.65), 0.55); g.lineWidth = 1; g.stroke();
        if (o.bottom === 'jeans') { g.beginPath(); g.moveTo(bx - 7, by + 8); g.quadraticCurveTo(bx, by + 14, bx + 7, by + 8); g.stroke(); }
        // belt loops
        for (const lu of [0.1, 0.4, 0.68, 0.82]) { const lx = tu(s > 0 ? lu : 1 - lu); fill(mul(o.bottomC, 0.8), lx - 1.5, y0, 3, 9); }
      }
      // yoke at back
      if (o.bottom === 'jeans') { g.strokeStyle = rgb([180, 130, 75], 0.45); g.lineWidth = 1; g.beginPath(); g.moveTo(tu(0.6), y0 + 12); g.quadraticCurveTo(tu(0.75), y0 + 20, tu(0.9), y0 + 12); g.stroke(); }
      // crotch whiskers at the front bottom
      folds(tu(0.15), ty(geo.crotchY + 0.06), tu(0.35) - tu(0.15), 26, 9, 'h', 0.16, 0.9);
      // buttock shading
      for (const s of [-1, 1]) { const gg = g.createRadialGradient(tu(0.75 + s * 0.07), ty(hipY - 0.03), 2, tu(0.75 + s * 0.07), ty(hipY - 0.03), 34); gg.addColorStop(0, 'rgba(255,255,255,0.06)'); gg.addColorStop(1, 'rgba(255,255,255,0)'); g.fillStyle = gg; g.fillRect(tu(0.55), ty(hipY + 0.1), TW * 0.4, 60); }
    } else if (o.bottom === 'salwar' || o.bottom === 'pyjama' || o.bottom === 'churidar' || o.bottom === 'leggings') {
      folds(TR[0], y0, TW, TR[3] - y0, 30, 'v', 0.14, 0.8);
    }
  }
  // saree skirt part on torso (from navel-ish line down) - skirt geometry continues it
  if (o.top === 'saree') {
    const y0 = ty(geo.sareeWaistY);
    fabric(TR[0], y0, TW, TR[3] - y0, o.topC, { pattern: o.pattern, c2: o.borderC, tile: T.weave });
    // pleats tuck at front
    for (let i = -5; i <= 5; i++) line(tu(0.25) + i * 3.2, y0 + 2, tu(0.25) + i * 3.6, TR[3], mul(o.topC, i % 2 ? 0.7 : 1.2), 0.5, 1.2);
    // blouse
    const yb = ty(geo.blouseY);
    fabric(TR[0], TR[1], TW, yb - TR[1], o.blouseC, { tile: T.weave });
    fill(mul(o.blouseC, 0.8), TR[0], yb - 2, TW, 2);
    // midriff: skin between blouse and saree waist already
    // pallu band across the front: from right hip (u .45, waist) up to left shoulder (u .05, top)
    const pallu = (yy) => { // u-centre of the band at canvas y
      const t = (yy - TR[1]) / (y0 + 6 - TR[1]);
      return tu(lerp(0.07, 0.38, t));
    };
    g.save(); g.beginPath(); g.rect(TR[0], TR[1], TW, y0 + 8 - TR[1]); g.clip();
    const bw = 0.11 * TW;
    for (let yy = TR[1]; yy < y0 + 8; yy += 1) {
      const cx = pallu(yy);
      fill(o.topC, cx - bw / 2, yy, bw, 1.2);
      fill(o.borderC, cx - bw / 2, yy, 5, 1.2);
      fill(o.borderC, cx + bw / 2 - 3, yy, 3, 1.2);
    }
    // pleat folds of the pallu
    for (let k = 0; k < 6; k++) {
      g.strokeStyle = `rgba(0,0,0,${0.12 + r() * 0.1})`; g.lineWidth = 1.5;
      g.beginPath();
      for (let yy = TR[1]; yy < y0 + 6; yy += 4) { const cx = pallu(yy) - bw / 2 + 8 + k * (bw - 14) / 5; if (yy === TR[1]) g.moveTo(cx, yy); else g.lineTo(cx, yy); }
      g.stroke();
    }
    // also over the back of the left shoulder (u ~ .95-1 and 0-.05)
    fill(o.topC, tu(0.0), TR[1], 0.06 * TW, 22); fill(o.topC, tu(0.95), TR[1], 0.05 * TW, 22);
    tex(T.weave, TR[0], TR[1], TW, y0 - TR[1], 'multiply', 0.5);
    g.restore();
  } else if (o.top !== 'none') {
    // top garment from neckline to hem
    const hemY = geo.hemY !== undefined ? geo.hemY : (o.hemH ? o.hemH * H : beltY - 0.005);
    const isLong = o.top === 'kurta' || o.top === 'kameez' || o.top === 'kurti' || o.top === 'frock';
    const yh = isLong ? TR[3] : ty(o.tucked ? beltY + 0.01 : hemY);
    fabric(TR[0], TR[1], TW, yh - TR[1], o.topC, topOpt);
    // hem band
    if (!isLong) {
      if (o.top === 'hoodie') { fill(mul(o.topC, 0.85), TR[0], yh - 10, TW, 10); tex(T.knit, TR[0], yh - 10, TW, 10, 'multiply', 0.8); }
      // shadow under the hem onto the trousers (soft, no painted outline)
      vgrad(TR[0], yh, TW, 4, [0, 0, 0], 0.25, [0, 0, 0], 0);
    }
    // neckline / collars
    const nx = tu(0.25);
    if (o.top === 'tee' || o.top === 'top' || o.top === 'frock') {
      const deep = o.top === 'top' ? 16 : 8;
      g.fillStyle = rgb(skin); g.beginPath(); g.ellipse(nx, TR[1], 0.07 * TW, deep, 0, 0, Math.PI); g.fill();
      g.strokeStyle = rgb(mul(o.topC, 0.82)); g.lineWidth = 3; g.beginPath(); g.ellipse(nx, TR[1], 0.07 * TW + 1.5, deep + 1.5, 0, 0, Math.PI); g.stroke();
    } else if (o.top === 'shirt' || o.top === 'polo') {
      // placket, buttons, open top V
      g.fillStyle = rgb(skinSh); g.beginPath(); g.moveTo(nx - 10, TR[1]); g.lineTo(nx, TR[1] + 18); g.lineTo(nx + 10, TR[1]); g.fill();
      const pl = o.top === 'polo' ? 40 : yh - TR[1];
      line(nx - 3, TR[1] + 14, nx - 3, TR[1] + pl, mul(o.topC, 0.7), 0.7);
      line(nx + 3, TR[1] + 14, nx + 3, TR[1] + pl, mul(o.topC, 0.7), 0.5);
      for (let yy = TR[1] + 24; yy < TR[1] + pl - 4; yy += 17) { g.fillStyle = 'rgba(235,232,225,0.9)'; g.beginPath(); g.arc(nx, yy, 1.4, 0, Math.PI * 2); g.fill(); }
      if (o.top === 'shirt') { // chest pocket (left)
        const px = tu(0.25 + 0.075), py = ty(geo.chestY + 0.03);
        g.strokeStyle = rgb(mul(o.topC, 0.7), 0.6); g.lineWidth = 1; g.strokeRect(px - 9, py, 18, 20);
        // yoke seam at back
        line(TR[0], TR[1] + 18, TR[2], TR[1] + 18, mul(o.topC, 0.75), 0.25);
      }
    } else if (o.top === 'hoodie') {
      g.fillStyle = rgb(mul(o.topC, 0.6)); g.beginPath(); g.ellipse(nx, TR[1], 0.06 * TW, 10, 0, 0, Math.PI); g.fill();
      // drawstrings
      for (const s of [-1, 1]) line(nx + s * 9, TR[1] + 6, nx + s * 11, TR[1] + 46, [230, 228, 220], 0.9, 2);
      // kangaroo pocket
      const py = ty(geo.waistY + 0.02);
      g.fillStyle = rgb(mul(o.topC, 0.94)); g.strokeStyle = rgb(mul(o.topC, 0.65), 0.8); g.lineWidth = 1.2;
      g.beginPath(); g.moveTo(nx - 34, py + 34); g.lineTo(nx - 26, py); g.lineTo(nx + 26, py); g.lineTo(nx + 34, py + 34); g.closePath(); g.fill(); g.stroke();
    } else if (o.top === 'jacket') {
      // open jacket: inner tee strip at front
      const iw = 0.07 * TW;
      fabric(nx - iw / 2, TR[1], iw, yh - TR[1], o.top2C, { tile: T.knit });
      g.fillStyle = rgb(skin); g.beginPath(); g.ellipse(nx, TR[1], iw * 0.45, 8, 0, 0, Math.PI); g.fill();
      for (const s of [-1, 1]) { line(nx + s * iw / 2, TR[1], nx + s * iw / 2, yh, mul(o.topC, 0.55), 0.9, 2); line(nx + s * (iw / 2 + 2), TR[1], nx + s * (iw / 2 + 2), yh, [180, 170, 150], 0.35, 1); }
      // lapel shading
      for (const s of [-1, 1]) { g.fillStyle = rgb(mul(o.topC, 0.85)); g.beginPath(); g.moveTo(nx + s * iw / 2, TR[1]); g.lineTo(nx + s * (iw / 2 + 18), TR[1]); g.lineTo(nx + s * iw / 2, TR[1] + 50); g.fill(); }
      // pockets
      for (const s of [-1, 1]) line(tu(0.25 + s * 0.09) - 8, ty(geo.waistY - 0.04), tu(0.25 + s * 0.09) + 8, ty(geo.waistY - 0.04), mul(o.topC, 0.55), 0.8, 2);
    } else if (isLong) {
      // kurta placket with buttons / keyhole neckline
      g.fillStyle = rgb(skin); g.beginPath(); g.ellipse(nx, TR[1], 0.05 * TW, 8, 0, 0, Math.PI); g.fill();
      if (o.top === 'kurta' && look.sex === 'm') {
        fill(mul(o.topC, 0.92), nx - 4, TR[1] + 4, 8, 50);
        for (let yy = TR[1] + 12; yy < TR[1] + 52; yy += 12) { g.fillStyle = 'rgba(60,50,40,0.7)'; g.beginPath(); g.arc(nx, yy, 1.4, 0, Math.PI * 2); g.fill(); }
      } else {
        // yoke panel / neckline embroidery
        g.strokeStyle = rgb(o.top2C, 0.9); g.lineWidth = 2.5;
        g.beginPath(); g.moveTo(nx - 14, TR[1]); g.lineTo(nx, TR[1] + 30); g.lineTo(nx + 14, TR[1]); g.stroke();
        if (o.top !== 'frock') { g.lineWidth = 1.2; g.beginPath(); g.moveTo(nx - 20, TR[1]); g.lineTo(nx, TR[1] + 38); g.lineTo(nx + 20, TR[1]); g.stroke(); }
      }
      if (o.top === 'frock') { // waist seam + bow
        const wy = ty(geo.waistY + 0.02);
        fill(o.top2C, TR[0], wy - 3, TW, 6);
      }
      // side slits shading on lower torso (kurta)
      folds(TR[0], ty(geo.waistY), TW, TR[3] - ty(geo.waistY), 16, 'v', 0.1, 0.8);
    }
    // graphic print on chest
    if (o.pattern === 'graphic') {
      const gx = tu(0.25), gy = ty(geo.chestY + 0.02);
      const gc = o.top2C, gc2 = mix(o.topC, [255, 255, 255], 0.7);
      const kind = Math.floor(r() * 3);
      g.save();
      if (kind === 0) { g.fillStyle = rgb(gc, 0.85); g.fillRect(gx - 22, gy - 14, 44, 30); g.fillStyle = rgb(gc2, 0.8); g.fillRect(gx - 16, gy - 8, 32, 5); g.fillRect(gx - 16, gy + 2, 22, 4); }
      else if (kind === 1) { g.fillStyle = rgb(gc, 0.85); g.beginPath(); g.arc(gx, gy, 16, 0, Math.PI * 2); g.fill(); g.fillStyle = rgb(gc2, 0.8); g.beginPath(); g.arc(gx, gy, 8, 0, Math.PI * 2); g.fill(); }
      else { g.fillStyle = rgb(gc2, 0.85); for (let i = 0; i < 4; i++) g.fillRect(gx - 26 + i * 14, gy - 6, 10, 12); g.fillRect(gx - 26, gy + 10, 52, 3); }
      g.restore();
      tex(T.speck, gx - 30, gy - 20, 60, 40, 'source-over', 0.8);
    }
    // fold shading on top garment: armpit/side creases and waist
    folds(TR[0], ty(geo.chestY + 0.06), TW, ty(geo.waistY - 0.05) - ty(geo.chestY + 0.06), 18, 'h', 0.1, 0.6);
    clothFolds(TR[0], TR[1], TW, yh - TR[1], 'torso', isLong);
    for (const su of [0.0, 0.5, 1.0]) { const x = tu(su); const gg = g.createLinearGradient(x - 26, 0, x + 26, 0); gg.addColorStop(0, 'rgba(0,0,0,0)'); gg.addColorStop(0.5, 'rgba(0,0,0,0.14)'); gg.addColorStop(1, 'rgba(0,0,0,0)'); g.fillStyle = gg; g.fillRect(x - 26, TR[1], 52, yh - TR[1]); }
    // side seams
    for (const su of [0.0, 0.5, 1.0]) line(tu(su), TR[1] + 8, tu(su), yh, mul(o.topC, 0.7), 0.35);
    // belt when tucked
    if (o.tucked) {
      const y0 = ty(beltY);
      fill([32, 24, 19], TR[0], y0 + 1, TW, 6);
      fill([150, 140, 115], tu(0.25) - 5, y0, 10, 8);
    }
  }
  // bust shading (female): soft darker under-bust line
  if (look.bust > 0.2 && o.top !== 'saree') {
    for (const s of [-1, 1]) {
      const cx = tu(0.25 + s * 0.06), cy = ty(geo.chestY - 0.03);
      const gg = g.createRadialGradient(cx, cy, 2, cx, cy, 20); gg.addColorStop(0, 'rgba(0,0,0,0.12)'); gg.addColorStop(1, 'rgba(0,0,0,0)');
      g.fillStyle = gg; g.fillRect(cx - 20, cy - 20, 40, 40);
    }
  }
  rough('torso', 0.92);
  if (o.top === 'saree') rough('torso', 0.75);
  if (o.top === 'jacket' && o.topC[2] < 90) rough('torso', 0.7);

  // ======================================================= SKIRT (kurta lower / saree / frock)
  const SR = REG.skirt;
  const SW = SR[2] - SR[0], SH = SR[3] - SR[1];
  fill(o.topC, SR[0], SR[1], SW, SH);
  fill(o.drapeC || o.topC, REG.drape[0], REG.drape[1], REG.drape[2] - REG.drape[0], REG.drape[3] - REG.drape[1]);
  if (o.top === 'saree') {
    fabric(SR[0], SR[1], SW, SH, o.topC, { pattern: o.pattern, c2: o.borderC, tile: T.weave });
    // pleat folds at the front (u .15-.35)
    for (let i = 0; i < 16; i++) {
      const x = SR[0] + (0.17 + i * 0.012) * SW;
      line(x, SR[1], x + (i - 8) * 0.8, SR[3], i % 2 ? mul(o.topC, 0.6) : mul(o.topC, 1.3), 0.55, 2);
    }
    folds(SR[0], SR[1], SW, SH, 40, 'v', 0.14, 1.2);
    // wide border at hem
    const bh = 16;
    fill(o.borderC, SR[0], SR[3] - bh, SW, bh);
    fill(mul(o.borderC, 0.7), SR[0], SR[3] - bh, SW, 2);
    for (let x = SR[0]; x < SR[2]; x += 6) { g.fillStyle = rgb(mul(o.borderC, 0.75), 0.8); g.fillRect(x, SR[3] - bh + 5, 3, 5); }
    fill(mul(o.topC, 0.7), SR[0], SR[3] - bh - 3, SW, 2);
    rough('skirt', 0.72);
  } else if (o.skirtLen) {
    const sopt = Object.assign({}, topOpt);
    fabric(SR[0], SR[1], SW, SH, o.topC, sopt);
    folds(SR[0], SR[1], SW, SH, 26, 'v', 0.12, 1.2);
    // hem border
    if (o.top === 'kameez' || o.top === 'kurti' || (o.top === 'kurta' && look.sex === 'f')) {
      fill(o.top2C, SR[0], SR[3] - 9, SW, 7, 0.85); fill(o.top3C || o.top2C, SR[0], SR[3] - 6, SW, 2, 0.7);
    }
    // side slits: soft shadow lines at u .0 and .5
    for (const su of [0, 0.5, 1]) line(SR[0] + su * SW, SR[1] + SH * 0.15, SR[0] + su * SW, SR[3], mul(o.topC, 0.78), 0.35, 2);
    // long vertical drape shadows down the skirt (large, low-contrast)
    clothFolds(SR[0], SR[1], SW, SH, 'skirt');
    rough('skirt', 0.92);
  }

  // ======================================================= LEGS (u: 0 inseam, .25 front, .5 outseam, .75 back; v top->ankle)
  const LR = REG.legs;
  const LW = LR[2] - LR[0], LH = LR[3] - LR[1];
  const lv = (frac) => LR[1] + frac * LH;
  if (o.bottom === 'saree') {
    // petticoat (inskirt) colour under the saree, skin at the ankles
    skinFill(LR[0], LR[1], LW, LH);
    fabric(LR[0], LR[1], LW, lv(0.82) - LR[1], mul(o.topC, 0.75), { tile: T.weave });
  } else if (o.bottom === 'bare') {
    skinFill(LR[0], LR[1], LW, LH);
    // knee shading
    vgrad(LR[0], lv(0.45), LW, 10, [0, 0, 0], 0, [0, 0, 0], 0.06);
  } else if (o.bottom === 'shorts') {
    skinFill(LR[0], LR[1], LW, LH);
    fabric(LR[0], LR[1], LW, lv(0.5) - LR[1], o.bottomC, { tile: T.denim });
    fill(mul(o.bottomC, 0.75), LR[0], lv(0.5) - 3, LW, 3);
    vgrad(LR[0], lv(0.5), LW, 6, [0, 0, 0], 0.25, [0, 0, 0], 0);
  } else {
    fabric(LR[0], LR[1], LW, LH, o.bottomC, { tile: bottomTile, pattern: 'plain' });
    if (o.bottom === 'jeans') {
      // fades: lighter on front thigh and knees
      for (const [cu, cv, rr, a] of [[0.25, 0.22, 30, 0.12], [0.25, 0.48, 18, 0.1], [0.75, 0.15, 30, 0.06]]) {
        const cx = LR[0] + cu * LW, cy = lv(cv);
        const gg = g.createRadialGradient(cx, cy, 2, cx, cy, rr * 1.6); gg.addColorStop(0, `rgba(255,255,255,${a})`); gg.addColorStop(1, 'rgba(255,255,255,0)');
        g.fillStyle = gg; g.fillRect(cx - rr * 2, cy - rr * 2, rr * 4, rr * 4);
      }
      // outseam stitching & inseam
      line(LR[0] + 0.5 * LW, LR[1], LR[0] + 0.5 * LW, LR[3], [175, 130, 80], 0.45, 1);
      line(LR[0] + 0.5 * LW + 2, LR[1], LR[0] + 0.5 * LW + 2, LR[3], mul(o.bottomC, 0.6), 0.6, 1);
      line(LR[0] + 2, LR[1], LR[0] + 2, LR[3], mul(o.bottomC, 0.6), 0.5, 2);
      // knee whiskers and back-knee honeycombs
      folds(LR[0] + 0.12 * LW, lv(0.42), 0.26 * LW, 22, 6, 'h', 0.18, 0.8);
      folds(LR[0] + 0.62 * LW, lv(0.45), 0.26 * LW, 20, 7, 'h', 0.2, 0.7);
      // stacking near the hem
      folds(LR[0], lv(0.85), LW, lv(0.98) - lv(0.85), 14, 'h', 0.22, 0.9);
      fill(mul(o.bottomC, 0.8), LR[0], lv(0.985), LW, LR[3] - lv(0.985));
      rough('legs', 0.88);
    } else if (o.bottom === 'chinos') {
      line(LR[0] + 0.25 * LW, LR[1] + 6, LR[0] + 0.25 * LW, LR[3], mul(o.bottomC, 1.18), 0.4, 1.5); // crease
      line(LR[0] + 0.5 * LW, LR[1], LR[0] + 0.5 * LW, LR[3], mul(o.bottomC, 0.7), 0.5, 1);
      folds(LR[0] + 0.62 * LW, lv(0.45), 0.26 * LW, 20, 5, 'h', 0.15, 0.7);
      folds(LR[0], lv(0.86), LW, lv(0.98) - lv(0.86), 8, 'h', 0.16, 0.9);
      rough('legs', 0.9);
    } else if (o.bottom === 'salwar' || o.bottom === 'pyjama') {
      folds(LR[0], LR[1], LW, LH, 46, 'v', 0.2, 1.4);
      fill(mul(o.bottomC, 0.8), LR[0], lv(0.95), LW, LR[3] - lv(0.95));
      folds(LR[0], lv(0.88), LW, lv(0.97) - lv(0.88), 10, 'h', 0.2, 0.6);
      rough('legs', 0.93);
    } else if (o.bottom === 'churidar' || o.bottom === 'leggings') {
      // churidar bunching at the calf: soft, low-contrast (the geometry ripples carry most of it)
      if (o.bottom === 'churidar') { g.save(); g.filter = 'blur(1.5px)'; for (let k = 0; k < 9; k++) { const y = lv(0.7 + k * 0.032); line(LR[0], y, LR[2], y + (k % 2 ? 2 : -1), mul(o.bottomC, 0.85), 0.5, 3); line(LR[0], y + 3, LR[2], y + 4, mul(o.bottomC, 1.06), 0.35, 2); } g.restore(); }
      folds(LR[0], LR[1], LW, LH * 0.6, 10, 'h', 0.08, 0.8);
      rough('legs', o.bottom === 'leggings' ? 0.7 : 0.9);
    }
  }
  if (o.bottom !== 'saree' && o.bottom !== 'bare' && o.bottom !== 'shorts') clothFolds(LR[0], LR[1], LW, LH, 'knee');
  // ======================================================= ARMS (u: 0 medial, .25 front, .5 lateral, .75 back; v shoulder->wrist)
  const AR = REG.arms;
  const AW = AR[2] - AR[0], AH = AR[3] - AR[1];
  skinFill(AR[0], AR[1], AW, AH);
  // forearm hair/shade and elbow
  vgrad(AR[0], AR[1] + AH * 0.5, AW, AH * 0.5, [0, 0, 0], 0, [0, 0, 0], 0.04);
  {
    let sl = o.sleeve || 0;
    const rolled = o.top === 'shirt' && sl > 0.5 && sl < 0.9;
    let sc = o.top === 'saree' ? o.blouseC : (o.top === 'jacket' ? o.topC : o.topC);
    if (sl > 0) {
      const ys = AR[1] + sl * AH;
      fabric(AR[0], AR[1], AW, ys - AR[1], sc, o.top === 'saree' ? { pattern: 'plain' } : Object.assign({}, topOpt, { per: topOpt.per ? topOpt.per * 0.6 : undefined }));
      folds(AR[0], AR[1] + AH * 0.35, AW, Math.max(4, ys - AR[1] - AH * 0.35), 10, 'h', 0.14, 0.7);
      if (sl > 0.6) clothFolds(AR[0], AR[1], AW, ys - AR[1], 'sleeve');
      // hem/cuff
      if (rolled) { fill(mul(sc, 0.9), AR[0], ys - 9, AW, 9); line(AR[0], ys - 9, AR[2], ys - 9, mul(sc, 0.6), 0.7, 1.5); }
      else if (sl >= 0.95) { fill(mul(sc, o.top === 'hoodie' ? 0.85 : 0.9), AR[0], ys - 9, AW, 9); if (o.top === 'hoodie') tex(T.knit, AR[0], ys - 9, AW, 9, 'multiply', 0.9); }
      else fill(mul(sc, 0.88), AR[0], ys - 2, AW, 2);
      if (o.pattern === 'print' && (o.top === 'kameez' || o.top === 'kurti' || o.top === 'kurta')) fill(o.top2C, AR[0], ys - 6, AW, 4);
      vgrad(AR[0], ys, AW, 5, [0, 0, 0], 0.3, [0, 0, 0], 0);
      // underarm seam
      line(AR[0] + 1, AR[1], AR[0] + 1, ys, mul(sc, 0.65), 0.5, 1.5);
    }
    // wrist accessories
    if (look.wrist === 'watch' && sl < 0.9) { fill([28, 28, 30], AR[0], AR[3] - 10, AW, 5); fill([150, 150, 150], AR[0] + 0.5 * AW - 4, AR[3] - 11, 8, 7); }
    if (look.wrist === 'bangles' && sl < 0.9) for (let k = 0; k < 3; k++) fill(k % 2 ? [190, 150, 70] : [140, 30, 50], AR[0], AR[3] - 12 + k * 3, AW, 2);
  }
  rough('arms', o.sleeve > 0.9 ? 0.9 : 0.62);
  // ======================================================= HANDS
  const HR = REG.hands;
  skinFill(HR[0], HR[1], HR[2] - HR[0], HR[3] - HR[1]);
  // palm side lighter (u around .0-.25?), knuckle lines
  fill(mix(skin, [235, 200, 185], 0.25), HR[0], HR[1], (HR[2] - HR[0]) * 0.5, HR[3] - HR[1], 0.6);
  for (let k = 0; k < 4; k++) line(HR[0] + (HR[2] - HR[0]) * 0.55, HR[1] + 26 + k * 2, HR[2], HR[1] + 26 + k * 2, skinSh, 0.25, 1);
  rough('hands', 0.6);
  // ======================================================= SHOES (u around, v heel->toe)
  const ShR = REG.shoes;
  const ShW = ShR[2] - ShR[0], ShH = ShR[3] - ShR[1];
  if (o.shoes === 'sandal' || o.shoes === 'flat') {
    skinFill(ShR[0], ShR[1], ShW, ShH);
    // toenail hints at toe end
    fill(mix(skin, [240, 220, 210], 0.4), ShR[0] + ShW * 0.15, ShR[3] - 5, ShW * 0.2, 3);
    if (o.shoes === 'flat') {
      // closed-toe flat: upper covers the front part of the foot
      fill(o.shoeC, ShR[0], ShR[1] + ShH * 0.55, ShW, ShH * 0.45);
      fill(mul(o.shoeC, 1.25), ShR[0] + ShW * 0.15, ShR[1] + ShH * 0.6, ShW * 0.2, 3);
      fill(o.shoeC, ShR[0], ShR[1], ShW, ShH * 0.12); // heel counter
    } else {
      // straps: across the forefoot and an ankle/toe strap
      fill(o.shoeC, ShR[0], ShR[1] + ShH * 0.62, ShW, 7);
      fill(o.shoeC, ShR[0], ShR[1] + ShH * 0.35, ShW, 5);
      fill(o.shoeC, ShR[0], ShR[1], ShW, ShH * 0.06);
    }
    // sole band at the bottom of every ring (u ~ .2-.3 bottom?) handled by geometry colour
    rough('shoes', 0.55);
  } else {
    fill(o.shoeC, ShR[0], ShR[1], ShW, ShH);
    tex(o.shoes === 'sneaker' ? T.weave : T.skin, ShR[0], ShR[1], ShW, ShH, 'multiply', 0.8);
    if (o.shoes === 'sneaker') {
      // laces on top (u .5 is top for the foot loft), tongue, swoosh-like side stripe, heel tab
      const tx = ShR[0] + 0.5 * ShW;
      fill(mul(o.shoeC, 0.92), tx - 9, ShR[1] + ShH * 0.25, 18, ShH * 0.45);
      for (let k = 0; k < 6; k++) line(tx - 7, ShR[1] + ShH * (0.3 + k * 0.06), tx + 7, ShR[1] + ShH * (0.32 + k * 0.06), [238, 236, 230], 0.9, 1.5);
      const acc = mix(o.soleC, o.shoeC[0] > 150 ? [60, 70, 90] : [220, 220, 215], 0.6);
      for (const s of [0.25, 0.75]) { g.strokeStyle = rgb(acc, 0.8); g.lineWidth = 3; g.beginPath(); g.moveTo(ShR[0] + s * ShW - 6, ShR[1] + ShH * 0.25); g.quadraticCurveTo(ShR[0] + s * ShW, ShR[1] + ShH * 0.6, ShR[0] + s * ShW + 4, ShR[1] + ShH * 0.8); g.stroke(); }
      fill(acc, tx - 6, ShR[1], 12, 6);
      rough('shoes', 0.8);
    } else {
      // leather shine streak + toe cap seam
      fill(mix(o.shoeC, [255, 255, 255], 0.12), ShR[0] + 0.45 * ShW, ShR[1] + ShH * 0.7, 0.1 * ShW, ShH * 0.25);
      line(ShR[0], ShR[1] + ShH * 0.72, ShR[2], ShR[1] + ShH * 0.72, mul(o.shoeC, 0.6), 0.6);
      rough('shoes', 0.4);
    }
    // the sole band: bottom quadrant of the ring -> u from .125 to .375? (ring theta 0 is the bottom)
  }
  // ======================================================= DRAPE (dupatta / pallu): u across width, v along length
  const DR = REG.drape;
  const DW = DR[2] - DR[0], DH = DR[3] - DR[1];
  if (o.drapeC) {
    const sareeD = o.top === 'saree';
    if (!sareeD) r(); // keep the random sequence of the looks after this point unchanged
    fabric(DR[0], DR[1], DW, DH, o.drapeC, { pattern: sareeD ? o.pattern : 'plain', c2: o.drapeBorderC, per: 12 });
    // thin borders along both long edges (u 0 and .5: the ribbon's width edges), toned into the cloth
    const bC = sareeD ? o.drapeBorderC : mix(o.drapeBorderC, o.drapeC, 0.45);
    for (const su of [0.0, 0.5, 1.0]) fill(bC, DR[0] + su * DW - 2.5, DR[1], 5, DH, 0.9);
    folds(DR[0], DR[1], DW, DH, 20, 'v', 0.14, 1.2);
    // short, dark fringe at the end (~1.5 cm)
    fill(mul(bC, 0.8), DR[0], DR[3] - 4, DW, 4, 0.85);
    rough('drape', o.top === 'saree' ? 0.7 : 0.88);
  }
  // ======================================================= HEAD (u around, .5 = face centre; v top->chin)
  paintHead(g, look, geo, rng, T, skinFill, fill, tex);
  rough('head', 0.68);
  // ======================================================= HAIR
  const HaR = REG.hair;
  fill(look.hairColor, HaR[0], HaR[1], HaR[2] - HaR[0], HaR[3] - HaR[1]);
  g.save(); g.globalCompositeOperation = 'multiply'; g.drawImage(T.hair, HaR[0], HaR[1], HaR[2] - HaR[0], HaR[3] - HaR[1]); g.restore();
  if (look.grey > 0) tex(T.greyStrands, HaR[0], HaR[1], HaR[2] - HaR[0], HaR[3] - HaR[1], 'source-over', Math.min(0.45, look.grey * 0.5));
  // strand streaks running from the crown (v = 0) down and around (lighter / darker combed lines)
  {
    const hw = HaR[2] - HaR[0], hh = HaR[3] - HaR[1];
    g.save(); g.beginPath(); g.rect(HaR[0], HaR[1], hw, hh); g.clip();
    for (let i = 0; i < 70; i++) {
      const x = HaR[0] + r() * hw, y0 = HaR[1] + r() * hh * 0.3, len = hh * (0.3 + 0.6 * r());
      const light = r() < 0.45;
      g.strokeStyle = light ? `rgba(255,235,210,${0.05 + 0.05 * r()})` : `rgba(0,0,0,${0.10 + 0.12 * r()})`;
      g.lineWidth = 0.6 + r() * 0.9;
      g.beginPath(); g.moveTo(x, y0); g.quadraticCurveTo(x + (r() - 0.5) * 6, y0 + len * 0.5, x + (r() - 0.5) * 10, y0 + len); g.stroke();
    }
    // crown whorl: a small darker spiral where the strands part (top of the head, v ~ 0)
    const wx = HaR[0] + (0.5 + (r() - 0.5) * 0.3) * hw, wy = HaR[1] + 3;
    for (let k = 0; k < 7; k++) {
      const a0 = k * 0.9;
      g.strokeStyle = `rgba(0,0,0,${0.16})`; g.lineWidth = 0.8;
      g.beginPath(); g.moveTo(wx, wy); g.quadraticCurveTo(wx + Math.cos(a0) * 6, wy + Math.abs(Math.sin(a0)) * 4, wx + Math.cos(a0 + 0.8) * 12, wy + Math.abs(Math.sin(a0 + 0.8)) * 9); g.stroke();
    }
    g.restore();
  }
  // highlight band where the downlights catch the top of the head (anisotropic-looking stripe)
  { const gg = g.createLinearGradient(0, HaR[1], 0, HaR[3]); gg.addColorStop(0.05, 'rgba(255,255,255,0)'); gg.addColorStop(0.18, `rgba(255,236,210,${0.13})`); gg.addColorStop(0.24, `rgba(255,236,210,${0.06})`); gg.addColorStop(0.36, 'rgba(255,255,255,0)'); g.fillStyle = gg; g.fillRect(HaR[0], HaR[1], HaR[2] - HaR[0], HaR[3] - HaR[1]); }
  // parting line (front centre u = .5 from the crown v=0 down a bit)
  if (look.sex === 'f' || (look.hair === 'medium' && r() < 0.5)) {
    const px = HaR[0] + (look.parting === 'side' || look.sex === 'm' ? 0.5 + 0.07 : 0.5) * (HaR[2] - HaR[0]);
    const ph = (HaR[3] - HaR[1]) * 0.4;
    g.strokeStyle = rgb(mix(skin, look.hairColor, 0.45), look.sex === 'm' ? 0.5 : 0.8); g.lineWidth = 1.1; g.beginPath(); g.moveTo(px, HaR[1] + ph * 0.32); g.lineTo(px, HaR[1] + ph); g.stroke();
    if (look.sindoor) { g.strokeStyle = 'rgba(170,25,30,0.95)'; g.lineWidth = 1.5; g.beginPath(); g.moveTo(px, HaR[1] + ph * 0.55); g.lineTo(px, HaR[1] + ph); g.stroke(); }
  }
  rough('hair', 0.74);
  // ======================================================= ITEMS
  const IT = ITEM_REG;
  { // popcorn tub sides: vertical stripes
    const [x0, y0, x1, y1] = IT.tub; const w = x1 - x0, h = y1 - y0;
    fill(look.tubC[1], x0, y0, w, h);
    const n = 8;
    for (let i = 0; i < n; i++) if (i % 2 === 0) fill(look.tubC[0], x0 + (i / n) * w, y0, w / n, h);
    fill(look.tubC[0], x0, y0, w, h * 0.08); // rim band
    for (const cx of [0.25, 0.75]) { g.fillStyle = rgb(look.tubC[0]); g.beginPath(); g.ellipse(x0 + cx * w, y0 + h * 0.5, w * 0.07, h * 0.12, 0, 0, Math.PI * 2); g.fill(); g.fillStyle = 'rgba(245,240,230,0.95)'; g.fillRect(x0 + cx * w - w * 0.04, y0 + h * 0.48, w * 0.08, h * 0.04); }
    tex(T.weave, x0, y0, w, h, 'multiply', 0.5);
  }
  { // cup
    const [x0, y0, x1, y1] = IT.cup; const w = x1 - x0, h = y1 - y0;
    if (look.cupClear) { fill([60, 30, 20], x0, y0 + h * 0.15, w, h * 0.85); fill([150, 120, 100], x0, y0, w, h * 0.15); fill([210, 205, 200], x0, y0 + h * 0.5, w, h * 0.2, 0.5); }
    else { fill(look.cupC[0], x0, y0, w, h); fill(look.cupC[1], x0, y0 + h * 0.3, w, h * 0.35); fill(look.cupC[0], x0 + w * 0.2, y0 + h * 0.4, w * 0.3, h * 0.12); fill(look.cupC[0], x0 + w * 0.7, y0 + h * 0.4, w * 0.25, h * 0.12); }
  }
  { // bag
    const [x0, y0, x1, y1] = IT.bag; const w = x1 - x0, h = y1 - y0;
    fill(look.bagC, x0, y0, w, h); tex(T.skin, x0, y0, w, h, 'multiply', 1);
    line(x0, y0 + h * 0.3, x1, y0 + h * 0.3, mul(look.bagC, 0.6), 0.8, 1); fill([170, 150, 100], x0 + w * 0.45, y0 + h * 0.25, w * 0.1, h * 0.12);
  }
  { // phone
    const [x0, y0, x1, y1] = IT.phone; const w = x1 - x0, h = y1 - y0;
    fill(look.phoneC, x0, y0, w, h);
    fill([30, 50, 80], x0 + 3, y0 + 3, w - 6, h - 6);
    fill([90, 130, 170], x0 + 5, y0 + 6, w - 10, 4); fill([200, 210, 220], x0 + 5, y0 + 13, w - 14, 2); fill([200, 210, 220], x0 + 5, y0 + 17, w - 10, 2);
  }
  gr.fillStyle = 'rgb(110,110,110)'; gr.fillRect(IT.cup[0] / 4, IT.cup[1] / 4, 8, 14);
  gr.fillStyle = 'rgb(60,60,60)'; gr.fillRect(IT.phone[0] / 4, IT.phone[1] / 4, 8, 7);
  gr.fillStyle = 'rgb(170,170,170)'; gr.fillRect(IT.tub[0] / 4, IT.tub[1] / 4, 16, 14);
  gr.fillStyle = 'rgb(130,130,130)'; gr.fillRect(IT.bag[0] / 4, IT.bag[1] / 4, 8, 7);
  // cloth sheen mask (grey = sheen strength) at roughness-map resolution
  const shc = makeCanvas(ATLAS / 4, ATLAS / 4);
  const shg = shc.getContext('2d');
  shg.fillStyle = '#000'; shg.fillRect(0, 0, ATLAS / 4, ATLAS / 4);
  const shR = (reg, v, y0f = 0, y1f = 1) => { const R = REG[reg]; const y0 = R[1] + (R[3] - R[1]) * y0f, y1 = R[1] + (R[3] - R[1]) * y1f; shg.fillStyle = `rgb(${v * 255 | 0},${v * 255 | 0},${v * 255 | 0})`; shg.fillRect(R[0] / 4, y0 / 4, (R[2] - R[0]) / 4, (y1 - y0) / 4); };
  const knit = o.top === 'hoodie' || o.top === 'tee' || o.top === 'polo';
  shR('torso', knit ? 0.45 : 0.32);
  if (o.skirtLen || o.top === 'saree') shR('skirt', 0.35);
  shR('drape', 0.4);
  if (o.bottom !== 'saree' && o.bottom !== 'bare') shR('legs', o.bottom === 'jeans' ? 0.22 : 0.32, 0, o.bottom === 'shorts' ? 0.5 : 1);
  if (o.sleeve > 0) shR('arms', knit ? 0.45 : 0.32, 0, o.sleeve);
  return { canvas: cv, rough: rc, sheen: shc };
}

function paintHead(g, look, geo, rng, T, skinFill, fill, tex) {
  const r = () => rng();
  const R = REG.head;
  const W = R[2] - R[0], Hh = R[3] - R[1];
  const skin = look.skin;
  const X = (u) => R[0] + u * W;
  const Y = (v) => R[1] + v * Hh; // v: 0 crown, 1 chin bottom
  const s2v = (s) => 1 - s;       // s: height fraction from chin
  skinFill(R[0], R[1], W, Hh);
  const F = geo.face; // { eyeS, browS, noseS, mouthS, hairS, eyeDu, child }
  const du = F.eyeDu;
  // subtle colouring: warmer cheeks, darker under-jaw, lighter forehead
  const blob = (u, s, rx, ry, c, a) => {
    const cx = X(u), cy = Y(s2v(s));
    g.save(); g.translate(cx, cy); g.scale(1, ry / rx);
    const gg = g.createRadialGradient(0, 0, 0, 0, 0, rx);
    gg.addColorStop(0, `rgba(${c[0]},${c[1]},${c[2]},${a})`); gg.addColorStop(1, `rgba(${c[0]},${c[1]},${c[2]},0)`);
    g.fillStyle = gg; g.fillRect(-rx, -rx, rx * 2, rx * 2); g.restore();
  };
  for (const s of [-1, 1]) blob(0.5 + s * du * 1.4, F.noseS, 9, 7, [170, 70, 60], 0.13);
  blob(0.5, F.browS + 0.12, 14, 8, [255, 230, 210], 0.08);
  // jaw/under-chin darker
  { const gg = g.createLinearGradient(0, Y(s2v(0.12)), 0, Y(1)); gg.addColorStop(0, 'rgba(0,0,0,0)'); gg.addColorStop(1, 'rgba(40,20,10,0.25)'); g.fillStyle = gg; g.fillRect(R[0], Y(s2v(0.12)), W, Y(1) - Y(s2v(0.12))); }
  // eye sockets (shadowed), eyes, brows
  for (const s of [-1, 1]) {
    const ex = 0.5 + s * du;
    blob(ex, F.eyeS + 0.01, 6, 4, [70, 38, 28], 0.09);
    // eye: small dark almond (at CCTV scale the whites barely register)
    const cx = X(ex), cy = Y(s2v(F.eyeS));
    g.fillStyle = 'rgba(225,215,205,0.25)'; g.beginPath(); g.ellipse(cx, cy, 3.0, 1.2, 0, 0, Math.PI * 2); g.fill();
    g.fillStyle = 'rgba(25,15,12,0.6)'; g.beginPath(); g.arc(cx + s * -0.3, cy, 1.15, 0, Math.PI * 2); g.fill();
    g.strokeStyle = 'rgba(20,12,10,0.5)'; g.lineWidth = 0.8; g.beginPath(); g.ellipse(cx, cy, 3.3, 1.4, 0, Math.PI, Math.PI * 2); g.stroke();
    // brow
    const by = Y(s2v(F.browS));
    g.strokeStyle = `rgba(${look.hairColor.map((v) => v | 0).join(',')},${look.sex === 'm' ? 0.8 : 0.6})`;
    g.lineWidth = look.sex === 'm' ? 1.9 : 1.1; g.lineCap = 'round';
    g.beginPath(); g.moveTo(cx - s * 3.6, by + 0.8); g.quadraticCurveTo(cx + s * 0.5, by - 1.4, cx + s * 4.2, by + 0.6); g.stroke();
  }
  // nose: shading on sides and nostrils
  { const nx = X(0.5), ny = Y(s2v(F.noseS));
    g.fillStyle = 'rgba(60,30,20,0.35)'; g.beginPath(); g.ellipse(nx - 2.2, ny + 0.5, 1.1, 0.8, 0, 0, Math.PI * 2); g.fill(); g.beginPath(); g.ellipse(nx + 2.2, ny + 0.5, 1.1, 0.8, 0, 0, Math.PI * 2); g.fill();
    blob(0.5, F.noseS + 0.08, 3, 7, [255, 235, 220], 0.12); }
  // lips
  { const mx = X(0.5), my = Y(s2v(F.mouthS));
    const lc = look.sex === 'f' && r() < 0.5 ? [140, 40, 50] : [mul3(skin, 0.7)[0], mul3(skin, 0.6)[1], mul3(skin, 0.6)[2]];
    g.fillStyle = `rgba(${lc[0] | 0},${lc[1] | 0},${lc[2] | 0},0.85)`;
    g.beginPath(); g.ellipse(mx, my - 0.6, 4.6, 1.3, 0, Math.PI, Math.PI * 2); g.fill();
    g.beginPath(); g.ellipse(mx, my + 0.2, 4.0, 1.6, 0, 0, Math.PI); g.fill();
    g.strokeStyle = 'rgba(40,15,12,0.7)'; g.lineWidth = 0.8; g.beginPath(); g.moveTo(mx - 4.5, my); g.quadraticCurveTo(mx, my + 0.6, mx + 4.5, my); g.stroke(); }
  // beard
  if (look.beard !== 'none') {
    const hc = look.hairColor;
    const a = look.beard === 'stubble' ? 0.26 : 0.72;
    g.save();
    g.fillStyle = `rgba(${hc[0] | 0},${hc[1] | 0},${hc[2] | 0},${a})`;
    if (look.beard === 'full' || look.beard === 'stubble') {
      // jaw region: from below the cheekbones to the chin, around to the ears
      g.beginPath();
      g.moveTo(X(0.5 - 0.235), Y(s2v(0.34)));
      g.quadraticCurveTo(X(0.5 - 0.16), Y(s2v(F.noseS - 0.06)), X(0.5 - du * 1.4), Y(s2v(F.mouthS + 0.05)));
      g.lineTo(X(0.5 - du * 0.9), Y(s2v(F.mouthS + 0.1)));
      g.quadraticCurveTo(X(0.5), Y(s2v(F.mouthS + 0.14)), X(0.5 + du * 0.9), Y(s2v(F.mouthS + 0.1)));
      g.lineTo(X(0.5 + du * 1.4), Y(s2v(F.mouthS + 0.05)));
      g.quadraticCurveTo(X(0.5 + 0.16), Y(s2v(F.noseS - 0.06)), X(0.5 + 0.235), Y(s2v(0.34)));
      g.lineTo(X(0.5 + 0.26), Y(1)); g.lineTo(X(0.5 - 0.26), Y(1)); g.closePath(); g.fill();
      // keep lips visible
      g.fillStyle = `rgba(${mul3(skin, 0.65).map((v) => v | 0).join(',')},${look.beard === 'full' ? 0.9 : 0.5})`;
      g.beginPath(); g.ellipse(X(0.5), Y(s2v(F.mouthS)), 4.2, 1.5, 0, 0, Math.PI * 2); g.fill();
    } else {
      g.beginPath(); g.ellipse(X(0.5), Y(s2v(F.mouthS + 0.045)), 6.5, 1.8, 0, 0, Math.PI * 2); g.fill();
    }
    g.restore();
    tex(T.speck, R[0], Y(s2v(F.noseS)), W, Y(1) - Y(s2v(F.noseS)), 'source-over', 0.4);
  }
  // glasses
  if (look.glasses) {
    const c = look.glassesColor;
    g.strokeStyle = `rgba(${c[0]},${c[1]},${c[2]},0.7)`; g.lineWidth = 0.8;
    for (const s of [-1, 1]) { g.beginPath(); g.ellipse(X(0.5 + s * du), Y(s2v(F.eyeS)), 4.2, 2.8, 0, 0, Math.PI * 2); g.stroke(); }
    g.beginPath(); g.moveTo(X(0.5 - du) + 4.6, Y(s2v(F.eyeS)) - 1); g.lineTo(X(0.5 + du) - 4.6, Y(s2v(F.eyeS)) - 1); g.stroke();
    for (const s of [-1, 1]) { g.beginPath(); g.moveTo(X(0.5 + s * du) + s * 4.6, Y(s2v(F.eyeS)) - 1); g.lineTo(X(0.5 + s * 0.24), Y(s2v(F.eyeS + 0.02))); g.stroke(); }
  }
  if (look.bindi) { g.fillStyle = 'rgba(150,20,35,0.95)'; g.beginPath(); g.arc(X(0.5), Y(s2v(F.browS + 0.02)), 1.2, 0, Math.PI * 2); g.fill(); }
  // scalp / hair region painted with hair colour (soft hairline)
  const hc = look.hairColor;
  const bald = look.hair === 'receding';
  {
    const N = 64;
    const sm = makeCanvas(N, N);
    const sg = sm.getContext('2d');
    const im = sg.createImageData(N, N);
    for (let j = 0; j < N; j++) {
      const s = 1 - (j + 0.5) / N;
      for (let i = 0; i < N; i++) {
        const u = (i + 0.5) / N;
        let cov = hairCoverage(look, F, u, s);
        if (bald && s > 0.8 && Math.abs(u - 0.5) < 0.22) cov *= 0.25;
        const k = (j * N + i) * 4;
        im.data[k] = hc[0]; im.data[k + 1] = hc[1]; im.data[k + 2] = hc[2]; im.data[k + 3] = Math.round(clamp(cov, 0, 1) * 255);
      }
    }
    sg.putImageData(im, 0, 0);
    g.save(); g.imageSmoothingEnabled = true; g.drawImage(sm, R[0], R[1], W, Hh); g.restore();
  }
  tex(T.hair, R[0], R[1], W, Y(s2v(F.hairS - 0.15)) - R[1], 'multiply', 0.5);
  // ears region shading (behind ears)
  for (const s of [-1, 1]) blob(0.5 + s * 0.25, F.eyeS - 0.08, 6, 10, [60, 30, 20], 0.18);
}
function mul3(c, k) { return [c[0] * k, c[1] * k, c[2] * k]; }

// Hair coverage on the head surface at (u around, .5 = front; s = height fraction from chin).
// Shared by the painter and the hair-shell geometry so they agree.
export function hairCoverage(look, F, u, s, softness = 0.03) {
  const a = (u - 0.5) * Math.PI * 2; // 0 = front, +-pi = back
  const ca = Math.cos(a);
  // hairline height (in s) as a function of angle: forehead high, temples, around ears, nape low
  const front = F.hairS + (look.hair === 'receding' ? 0.09 : 0) - (look.sex === 'f' ? 0.01 : 0);
  const side = F.eyeS + 0.12; // above the ear
  const back = look.sex === 'f' ? 0.12 : 0.3;
  let line;
  if (ca > 0.3) line = lerp(side, front, Math.pow((ca - 0.3) / 0.7, 0.6));
  else if (ca > -0.35) line = side + (look.sex === 'm' && look.hair !== 'medium' ? 0.02 : -0.05) * (1 - Math.abs(ca));
  else line = lerp(side, back, Math.pow((-ca - 0.35) / 0.65, 0.8));
  // ear cut-out (hair goes over the ear for long styles)
  const earA = Math.abs(Math.abs(a) - Math.PI / 2);
  if (look.sex === 'm' || look.hair === 'bun' || look.hair === 'braid' || look.hair === 'pony') {
    if (earA < 0.35 && s < F.eyeS + 0.1) line = Math.max(line, F.eyeS + 0.1);
  }
  return clamp((s - line) / softness + 0.5, 0, 1);
}
