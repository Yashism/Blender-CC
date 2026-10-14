// The cinema auditorium entrance as seen by a ceiling dome camera.
// World: metres, Y up, floor y = 0, camera looks toward -Z. See SPEC.md.
//
// Corridor (lit, PBR): patterned carpet, acoustic-fabric wall panels with brass
// trims and warm LED strips, padded double doors open into the corridor, ticket
// podium with a tablet, chrome stanchions with belts, plaster ceiling with
// downlights (4 shadow casters).
// The LED wall-wash is baked per vertex (analytic, in code) and added in the
// shader as albedo x irradiance, so it costs nothing at run time and never leaks.
// Auditorium (behind the door, very dark): unlit baked materials so corridor
// lights never reach it; seat rows, aisle step lights, glowing screen.
import * as THREE from 'three';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';
import { distortNdc } from './cctv_pass.js';
import { smoothNoise1, mulberry32, hash2 } from './rng.js';
import {
  carpetTextures, fabricTextures, brassTextures, tuftedTextures, woodTextures,
  chromeTextures, plasterTextures, velvetTextures, screenTexture, tabletTexture, glowTexture,
} from './textures.js';

export const LINE = { z: -3.3, x0: -2.4, x1: 2.4 };

// Camera fitted to look_ref.jpg (door corners, door leaves, wall/floor and
// wall/ceiling junction curves; least squares incl. lens distortion). Euler YXZ.
export const CAMERA = {
  position: [0.0927, 3.15, 2.9024],
  yaw: -0.0279,   // rad, + turns toward -X
  pitch: 0.4724,  // rad, looking down
  roll: -0.0318,  // rad
  fov: 73.89,     // vertical, degrees, pinhole (before barrel distortion)
  near: 0.05,
  far: 60,
};

export const CEIL = 3.25;
const WALL_Z = -4.9; // face of the door-wall panels (door frame recess behind it to z = -5.0)
export const DOOR = { x0: -1.3, x1: 1.3, height: 2.6, z: -5.0, reveal: 0.3, leafWidth: 1.27, leafAngleL: 106.6, leafAngleR: 104.5 };

// Wall plan (x, z). Walking A -> B keeps the room on the left (frame Z = into room).
// `at` = metres from A. Hidden first/last segments flare behind the camera.
const WALLS = [
  { a: [-4.6, 4.6], b: [-3.68, 1.0], joints: [] },
  { a: [-3.68, 1.0], b: [-3.97, -4.08], joints: [{ at: 0.33, type: 'led' }, { at: 1.96, type: 'trim' }, { at: 3.49, type: 'trim' }] },
  { a: [-3.97, -4.08], b: [-2.91, WALL_Z], joints: [] },
  { a: [-2.91, WALL_Z], b: [4.95, WALL_Z], joints: [{ at: 6.19, type: 'trim' }], door: true },
  { a: [4.95, WALL_Z], b: [5.0, 1.0], joints: [{ at: 1.5, type: 'trim' }, { at: 3.34, type: 'led' }, { at: 5.2, type: 'trim' }] },
  { a: [5.0, 1.0], b: [5.05, 4.6], joints: [] },
];
// joints between segment i and i + 1
const CORNERS = { 1: 'led', 2: 'trim', 3: 'led' };
// LED wash weights per strip: toward the A-end (wA) / B-end (wB) of its wall(s)
const LED_WEIGHTS = { '1:0.33': [0.85, 0.75], 'c1': [0.5, 1.0], 'c3': [1.0, 0.4], '4:3.34': [0.35, 1.35] };

// Footprints for the crowd planner (x, z in metres). Keep bodies out of these.
const rad = (d) => d * Math.PI / 180;
export const OBSTACLES = [
  { kind: 'box', name: 'podium', cx: 2.38, cz: -3.97, w: 0.55, d: 0.45 },
  { kind: 'circle', name: 'stanchionA', x: 3.12, z: -4.12, r: 0.18 },
  { kind: 'circle', name: 'stanchionB', x: 3.23, z: -2.6, r: 0.18 },
  { kind: 'circle', name: 'stanchionC', x: 3.98, z: -3.28, r: 0.18 },
  { kind: 'segment', name: 'beltAB', x0: 3.12, z0: -4.12, x1: 3.23, z1: -2.6 },
  { kind: 'segment', name: 'beltBC', x0: 3.23, z0: -2.6, x1: 3.98, z1: -3.28 },
  { kind: 'segment', name: 'leafL', x0: -1.3, z0: -4.96, x1: -1.3 + 1.27 * Math.cos(rad(106.6)), z1: -4.96 + 1.27 * Math.sin(rad(106.6)) },
  { kind: 'segment', name: 'leafR', x0: 1.3, z0: -4.96, x1: 1.3 - 1.27 * Math.cos(rad(104.5)), z1: -4.96 + 1.27 * Math.sin(rad(104.5)) },
];
// Walkable corridor outline (x, z), inside the wall faces (doorway at |x| < 1.3).
export const WALKABLE = [[-4.5, 3.6], [-3.6, 1.0], [-3.88, -4.02], [-2.88, -4.82], [4.86, -4.82], [4.92, 1.0], [4.95, 3.6]];

// ---------------------------------------------------------------------------
// geometry utilities

// Box with metric UVs (by face normal) and optional vertex AO.
// uvMode: 'xy' (default), 'yx' (long axis vertical -> u)
function boxGeo(w, h, d, { segX = 1, segY = 1, uvMode = 'xy', ao = null } = {}) {
  const g = new THREE.BoxGeometry(w, h, d, segX, segY, 1);
  const p = g.attributes.position, n = g.attributes.normal, uv = g.attributes.uv;
  const col = new Float32Array(p.count * 3);
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    const ax = Math.abs(n.getX(i)), ay = Math.abs(n.getY(i));
    let u, v;
    if (ay > 0.5) { u = x; v = z; } else if (ax > 0.5) { u = z; v = y; } else { u = x; v = y; }
    if (uvMode === 'yx') { const t = u; u = v; v = t; }
    uv.setXY(i, u, v);
    const a = ao ? ao(x, y, z) : 1;
    col[i * 3] = col[i * 3 + 1] = col[i * 3 + 2] = a;
  }
  g.setAttribute('color', new THREE.BufferAttribute(col, 3));
  return g;
}

const KEEP = ['position', 'normal', 'uv', 'color', 'wash'];
function ensureAttrs(g) {
  const n = g.attributes.position.count;
  if (!g.attributes.uv) g.setAttribute('uv', new THREE.BufferAttribute(new Float32Array(n * 2), 2));
  if (!g.attributes.color) g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(n * 3).fill(1), 3));
  if (!g.attributes.wash) g.setAttribute('wash', new THREE.BufferAttribute(new Float32Array(n * 3), 3));
  for (const k of Object.keys(g.attributes)) if (!KEEP.includes(k)) g.deleteAttribute(k);
  return g;
}

// Collects geometry per material, merges at the end (few draw calls).
class Batch {
  constructor() { this.groups = new Map(); }
  add(mat, geo, matrix, kind = null) {
    const g = ensureAttrs(geo);
    if (matrix) g.applyMatrix4(matrix);
    g.userData.kind = kind;
    if (!this.groups.has(mat)) this.groups.set(mat, { indexed: [], plain: [] });
    (g.index ? this.groups.get(mat).indexed : this.groups.get(mat).plain).push(g);
  }
  build(parent, { castShadow = false, receiveShadow = true, wash = null, parentMatrix = null } = {}) {
    const out = [];
    for (const [mat, { indexed, plain }] of this.groups) {
      for (const list of [indexed, plain]) {
        if (!list.length) continue;
        if (wash && mat.userData.washKind !== undefined) {
          for (const g of list) bakeWash(g, wash, g.userData.kind || mat.userData.washKind, parentMatrix);
        }
        const geo = mergeGeometries(list, false);
        geo.computeBoundingSphere();
        const mesh = new THREE.Mesh(geo, mat);
        mesh.castShadow = mat.userData.castShadow ?? castShadow;
        mesh.receiveShadow = mat.userData.receiveShadow ?? receiveShadow;
        mesh.matrixAutoUpdate = false;
        parent.add(mesh);
        out.push(mesh);
      }
    }
    return out;
  }
}

function bakeWash(g, washFn, kind, parentMatrix) {
  const p = g.attributes.position, n = g.attributes.normal, w = g.attributes.wash;
  const P = new THREE.Vector3(), N = new THREE.Vector3();
  const nm = parentMatrix ? new THREE.Matrix3().getNormalMatrix(parentMatrix) : null;
  const out = [0, 0, 0];
  for (let i = 0; i < p.count; i++) {
    P.fromBufferAttribute(p, i); N.fromBufferAttribute(n, i);
    if (parentMatrix) { P.applyMatrix4(parentMatrix); N.applyMatrix3(nm).normalize(); }
    washFn(P, N, kind, out);
    w.setXYZ(i, out[0], out[1], out[2]);
  }
}

// adds `diffuse * wash * scale` as emitted radiance (baked LED wall-wash)
function addWashShader(mat, kind, scale = 1) {
  mat.userData.washKind = kind;
  const prev = mat.onBeforeCompile;
  mat.onBeforeCompile = (sh, r) => {
    if (prev) prev(sh, r);
    sh.uniforms.uWashScale = { value: scale };
    mat.userData.shader = sh;
    sh.vertexShader = 'attribute vec3 wash;\nvarying vec3 vWash;\n' + sh.vertexShader.replace('#include <begin_vertex>', '#include <begin_vertex>\n\tvWash = wash;');
    sh.fragmentShader = 'uniform float uWashScale;\nvarying vec3 vWash;\n' + sh.fragmentShader.replace('#include <emissivemap_fragment>', '#include <emissivemap_fragment>\n\ttotalEmissiveRadiance += diffuseColor.rgb * vWash * uWashScale;');
  };
  mat.customProgramCacheKey = () => 'wash' + (mat.type || '');
}

// local frame of a wall segment: X along the wall (A -> B), Y up, Z into the room
function segFrame(a, b) {
  const dx = b[0] - a[0], dz = b[1] - a[1];
  const L = Math.hypot(dx, dz);
  const t = new THREE.Vector3(dx / L, 0, dz / L);
  const n = new THREE.Vector3(-t.z, 0, t.x);
  return { L, t, n, origin: new THREE.Vector3(a[0], 0, a[1]) };
}
function frameMatrix(f, s, o, y = 0) {
  const pos = f.origin.clone().addScaledVector(f.t, s).addScaledVector(f.n, o);
  pos.y = y;
  return new THREE.Matrix4().makeBasis(f.t, new THREE.Vector3(0, 1, 0), f.n).setPosition(pos);
}

// approximate blackbody -> linear sRGB (max channel = 1)
function kelvin(k) {
  const t = k / 100;
  let r, g, b;
  if (t <= 66) { r = 255; g = 99.47 * Math.log(t) - 161.12; b = t <= 19 ? 0 : 138.52 * Math.log(t - 10) - 305.04; } else { r = 329.7 * Math.pow(t - 60, -0.1332); g = 288.12 * Math.pow(t - 60, -0.0755); b = 255; }
  const c = new THREE.Color(Math.min(255, Math.max(0, r)) / 255, Math.min(255, Math.max(0, g)) / 255, Math.min(255, Math.max(0, b)) / 255);
  return c.convertSRGBToLinear();
}
const smooth = (a, b, x) => { const t = Math.min(1, Math.max(0, (x - a) / (b - a))); return t * t * (3 - 2 * t); };

// ---------------------------------------------------------------------------

export function buildEnvironment(scene, renderer) {
  if (renderer) {
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  }
  const root = new THREE.Group();
  root.name = 'environment';
  scene.add(root);
  scene.background = new THREE.Color(0x000000);

  // ---------------- materials
  const T = {
    carpet: carpetTextures(renderer), fabric: fabricTextures(renderer), brass: brassTextures(renderer),
    tufted: tuftedTextures(renderer), wood: woodTextures(renderer), chrome: chromeTextures(renderer),
    plaster: plasterTextures(renderer), velvet: velvetTextures(renderer),
  };
  const M = {};
  M.carpet = new THREE.MeshStandardMaterial({ map: T.carpet.map, normalMap: T.carpet.normalMap, roughnessMap: T.carpet.roughnessMap, roughness: 1, metalness: 0, vertexColors: true, normalScale: new THREE.Vector2(0.7, 0.7) });
  M.fabric = new THREE.MeshStandardMaterial({ map: T.fabric.map, normalMap: T.fabric.normalMap, roughness: 0.92, metalness: 0, vertexColors: true, normalScale: new THREE.Vector2(0.6, 0.6) });
  M.backing = new THREE.MeshStandardMaterial({ color: 0x0a0a0a, roughness: 0.9, vertexColors: true });
  M.brass = new THREE.MeshStandardMaterial({ color: new THREE.Color(0.80, 0.58, 0.28), map: T.brass.map, roughnessMap: T.brass.roughnessMap, normalMap: T.brass.normalMap, roughness: 1, metalness: 1, vertexColors: true, envMapIntensity: 1.0 });
  M.brassDull = new THREE.MeshStandardMaterial({ color: new THREE.Color(0.62, 0.45, 0.22), map: T.brass.map, roughnessMap: T.brass.roughnessMap, roughness: 1.4, metalness: 1, vertexColors: true });
  M.kick = new THREE.MeshStandardMaterial({ color: 0x0b0a09, roughness: 0.5, metalness: 0.0, vertexColors: true });
  M.plaster = new THREE.MeshStandardMaterial({ map: T.plaster.map, normalMap: T.plaster.normalMap, roughness: 0.95, vertexColors: true });
  M.tufted = new THREE.MeshPhysicalMaterial({ map: T.tufted.map, normalMap: T.tufted.normalMap, roughness: 0.8, sheen: 0.25, sheenRoughness: 0.6, sheenColor: new THREE.Color(0.30, 0.34, 0.40), vertexColors: true, color: new THREE.Color(0.86, 0.95, 1.15) });
  M.leafEdge = new THREE.MeshStandardMaterial({ color: 0x16181b, roughness: 0.7, vertexColors: true });
  M.wood = new THREE.MeshPhysicalMaterial({ map: T.wood.map, roughnessMap: T.wood.roughnessMap, normalMap: T.wood.normalMap, roughness: 1, clearcoat: 0.3, clearcoatRoughness: 0.4, vertexColors: true, normalScale: new THREE.Vector2(0.3, 0.3) });
  M.blackGloss = new THREE.MeshStandardMaterial({ color: 0x060606, roughness: 0.28, metalness: 0.1, vertexColors: true });
  M.chrome = new THREE.MeshStandardMaterial({ color: 0xe6e6e6, metalness: 1, roughness: 1, roughnessMap: T.chrome.roughnessMap, vertexColors: true, envMapIntensity: 1.0 });
  M.belt = new THREE.MeshStandardMaterial({ color: 0x0b0b0c, roughness: 0.6, metalness: 0.0, vertexColors: true, side: THREE.DoubleSide });
  M.reveal = new THREE.MeshStandardMaterial({ color: 0x121214, normalMap: T.velvet.normalMap, roughness: 0.9, vertexColors: true });
  M.ledStrip = new THREE.MeshBasicMaterial({ color: kelvin(3100).multiplyScalar(40), vertexColors: true });
  M.downlightLens = new THREE.MeshBasicMaterial({ color: kelvin(3300).multiplyScalar(24), vertexColors: true });
  M.fixtureTrim = new THREE.MeshStandardMaterial({ color: 0xc8c8c4, roughness: 0.4, metalness: 0.5, vertexColors: true });
  M.tablet = new THREE.MeshBasicMaterial({ map: tabletTexture(renderer), color: new THREE.Color(0.55, 0.6, 0.7), vertexColors: true });
  M.label = new THREE.MeshStandardMaterial({ color: 0xe8e8e2, roughness: 0.6, vertexColors: true });
  for (const k of ['ledStrip', 'downlightLens', 'tablet']) M[k].userData.castShadow = false;
  M.carpet.userData.castShadow = false;
  M.plaster.userData.castShadow = false;
  // baked LED wash on the room surfaces
  addWashShader(M.carpet, 'floor');
  addWashShader(M.fabric, 'wall');
  addWashShader(M.backing, 'wall');
  addWashShader(M.kick, 'wall', 0.6);
  addWashShader(M.plaster, 'ceil');
  addWashShader(M.brass, 'wall', 0.35);
  addWashShader(M.brassDull, 'wall', 0.35);
  addWashShader(M.reveal, 'other');
  addWashShader(M.tufted, 'other');
  addWashShader(M.leafEdge, 'other');
  addWashShader(M.wood, 'other');
  addWashShader(M.chrome, 'other', 0.15);

  const batch = new Batch();

  // ---------------- wall frames
  const frames = WALLS.map((w) => segFrame(w.a, w.b));
  const PANEL_T = 0.025;     // fabric panel thickness (proud of the wall line)
  const KICK_H = 0.1;
  const wallAO = (y) => 1 - 0.30 * Math.exp(-y / 0.25) - 0.30 * Math.exp(-(CEIL - y) / 0.2);

  // LED strips (positions for the bake and for small real-time fills)
  const leds = [];
  WALLS.forEach((w, i) => {
    for (const j of w.joints) if (j.type === 'led') {
      const f = frames[i];
      const p = f.origin.clone().addScaledVector(f.t, j.at);
      const wt = LED_WEIGHTS[`${i}:${j.at}`] || [0.8, 0.8];
      leds.push({ p, tA: f.t.clone().negate(), nA: f.n.clone(), tB: f.t.clone(), nB: f.n.clone(), wA: wt[0], wB: wt[1], corner: false });
    }
  });
  for (const [k, type] of Object.entries(CORNERS)) {
    if (type !== 'led') continue;
    const i = Number(k);
    const fA = frames[i], fB = frames[i + 1];
    const p = new THREE.Vector3(WALLS[i].b[0], 0, WALLS[i].b[1]);
    const wt = LED_WEIGHTS['c' + i] || [0.8, 0.8];
    leds.push({ p, tA: fA.t.clone().negate(), nA: fA.n.clone(), tB: fB.t.clone(), nB: fB.n.clone(), wA: wt[0], wB: wt[1], corner: true, bis: fA.n.clone().add(fB.n).normalize() });
  }
  const ledColor = kelvin(3000);
  const LED_I = 9.0; // wash strength (linear radiance multiplier on albedo)

  // Analytic LED wash (irradiance-like, artist-shaped from the reference).
  function wash(P, N, kind, out) {
    let e = 0;
    for (const L of leds) {
      const dx = P.x - L.p.x, dz = P.z - L.p.z;
      const dh = Math.hypot(dx, dz);
      if (dh > 6) continue;
      // which side of the strip / which wall the receiver is on
      const onA = dx * L.tA.x + dz * L.tA.z > 0;
      const w = onA ? L.wA : L.wB;
      if (kind === 'wall') {
        const nW = onA ? L.nA : L.nB;
        const facing = N.x * nW.x + N.z * nW.z;
        // receiver must be on (or parallel to) the lit wall and in front of the strip line
        if (facing < 0.6) { // side faces of trims/panels: weaker
          const toL = -(dx * N.x + dz * N.z);
          if (toL <= 0) continue;
          e += w * 0.6 * Math.exp(-dh / 0.25) * toL / (dh + 1e-3);
          continue;
        }
        const along = Math.abs(dx * (onA ? L.tA.x : L.tB.x) + dz * (onA ? L.tA.z : L.tB.z));
        const off = Math.abs(dx * nW.x + dz * nW.z);
        if (off > 0.3) continue;
        const y = P.y;
        const vert = (0.55 + 0.45 * smooth(0.0, 0.6, y)) * (1 - 0.25 * smooth(2.4, 3.25, y));
        e += w * (2.4 * Math.exp(-along / 0.06) + 1.0 * Math.exp(-along / 0.28) + 0.035 * Math.exp(-along / 1.2)) * vert;
      } else if (kind === 'floor') {
        const nAvg = L.corner ? L.bis : L.nA;
        const front = dx * nAvg.x + dz * nAvg.z;
        if (front < -0.05) continue;
        // elongated along the wall
        const tA = L.corner ? new THREE.Vector3(-nAvg.z, 0, nAvg.x) : L.tA;
        const al = dx * tA.x + dz * tA.z;
        const r2 = (al * al) / (1.0 * 1.0) + (front * front) / (0.7 * 0.7);
        e += (0.32 * Math.exp(-r2) + 0.02 * Math.exp(-dh / 0.8)) * (0.5 + 0.5 * w);
      } else if (kind === 'ceil') {
        e += 0.14 * Math.exp(-dh / 0.35) + 0.03 * Math.exp(-dh / 1.5);
      } else {
        // other objects near a strip (podium, leaves, chrome): soft fill if facing it
        const toL = -(dx * N.x + dz * N.z) / (dh + 1e-3);
        if (toL <= 0) continue;
        e += w * 0.06 * Math.exp(-dh / 0.9) * toL;
      }
    }
    out[0] = e * ledColor.r * LED_I; out[1] = e * ledColor.g * LED_I; out[2] = e * ledColor.b * LED_I;
  }

  // ---------------- floor (subdivided: baked AO, wear and LED pools in vertex data)
  {
    const x0 = -4.7, x1 = 5.1, z0 = -5.35, z1 = 4.8;
    const nx = 120, nz = 124;
    const g = new THREE.PlaneGeometry(x1 - x0, z1 - z0, nx, nz);
    g.rotateX(-Math.PI / 2);
    g.translate((x0 + x1) / 2, 0, (z0 + z1) / 2);
    const p = g.attributes.position, uv = g.attributes.uv;
    const col = new Float32Array(p.count * 3);
    const segs = WALLS.map((w) => [w.a, w.b]);
    const distSeg = (x, z, a, b) => {
      const vx = b[0] - a[0], vz = b[1] - a[1];
      const t = Math.max(0, Math.min(1, ((x - a[0]) * vx + (z - a[1]) * vz) / (vx * vx + vz * vz)));
      return Math.hypot(x - a[0] - vx * t, z - a[1] - vz * t);
    };
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), z = p.getZ(i);
      uv.setXY(i, x, -z);
      let d = 9;
      for (const [a, b] of segs) d = Math.min(d, distSeg(x, z, a, b));
      if (Math.abs(x) < 1.3 && z < WALL_Z + 0.1) d = 9 - 8 * smooth(1.0, 1.3, Math.abs(x));
      let ao = 1 - 0.45 * Math.exp(-d / 0.12) - 0.15 * Math.exp(-d / 0.5);
      // traffic wear: pile slightly crushed / lighter along the main path to the door
      const path = Math.exp(-Math.pow(x / 1.4, 2)) * (z < -0.5 ? 1 : Math.exp(-(z + 0.5) / 2.5));
      const mott = 0.07 * smoothNoise1(11, x * 0.7 + 3.1) + 0.05 * smoothNoise1(12, z * 0.6 + 7.7);
      ao *= 1 + 0.06 * path + mott;
      if (z < WALL_Z) ao *= 0.6; // inside the door recess
      col[i * 3] = ao; col[i * 3 + 1] = ao * (1 - 0.015 * path); col[i * 3 + 2] = ao * (1 - 0.02 * path);
    }
    g.setAttribute('color', new THREE.BufferAttribute(col, 3));
    batch.add(M.carpet, g, null, 'floor');
  }

  // ---------------- walls
  const addPanel = (f, s0, s1, y0, y1) => {
    const w = s1 - s0, h = y1 - y0;
    if (w <= 0.005 || h <= 0.005) return;
    const geo = boxGeo(w, h, PANEL_T, { segX: Math.max(2, Math.ceil(w / 0.05)), segY: 18, ao: (x, y) => wallAO(y + y0 + h / 2) });
    const uv = geo.attributes.uv, pos = geo.attributes.position;
    const u0 = s0 + f.origin.x * 3.7 + f.origin.z * 1.3; // decorrelate panels
    for (let i = 0; i < uv.count; i++) uv.setXY(i, pos.getX(i) + w / 2 + u0, pos.getY(i) + y0 + h / 2);
    batch.add(M.fabric, geo, frameMatrix(f, (s0 + s1) / 2, PANEL_T / 2, y0 + h / 2), 'wall');
  };
  const addBrassV = (f, s, y0, y1, width = 0.03, proud = 0.012, mat = M.brass, base = PANEL_T) => {
    const h = y1 - y0;
    batch.add(mat, boxGeo(width, h, proud, { uvMode: 'yx', segY: 12 }), frameMatrix(f, s, base + proud / 2 - 0.002, y0 + h / 2), 'wall');
  };
  const addBrassH = (f, s0, s1, y, height, proud, mat = M.brass) => {
    const w = s1 - s0;
    batch.add(mat, boxGeo(w, height, proud, { segX: Math.max(1, Math.ceil(w / 0.1)) }), frameMatrix(f, (s0 + s1) / 2, proud / 2, y), 'wall');
  };
  const addKick = (f, s0, s1) => {
    const w = s1 - s0;
    if (w <= 0) return;
    batch.add(M.kick, boxGeo(w, KICK_H, PANEL_T + 0.012, { segX: Math.max(1, Math.ceil(w / 0.1)), ao: (x, y) => 0.7 + 0.3 * Math.min(1, (y + KICK_H / 2) / KICK_H) }), frameMatrix(f, (s0 + s1) / 2, (PANEL_T + 0.012) / 2, KICK_H / 2), 'wall');
    addBrassH(f, s0, s1, KICK_H + 0.005, 0.01, PANEL_T + 0.015, M.brassDull);
  };
  const addBacking = (f, s0, s1, y0 = 0, y1 = CEIL) => {
    const w = s1 - s0, h = y1 - y0;
    if (w <= 0) return;
    batch.add(M.backing, boxGeo(w, h, 0.02, { segX: Math.max(1, Math.ceil(w / 0.2)), ao: () => 0.5 }), frameMatrix(f, (s0 + s1) / 2, -0.01, y0 + h / 2), 'wall');
  };
  const addLed = (f, s, y0, y1) => {
    const h = y1 - y0;
    batch.add(M.ledStrip, boxGeo(0.02, h, 0.008), frameMatrix(f, s, PANEL_T + 0.002, y0 + h / 2));
    addBrassV(f, s - 0.019, y0, y1, 0.008, 0.008);
    addBrassV(f, s + 0.019, y0, y1, 0.008, 0.008);
  };

  WALLS.forEach((w, i) => {
    const f = frames[i];
    const joints = w.joints.map((j) => ({ s: j.at, type: j.type }));
    if (CORNERS[i - 1]) joints.push({ s: 0, type: CORNERS[i - 1], corner: true });
    if (CORNERS[i]) joints.push({ s: f.L, type: CORNERS[i], corner: true });
    joints.sort((p, q) => p.s - q.s);
    const cuts = [0, ...joints.map((j) => j.s).filter((s) => s > 0.001 && s < f.L - 0.001), f.L];
    let hole = null;
    if (w.door) hole = [-1.42 - w.a[0], 1.42 - w.a[0]];
    if (hole) {
      addBacking(f, 0, hole[0]); addBacking(f, hole[1], f.L); addBacking(f, hole[0], hole[1], DOOR.height + 0.12, CEIL);
    } else addBacking(f, 0, f.L);
    for (let k = 0; k < cuts.length - 1; k++) {
      const g0 = k > 0 ? 0.012 : (CORNERS[i - 1] === 'led' ? 0.02 : 0.0);
      const g1 = k < cuts.length - 2 ? 0.012 : (CORNERS[i] === 'led' ? 0.02 : 0.0);
      const s0 = cuts[k] + g0, s1 = cuts[k + 1] - g1;
      if (hole && s1 > hole[0] && s0 < hole[1]) {
        addPanel(f, s0, hole[0], KICK_H, CEIL);
        addPanel(f, hole[1], s1, KICK_H, CEIL);
        addPanel(f, hole[0], hole[1], DOOR.height + 0.12, CEIL);
        addKick(f, cuts[k], hole[0]);
        addKick(f, hole[1], cuts[k + 1]);
      } else {
        addPanel(f, s0, s1, KICK_H, CEIL);
        addKick(f, cuts[k], cuts[k + 1]);
      }
    }
    for (const j of joints) {
      if (j.type === 'trim') addBrassV(f, j.s, KICK_H, CEIL, 0.032, 0.014);
      if (j.type === 'led' && !j.corner) addLed(f, j.s, KICK_H + 0.015, CEIL - 0.03);
    }
  });
  // corner LED strips
  for (const L of leds) if (L.corner) {
    const h = CEIL - 0.03 - (KICK_H + 0.015);
    const xAxis = new THREE.Vector3().crossVectors(new THREE.Vector3(0, 1, 0), L.bis);
    const m = new THREE.Matrix4().makeBasis(xAxis, new THREE.Vector3(0, 1, 0), L.bis)
      .setPosition(L.p.clone().addScaledVector(L.bis, PANEL_T * 0.6).setY(KICK_H + 0.015 + h / 2));
    batch.add(M.ledStrip, boxGeo(0.024, h, 0.016), m);
  }

  // ---------------- door frame, recess, reveal, leaves
  {
    const proud = 0.012;
    const jambW = 0.1, headH = 0.12;
    const fz = WALL_Z + PANEL_T; // front of the panels
    // brass frame on the wall face, wrapping into the recess
    for (const sx of [-1, 1]) {
      batch.add(M.brass, boxGeo(jambW, DOOR.height + headH, proud, { uvMode: 'yx', segY: 10 }), new THREE.Matrix4().makeTranslation(sx * (DOOR.x1 + jambW / 2), (DOOR.height + headH) / 2, fz + proud / 2), 'wall');
      // recess side (brass lined) from the wall face back to the door plane
      const rd = fz - DOOR.z;
      batch.add(M.brassDull, boxGeo(rd, DOOR.height, 0.01, { uvMode: 'xy', segY: 8 }), new THREE.Matrix4().makeRotationY(sx < 0 ? Math.PI / 2 : -Math.PI / 2).setPosition(sx * (DOOR.x1 + 0.005), DOOR.height / 2, (fz + DOOR.z) / 2), 'other');
      // reveal lining (behind the door plane)
      batch.add(M.reveal, boxGeo(DOOR.reveal, DOOR.height, 0.02, { segY: 8 }), new THREE.Matrix4().makeRotationY(sx < 0 ? Math.PI / 2 : -Math.PI / 2).setPosition(sx * (DOOR.x1 + 0.01), DOOR.height / 2, DOOR.z - DOOR.reveal / 2), 'other');
    }
    batch.add(M.brass, boxGeo(2 * (DOOR.x1 + jambW), headH, proud, { segX: 20 }), new THREE.Matrix4().makeTranslation(0, DOOR.height + headH / 2, fz + proud / 2), 'wall');
    batch.add(M.brassDull, boxGeo(2 * DOOR.x1, fz - DOOR.z, 0.01, { segX: 10 }), new THREE.Matrix4().makeRotationX(Math.PI / 2).setPosition(0, DOOR.height + 0.005, (fz + DOOR.z) / 2), 'other');
    batch.add(M.reveal, boxGeo(2 * DOOR.x1, DOOR.reveal, 0.02, {}), new THREE.Matrix4().makeRotationX(Math.PI / 2).setPosition(0, DOOR.height + 0.01, DOOR.z - DOOR.reveal / 2), 'other');
    // threshold plate
    batch.add(M.brassDull, boxGeo(2 * DOOR.x1, 0.008, 0.1, {}), new THREE.Matrix4().makeTranslation(0, 0.004, DOOR.z - 0.05), 'other');

    // leaves: tufted panels, brass edge bands, vertical pull bars
    const LW = DOOR.leafWidth, LH = DOOR.height - 0.03, LT = 0.07;
    const leafGroup = new THREE.Group();
    leafGroup.name = 'doorLeaves';
    root.add(leafGroup);
    const buildLeaf = (side, angleDeg) => {
      const pivot = new THREE.Group();
      pivot.position.set(side * DOOR.x1, 0, DOOR.z + 0.04);
      const a = THREE.MathUtils.degToRad(angleDeg);
      pivot.rotation.y = side < 0 ? -a : a;
      pivot.updateMatrix();
      leafGroup.add(pivot);
      const dir = side < 0 ? 1 : -1; // leaf extends along local +x (left) or -x (right)
      const lb = new Batch();
      const cx = dir * LW / 2;
      lb.add(M.leafEdge, boxGeo(LW, LH, LT - 0.004, { segX: 6, segY: 12 }), new THREE.Matrix4().makeTranslation(cx, LH / 2 + 0.01, 0));
      for (const fs of [1, -1]) {
        const face = new THREE.PlaneGeometry(LW - 0.05, LH - 0.05, 8, 16);
        const m = new THREE.Matrix4().makeRotationY(fs > 0 ? 0 : Math.PI).setPosition(cx, LH / 2 + 0.01, fs * (LT / 2 + 0.001));
        lb.add(M.tufted, face, m);
        const bw = 0.024, bp = 0.006;
        lb.add(M.brass, boxGeo(LW, bw, bp, { segX: 8 }), new THREE.Matrix4().makeTranslation(cx, LH + 0.01 - bw / 2, fs * (LT / 2 + bp / 2)));
        lb.add(M.brass, boxGeo(LW, bw, bp, { segX: 8 }), new THREE.Matrix4().makeTranslation(cx, 0.01 + bw / 2, fs * (LT / 2 + bp / 2)));
        lb.add(M.brass, boxGeo(bw, LH, bp, { uvMode: 'yx', segY: 12 }), new THREE.Matrix4().makeTranslation(dir * bw / 2, LH / 2 + 0.01, fs * (LT / 2 + bp / 2)));
        lb.add(M.brass, boxGeo(bw, LH, bp, { uvMode: 'yx', segY: 12 }), new THREE.Matrix4().makeTranslation(dir * (LW - bw / 2), LH / 2 + 0.01, fs * (LT / 2 + bp / 2)));
        const bx = dir * (LW - 0.15);
        lb.add(M.brass, new THREE.CylinderGeometry(0.016, 0.016, 1.1, 14, 6), new THREE.Matrix4().makeTranslation(bx, 1.4, fs * (LT / 2 + 0.065)));
        for (const by of [0.92, 1.88]) {
          const st = new THREE.CylinderGeometry(0.009, 0.009, 0.065, 8);
          st.rotateX(Math.PI / 2);
          lb.add(M.brass, st, new THREE.Matrix4().makeTranslation(bx, by, fs * (LT / 2 + 0.033)));
        }
      }
      lb.add(M.brass, boxGeo(0.008, LH, LT + 0.014, { uvMode: 'yx', segY: 12 }), new THREE.Matrix4().makeTranslation(dir * (LW + 0.004), LH / 2 + 0.01, 0));
      lb.add(M.brass, boxGeo(LW, 0.008, LT + 0.014, { segX: 8 }), new THREE.Matrix4().makeTranslation(cx, LH + 0.014, 0));
      for (const hy of [0.25, 1.3, 2.35]) lb.add(M.brassDull, new THREE.CylinderGeometry(0.012, 0.012, 0.11, 10), new THREE.Matrix4().makeTranslation(0, hy, LT / 2 + 0.006));
      const mtx = new THREE.Matrix4().compose(pivot.position, pivot.quaternion, new THREE.Vector3(1, 1, 1));
      for (const mm of lb.build(pivot, { castShadow: true, wash, parentMatrix: mtx })) { mm.castShadow = true; mm.receiveShadow = true; }
    };
    buildLeaf(-1, DOOR.leafAngleL);
    buildLeaf(1, DOOR.leafAngleR);
  }

  // ---------------- podium + tablet
  {
    const ob = OBSTACLES[0];
    const W = ob.w, D = ob.d, Hf = 1.08, Hb = 1.15;
    const pb = new Batch();
    const pm = new THREE.Matrix4().makeTranslation(ob.cx, 0, ob.cz);
    pb.add(M.blackGloss, boxGeo(W - 0.03, 0.07, D - 0.03, {}), new THREE.Matrix4().makeTranslation(0, 0.035, 0));
    pb.add(M.wood, boxGeo(W, Hf - 0.12, D, { segX: 4, segY: 10, ao: (x, y) => 0.75 + 0.25 * Math.min(1, (y + (Hf - 0.12) / 2) / 0.45) }), new THREE.Matrix4().makeTranslation(0, 0.07 + (Hf - 0.12) / 2, 0));
    // shadow-gap + slim brass inlays on the front
    pb.add(M.brassDull, boxGeo(W - 0.06, 0.006, 0.004, {}), new THREE.Matrix4().makeTranslation(0, 0.93, D / 2 + 0.002));
    pb.add(M.blackGloss, boxGeo(W + 0.002, 0.012, D + 0.002, {}), new THREE.Matrix4().makeTranslation(0, Hf - 0.05, 0));
    const slope = Math.atan2(Hb - Hf, D);
    pb.add(M.wood, boxGeo(W + 0.04, 0.045, D + 0.07, { segX: 3 }), new THREE.Matrix4().makeRotationX(slope).setPosition(0, (Hf + Hb) / 2 - 0.02, 0));
    pb.add(M.wood, boxGeo(W + 0.04, 0.03, 0.025, {}), new THREE.Matrix4().makeTranslation(0, Hf + 0.008, D / 2 + 0.035));
    const tabM = new THREE.Matrix4().makeRotationX(slope).setPosition(-0.04, (Hf + Hb) / 2 + 0.008, 0.0);
    pb.add(M.blackGloss, boxGeo(0.27, 0.012, 0.2, {}), tabM);
    const scr = new THREE.PlaneGeometry(0.235, 0.165); scr.rotateX(-Math.PI / 2);
    pb.add(M.tablet, scr, tabM.clone().multiply(new THREE.Matrix4().makeTranslation(0, 0.0065, 0)));
    const card = new THREE.PlaneGeometry(0.07, 0.05); card.rotateX(-Math.PI / 2);
    pb.add(M.label, card, new THREE.Matrix4().makeRotationX(slope).setPosition(0.2, (Hf + Hb) / 2 + 0.004, -0.09));
    const pg = new THREE.Group(); pg.name = 'podium';
    pg.position.set(ob.cx, 0, ob.cz); pg.updateMatrix();
    root.add(pg);
    for (const mm of pb.build(pg, { castShadow: true, wash, parentMatrix: pm })) mm.castShadow = mm.material !== M.tablet;
  }

  // ---------------- stanchions + belts
  {
    const posts = OBSTACLES.filter((o) => o.name.startsWith('stanchion'));
    const sb = new Batch();
    const H = 0.97;
    const heads = [];
    for (const o of posts) {
      const m = new THREE.Matrix4().makeTranslation(o.x, 0, o.z);
      const at = (y) => m.clone().multiply(new THREE.Matrix4().makeTranslation(0, y, 0));
      sb.add(M.chrome, new THREE.CylinderGeometry(0.15, 0.17, 0.02, 48), at(0.01));
      const cap = Math.PI * 0.17;
      sb.add(M.chrome, new THREE.SphereGeometry(0.15, 48, 6, 0, Math.PI * 2, 0, cap), at(0.02 - 0.15 * Math.cos(cap)));
      sb.add(M.chrome, new THREE.CylinderGeometry(0.04, 0.055, 0.03, 32), at(0.04));
      sb.add(M.chrome, new THREE.CylinderGeometry(0.031, 0.031, H - 0.15, 32), at(0.055 + (H - 0.15) / 2));
      sb.add(M.chrome, new THREE.CylinderGeometry(0.043, 0.038, 0.14, 32), at(H - 0.075));
      sb.add(M.chrome, new THREE.CylinderGeometry(0.03, 0.043, 0.02, 32), at(H + 0.004));
      sb.add(M.blackGloss, new THREE.CylinderGeometry(0.027, 0.027, 0.006, 24), at(H + 0.015));
      heads.push(new THREE.Vector3(o.x, H - 0.07, o.z));
    }
    const ribbon = (p0, p1) => {
      const n = 20, wBelt = 0.05;
      const pos = [], idx = [], nor = [], uvs = [];
      const dir = p1.clone().sub(p0); const len = dir.length(); dir.normalize();
      const side = new THREE.Vector3(-dir.z, 0, dir.x);
      for (let i = 0; i <= n; i++) {
        const t = i / n;
        const p = p0.clone().lerp(p1, t).addScaledVector(dir, (t - 0.5) * -0.08);
        p.y -= 0.03 * Math.sin(Math.PI * t) * (len / 1.5);
        for (const s of [-1, 1]) {
          pos.push(p.x, p.y + s * wBelt / 2, p.z);
          nor.push(side.x, 0, side.z);
          uvs.push(t * len, s * 0.5 + 0.5);
        }
        if (i < n) { const b = i * 2; idx.push(b, b + 1, b + 2, b + 1, b + 3, b + 2); }
      }
      const g = new THREE.BufferGeometry();
      g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
      g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
      g.setAttribute('uv', new THREE.Float32BufferAttribute(uvs, 2));
      g.setIndex(idx);
      return g;
    };
    sb.add(M.belt, ribbon(heads[0], heads[1]));
    sb.add(M.belt, ribbon(heads[1], heads[2]));
    for (const mm of sb.build(root, { castShadow: true, wash })) mm.castShadow = true;
  }

  // ---------------- ceiling + downlights
  // Fixtures at (-2.76,-1.85) and (1.47,1.46) are the two visible in look_ref.jpg.
  const DOWNLIGHTS = [
    { x: -1.45, z: -3.55, power: 0.85, beam: 30, pen: 0.85, shadow: true },
    { x: 1.05, z: -3.7, power: 0.85, beam: 30, pen: 0.85, shadow: true },
    { x: -2.76, z: -1.85, power: 0.5, beam: 46, pen: 0.9, shadow: true },
    { x: 2.62, z: -2.4, power: 0.55, beam: 46, pen: 0.9, shadow: true },
    { x: 1.47, z: 1.46, power: 0.5, beam: 52, pen: 1.0, shadow: false },
    { x: -1.75, z: 1.2, power: 0.45, beam: 52, pen: 1.0, shadow: false },
    { x: 0.2, z: -1.0, power: 0.4, beam: 55, pen: 1.0, shadow: false },
  ];
  {
    const g = new THREE.PlaneGeometry(10.4, 10.4, 64, 64);
    g.rotateX(Math.PI / 2);
    g.translate(0.2, CEIL, -0.2);
    const uv = g.attributes.uv, p = g.attributes.position;
    for (let i = 0; i < p.count; i++) uv.setXY(i, p.getX(i), p.getZ(i));
    batch.add(M.plaster, g, null, 'ceil');
    for (const d of DOWNLIGHTS) {
      batch.add(M.fixtureTrim, new THREE.CylinderGeometry(0.075, 0.075, 0.01, 32), new THREE.Matrix4().makeTranslation(d.x, CEIL - 0.005, d.z));
      const lens = new THREE.CircleGeometry(0.05, 24); lens.rotateX(Math.PI / 2);
      batch.add(M.downlightLens, lens, new THREE.Matrix4().makeTranslation(d.x, CEIL - 0.011, d.z));
    }
  }

  batch.build(root, { receiveShadow: true, wash });

  // ---------------- real-time lights
  const lights = new THREE.Group(); lights.name = 'lights'; root.add(lights);
  const warm = kelvin(3000);
  const spots = [];
  for (const d of DOWNLIGHTS) {
    const s = new THREE.SpotLight(warm, 38 * d.power, 10, THREE.MathUtils.degToRad(d.beam), d.pen, 2);
    s.position.set(d.x, CEIL - 0.04, d.z);
    s.target.position.set(d.x, 0, d.z + 0.02);
    s.castShadow = d.shadow;
    if (d.shadow) {
      s.shadow.mapSize.set(1024, 1024);
      s.shadow.bias = -0.0005;
      s.shadow.normalBias = 0.02;
      s.shadow.camera.near = 0.3; s.shadow.camera.far = 6;
      s.shadow.radius = 3;
    }
    lights.add(s, s.target);
    spots.push(s);
  }
  // small non-shadow fills at the LED strips so people walking past pick up the warm light
  for (const L of leds) {
    const n = L.corner ? L.bis : L.nA;
    const pl = new THREE.PointLight(ledColor, 0.5, 2.5, 2);
    pl.position.copy(L.p).addScaledVector(n, 0.25).setY(1.5);
    lights.add(pl);
  }
  // cool spill from the auditorium screen through the doorway (sky-like soft fill from the opening)
  const doorSpill = new THREE.SpotLight(new THREE.Color(0.42, 0.55, 1.0), 0.8, 8, THREE.MathUtils.degToRad(60), 1.0, 2);
  doorSpill.position.set(0, 2.2, DOOR.z - 1.2);
  doorSpill.target.position.set(0, 0, DOOR.z + 2.5);
  lights.add(doorSpill, doorSpill.target);
  const tabletLight = new THREE.PointLight(new THREE.Color(0.7, 0.8, 1.0), 0.03, 0.8, 2);
  tabletLight.position.set(OBSTACLES[0].cx, 1.3, OBSTACLES[0].cz);
  lights.add(tabletLight);
  const hemi = new THREE.HemisphereLight(new THREE.Color(0.32, 0.27, 0.22), new THREE.Color(0.20, 0.07, 0.05), 0.012);
  lights.add(hemi);

  // ---------------- auditorium (unlit, baked)
  const aud = buildAuditorium(renderer);
  root.add(aud.group);

  // ---------------- camera
  const camera = new THREE.PerspectiveCamera(CAMERA.fov, 16 / 9, CAMERA.near, CAMERA.far);
  camera.position.set(...CAMERA.position);
  camera.rotation.set(-CAMERA.pitch, CAMERA.yaw, CAMERA.roll, 'YXZ');
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);

  // ---------------- image-based light from the room itself (bounce + reflections)
  if (renderer) {
    scene.updateMatrixWorld(true);
    const cubeRT = new THREE.WebGLCubeRenderTarget(128, { type: THREE.HalfFloatType });
    const cubeCam = new THREE.CubeCamera(0.05, 30, cubeRT);
    cubeCam.position.set(2.4, 1.2, -2.2);
    scene.add(cubeCam);
    scene.environment = null;
    cubeCam.update(renderer, scene);
    scene.remove(cubeCam);
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envRT = pmrem.fromCubemap(cubeRT.texture);
    pmrem.dispose();
    cubeRT.dispose();
    scene.environment = envRT.texture;
    scene.environmentIntensity = 0.22;
    // polished metals see the room more strongly than the diffuse bounce
    M.chrome.envMap = envRT.texture; M.chrome.envMapIntensity = 0.9;
    M.brass.envMap = envRT.texture; M.brass.envMapIntensity = 0.7;
  }

  function update(t) {
    // projector light breathes with the pre-show content; pure function of t
    const f = 0.9 + 0.07 * smoothNoise1(501, t * 0.45) + 0.03 * smoothNoise1(502, t * 2.3);
    aud.setScreen(f);
    doorSpill.intensity = 0.8 * f;
  }
  update(0);

  return { camera, update, lights: { spots, doorSpill }, materials: M, root, leds };
}

// ---------------------------------------------------------------------------
// Auditorium: unlit, baked vertex colours (linear radiance), so corridor lights
// never affect it. Landing just inside the door, a long aisle with shallow steps
// and warm step lights, seat rows both sides, the screen at the far end.

function buildAuditorium(renderer) {
  const group = new THREE.Group();
  group.name = 'auditorium';
  const zDoor = DOOR.z - DOOR.reveal; // -5.3
  // stadium seating entered from the top/back: a cross-aisle landing, then
  // rows stepping gently down toward the screen
  const landingEnd = -7.4;
  const rows = 12, rowD = 1.0, drop = 0.1;
  const aisleHalf = 0.62;
  const frontZ = landingEnd - rows * rowD;          // -19.4
  const frontY = -rows * drop;                       // -1.2
  const screenZ = -21.0, screenY0 = -0.5, screenH = 3.7, screenW = 6.6;
  const roomHalf = 7.0;
  const rnd = mulberry32(4711);

  const basic = (opts) => new THREE.MeshBasicMaterial({ vertexColors: true, ...opts });
  const M = {
    floor: basic({ color: 0xffffff }),
    seat: basic({ color: 0xffffff }),
    wall: basic({ color: 0xffffff }),
    stepLight: new THREE.MeshBasicMaterial({ color: new THREE.Color(1.0, 0.55, 0.2).multiplyScalar(6) }),
    glow: new THREE.MeshBasicMaterial({ map: glowTexture(), color: new THREE.Color(0.9, 0.42, 0.14).multiplyScalar(0.16), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }),
    screen: new THREE.MeshBasicMaterial({ map: screenTexture(renderer), color: new THREE.Color(1, 1, 1).multiplyScalar(0.42) }),
  };
  const b = new Batch();
  const colorize = (g, fn) => {
    const p = g.attributes.position;
    const c = new Float32Array(p.count * 3);
    const v = new THREE.Vector3();
    for (let i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i);
      const col = fn(v);
      c[i * 3] = col[0]; c[i * 3 + 1] = col[1]; c[i * 3 + 2] = col[2];
    }
    g.setAttribute('color', new THREE.BufferAttribute(c, 3));
    return g;
  };
  // baked radiance: faint blue from the screen, a little corridor light near the door
  const S = 0.0018;
  const lightAt = (x, z) => {
    const s = S * (0.5 + 0.5 * Math.exp(-(z - screenZ) / 6));
    const nd = 0.008 * Math.exp(-(zDoor - z) / 0.8) * Math.exp(-Math.abs(x) / 1.2);
    return [s * 0.55 + nd, s * 0.75 + nd * 0.62, s * 1.3 + nd * 0.45];
  };

  {
    const lg = new THREE.PlaneGeometry(2 * roomHalf, zDoor - landingEnd, 40, 16);
    lg.rotateX(-Math.PI / 2);
    lg.translate(0, 0, (zDoor + landingEnd) / 2);
    colorize(lg, (v) => lightAt(v.x, v.z));
    b.add(M.floor, lg);
    for (let k = 0; k < rows; k++) {
      const z0 = landingEnd - k * rowD, z1 = z0 - rowD, y = -(k + 1) * drop;
      const tg = new THREE.PlaneGeometry(2 * roomHalf, rowD, 40, 4);
      tg.rotateX(-Math.PI / 2);
      tg.translate(0, y, (z0 + z1) / 2);
      colorize(tg, (v) => {
        const l = lightAt(v.x, v.z);
        const inA = Math.abs(v.x) < aisleHalf ? 1 : 0;
        // warm pools from the step lights on the aisle treads, nosing edge a touch lighter
        const pool = inA * (Math.exp(-Math.pow((v.z - (z0 - 0.15)) / 0.25, 2)) * Math.exp(-Math.pow((Math.abs(v.x) - aisleHalf) / 0.3, 2))) * 0.006;
        const nose = inA * (v.z > z0 - 0.04 ? 0.0012 : 0);
        return [l[0] + pool + nose, l[1] + pool * 0.5 + nose * 0.8, l[2] + pool * 0.2 + nose * 0.8];
      });
      b.add(M.floor, tg);
      // riser drops away from the camera (faces the screen): not visible, skip
      for (const sx of [-1, 1]) {
        // step light on the seat end standard, facing the aisle
        b.add(M.stepLight, new THREE.BoxGeometry(0.012, 0.025, 0.045), new THREE.Matrix4().makeTranslation(sx * (aisleHalf + 0.004), y + 0.13, z0 - 0.12));
        const pool = new THREE.PlaneGeometry(0.4, 0.4); pool.rotateX(-Math.PI / 2);
        b.add(M.glow, pool, new THREE.Matrix4().makeTranslation(sx * (aisleHalf - 0.1), y + 0.004, z0 - 0.14));
        const halo = new THREE.PlaneGeometry(0.16, 0.16);
        b.add(M.glow, halo, new THREE.Matrix4().makeTranslation(sx * (aisleHalf - 0.01), y + 0.13, z0 - 0.1));
      }
      // aisle-end standards (dark panels at each row end, catch a little step light)
      for (const sx of [-1, 1]) {
        const st = new THREE.BoxGeometry(0.06, 0.95, 0.6);
        st.translate(sx * (aisleHalf + 0.03), y + 0.475, z0 - 0.4);
        b.add(M.floor, colorize(st, (v) => [0.0025 + 0.004 * Math.exp(-Math.abs(v.y - y - 0.13) / 0.2), 0.002 + 0.002 * Math.exp(-Math.abs(v.y - y - 0.13) / 0.2), 0.002]));
      }
    }
    const fg = new THREE.PlaneGeometry(2 * roomHalf, frontZ - screenZ + 0.2, 20, 4);
    fg.rotateX(-Math.PI / 2);
    fg.translate(0, frontY, (frontZ + screenZ) / 2);
    colorize(fg, (v) => { const l = lightAt(v.x, v.z); return [l[0] * 1.6, l[1] * 1.6, l[2] * 1.6]; });
    b.add(M.floor, fg);
  }

  // seats (instanced): dark velour backs, top edges catch a little screen light
  {
    const parts = [];
    const back = new THREE.BoxGeometry(0.52, 0.72, 0.12, 1, 4, 1); back.translate(0, 0.36, 0); back.rotateX(0.14); back.translate(0, 0.36, 0.22);
    const head = new THREE.CylinderGeometry(0.06, 0.06, 0.52, 10); head.rotateZ(Math.PI / 2); head.translate(0, 1.08, 0.31);
    const cushion = new THREE.BoxGeometry(0.5, 0.14, 0.48); cushion.translate(0, 0.44, -0.02);
    const armL = new THREE.BoxGeometry(0.07, 0.22, 0.55); armL.translate(-0.29, 0.62, 0.0);
    const armR = armL.clone(); armR.translate(0.58, 0, 0);
    const stand = new THREE.BoxGeometry(0.07, 0.4, 0.42); stand.translate(-0.29, 0.2, 0.0);
    parts.push(back, head, cushion, armL, armR, stand);
    for (const p of parts) colorize(p, (v) => {
      const up = Math.max(0, Math.min(1, (v.y - 1.0) / 0.12));
      return [0.0024 + 0.0030 * up, 0.0017 + 0.0050 * up, 0.0019 + 0.0095 * up];
    });
    const seatGeo = mergeGeometries(parts.map((g) => { g.deleteAttribute('uv'); return g; }), false);
    const xs = [];
    for (let x = aisleHalf + 0.36; x < roomHalf - 0.4; x += 0.56) xs.push(x);
    const inst = new THREE.InstancedMesh(seatGeo, M.seat, rows * xs.length * 2);
    const m = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(1, 1, 1), pos = new THREE.Vector3();
    const up = new THREE.Vector3(0, 1, 0);
    let i = 0;
    for (let k = 0; k < rows; k++) {
      const z = landingEnd - k * rowD - 0.32, y = -(k + 1) * drop;
      for (const sx of [-1, 1]) for (const x of xs) {
        pos.set(sx * x, y, z);
        q.setFromAxisAngle(up, (rnd() - 0.5) * 0.03);
        m.compose(pos, q, s);
        inst.setMatrixAt(i++, m);
      }
    }
    inst.instanceMatrix.needsUpdate = true;
    group.add(inst);
  }

  // shell: side walls, ceiling, screen wall with masking
  {
    const wallCol = (v) => { const l = lightAt(v.x, v.z); return [l[0] * 0.45, l[1] * 0.45, l[2] * 0.45]; };
    for (const sx of [-1, 1]) {
      const g = new THREE.PlaneGeometry(zDoor - screenZ + 1, 9, 20, 4);
      g.rotateY(sx < 0 ? Math.PI / 2 : -Math.PI / 2);
      g.translate(sx * roomHalf, 3.0, (zDoor + screenZ) / 2);
      b.add(M.wall, colorize(g, wallCol));
    }
    const ceil = new THREE.PlaneGeometry(2 * roomHalf, zDoor - screenZ + 1, 8, 8);
    ceil.rotateX(Math.PI / 2); ceil.translate(0, 7, (zDoor + screenZ) / 2);
    b.add(M.wall, colorize(ceil, () => [0.0003, 0.0003, 0.0005]));
    const sw = new THREE.PlaneGeometry(2 * roomHalf, 10, 16, 8);
    sw.translate(0, 3, screenZ - 0.05);
    // masking wall around the screen picks up the screen's own light
    colorize(sw, (v) => {
      const dx = Math.max(0, Math.abs(v.x) - screenW / 2), dy = Math.max(0, screenY0 - v.y, v.y - (screenY0 + screenH));
      const k = Math.exp(-Math.hypot(dx, dy) / 0.8);
      return [0.0008 + 0.004 * k, 0.001 + 0.006 * k, 0.002 + 0.012 * k];
    });
    b.add(M.wall, sw);
  }

  const screenMesh = new THREE.Mesh(new THREE.PlaneGeometry(screenW, screenH), M.screen);
  screenMesh.position.set(0, screenY0 + screenH / 2, screenZ);
  group.add(screenMesh);

  b.build(group, { castShadow: false, receiveShadow: false });
  group.traverse((o) => { if (o.isMesh) { o.castShadow = false; o.receiveShadow = false; } });

  const baseScreen = M.screen.color.clone();
  return {
    group,
    setScreen(f) {
      M.screen.color.copy(baseScreen).multiplyScalar(f);
      M.seat.color.setScalar(0.8 + 0.2 * f);
      M.wall.color.setScalar(0.75 + 0.25 * f);
      M.floor.color.setScalar(0.85 + 0.15 * f);
    },
  };
}

// ---------------------------------------------------------------------------
// projection helper: world point -> 1920x1080 image px (camera projection + lens)
// Returns [NaN, NaN] for points behind the camera.

const _p = new THREE.Vector3();
export function projectToImage(camera, v) {
  if (Array.isArray(v)) _p.set(v[0], v[1], v[2]); else _p.copy(v);
  _p.applyMatrix4(camera.matrixWorldInverse);
  if (_p.z > -1e-4) return [NaN, NaN];
  _p.applyMatrix4(camera.projectionMatrix);
  const [dx, dy] = distortNdc(_p.x, _p.y);
  return [(dx + 1) * 0.5 * 1920, (1 - dy) * 0.5 * 1080];
}

export { hash2 };
