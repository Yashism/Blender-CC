// Procedural walk / idle for the people rig. Pure function of (phase, speed, turnRate, t).
//
// Foot model (per foot, local phase p, heel strike at p = 0):
//   [0, pFF)     heel rocker: rotate about the heel contact point (fixed in world)
//   [pFF, pHO)   foot flat (fixed in world)
//   [pHO, beta)  forefoot rocker: rotate about the MTP (ball) joint; toes stay flat
//   [beta, 1)    swing: Hermite path from toe-off to the next heel strike + clearance lift
// The root advances `k S` metres per cycle (k = stride factor: people shorten their stride
// when they slow down), so a planted point moves backwards relative to the root at exactly
// k S per unit phase -> no foot sliding when the crowd advances the phase at speed / (k S).
// Pelvis height comes from the legs' reach each frame (soft-min of what both legs allow),
// capped so the bob is 2-4 cm and the stance knee keeps a natural flex.
import * as THREE from 'three';
import { clamp, lerp, smooth } from './human_geo.js';
import { smoothNoise1 } from './rng.js';

const TAU = Math.PI * 2;

export const BONES = ['root', 'pelvis', 'spine', 'chest', 'neck', 'head',
  'clavL', 'upperArmL', 'forearmL', 'handL', 'clavR', 'upperArmR', 'forearmR', 'handR',
  'thighL', 'shinL', 'footL', 'toeL', 'thighR', 'shinR', 'footR', 'toeR', 'tail', 'drape', 'bag'];
export const BI = Object.fromEntries(BONES.map((n, i) => [n, i]));
export const PARENT = {
  pelvis: 'root', spine: 'pelvis', chest: 'spine', neck: 'chest', head: 'neck',
  clavL: 'chest', upperArmL: 'clavL', forearmL: 'upperArmL', handL: 'forearmL',
  clavR: 'chest', upperArmR: 'clavR', forearmR: 'upperArmR', handR: 'forearmR',
  thighL: 'pelvis', shinL: 'thighL', footL: 'shinL', toeL: 'footL',
  thighR: 'pelvis', shinR: 'thighR', footR: 'shinR', toeR: 'footR',
  tail: 'head', drape: 'chest', bag: 'chest',
};

const _q = new THREE.Quaternion();
const _q2 = new THREE.Quaternion();
const _v = new THREE.Vector3();
const _v2 = new THREE.Vector3();
const _m = new THREE.Matrix4();
const AX = new THREE.Vector3(1, 0, 0), AY = new THREE.Vector3(0, 1, 0), AZ = new THREE.Vector3(0, 0, 1);
function qa(out, axis, ang) { return out.setFromAxisAngle(axis, ang); }
// Euler-like composition used for joints: Z (abduction) * X (flexion) * Y (twist)
function qzxy(out, z, x, y) {
  out.setFromAxisAngle(AZ, z);
  _q2.setFromAxisAngle(AX, x); out.multiply(_q2);
  _q2.setFromAxisAngle(AY, y); out.multiply(_q2);
  return out;
}
function smin(a, b, k) {
  const m = Math.min(a, b);
  return m - k * Math.log(Math.exp(-(a - m) / k) + Math.exp(-(b - m) / k));
}
function hermite(p0, p1, m0, m1, u) {
  const u2 = u * u, u3 = u2 * u;
  return (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (-2 * u3 + 3 * u2) * p1 + (u3 - u2) * m1;
}

export class Gait {
  // M: measurements (see humans.js), look: appearance (gait personality), rest: rest bone positions (Vector3[])
  constructor(M, look, rest) {
    this.M = M;
    this.look = look;
    this.rest = rest;
    this.child = look.child;
    const g = look.gait;
    this.g = g;
    this.Lt = rest[BI.thighL].distanceTo(rest[BI.shinL]);
    this.Ls = rest[BI.shinL].distanceTo(rest[BI.footL]);
    this.reach = (this.Lt + this.Ls) * 0.9985;
    this.hipX = rest[BI.thighL].x;
    this.restHip = rest[BI.pelvis].y;
    this.aH = M.ankleY;     // ankle height above the floor (foot flat)
    this.bH = M.ballH;      // MTP joint height
    this.hb = M.heelBack;   // ankle -> heel contact (horizontal)
    this.bf = M.ballF;      // ankle -> MTP joint (horizontal)
    this.tf = M.toeF;       // ankle -> toe tip
    this.footX = M.footX;
    this.toeOut = g.toeOut;
    this.beta = 0.61; this.pFF = 0.095; this.pHO = 0.33;
    this.thHS = 0.3; this.thTO = 0.98;
    const sc = M.H / 1.7;
    this.lift = 0.034 * sc;
    this.bobTarget = clamp(0.04 * sc * g.bob, 0.024, 0.044);
    this.swayA = 0.02 * sc * g.sway;
    this.yawP = 0.075; this.rollP = 0.055 * g.sway; this.yawT = 0.06;
    this.surgeA = 0.007 * sc;
    // full stride (at brisk walking speed): as long as possible while the pelvis does not
    // drop more than ~3.5% of leg length, so the stance knee stays nearly straight (no crouch)
    this._fw = { x: 0, y: 0, z: 0, pitch: 0, toe: 0, contact: 0 };
    this._k = 1;
    let S = M.H * (this.child ? 0.77 : 0.79);
    for (let it = 0; it < 16; it++) {
      this.S = S;
      this._solveOffset();
      const drop = this.restHip - this.minHip;
      if (drop < (this.Lt + this.Ls) * 0.035) break;
      S *= 0.97;
    }
    this.S = S;
    // swing endpoints / velocities (constant for this person)
    this._prepSwing();
    // walking pelvis cap (lowest allowed height + bob), per stride factor
    this.capK = [0.5, 0.65, 0.8, 0.9, 1.0, 1.06];
    this.capV = this.capK.map((k) => { this._k = k; this._solveCap(); return this.walkCap; });
    this._k = 1;
    this.walkCap = this.capV[4];
    this.out = {
      pelvisPos: new THREE.Vector3(),
      local: BONES.map(() => new THREE.Quaternion()),
      abs: BONES.map(() => new THREE.Quaternion()),
      ankle: [new THREE.Vector3(), new THREE.Vector3()],
      footYaw: [0, 0], footPitch: [0, 0], contact: [0, 0],
    };
  }

  // --------------------------------------------------------------- foot path
  // world-frame (root at z = S*p) sagittal foot state for local phase p in [0,1)
  _stance(p, o) {
    const hb = this.hb, bf = this.bf, aH = this.aH, bH = this.bH;
    const zH0 = this.hsOff * this._k;
    if (p < this.pFF) {
      const th = this.thHS * (1 - smooth(0, 1, p / this.pFF));
      const c = Math.cos(th), s = Math.sin(th);
      o.z = zH0 + hb * c - aH * s; o.y = hb * s + aH * c; o.pitch = th; o.toe = 0; o.contact = 1;
    } else if (p < this.pHO) {
      o.z = zH0 + hb; o.y = aH; o.pitch = 0; o.toe = 0; o.contact = 1;
    } else {
      const x = clamp((p - this.pHO) / (this.beta - this.pHO), 0, 1);
      const th = -this.thTO * Math.pow(x, 1.4);
      const c = Math.cos(th), s = Math.sin(th);
      const dz = -bf, dy = aH - bH;
      o.z = zH0 + hb + bf + dz * c - dy * s; o.y = bH + dz * s + dy * c; o.pitch = th; o.toe = -th; o.contact = 1;
    }
    return o;
  }
  _prepSwing() {
    const o = { z: 0, y: 0, pitch: 0, toe: 0, contact: 0 };
    const b = this.beta, d = 1e-4;
    const cy = Math.cos(this.toeOut), sy = Math.sin(this.toeOut);
    this._cy = cy; this._sy = sy;
    const k0 = this._k; this._k = 1;
    this._stance(b - d, o); const z1 = o.z, y1 = o.y;
    this._stance(b - 2 * d, o); const z0 = o.z, y0 = o.y;
    this._k = k0;
    // toe-off ankle (world, along-axis offset from the heel strike point rotated by toe-out)
    this.A0d = z1 - this.hsOff;
    this.A0y = y1;
    this.V0z = cy * (z1 - z0) / d; this.V0y = (y1 - y0) / d;
    const th = this.thHS;
    this.A1d = this.hb * Math.cos(th) - this.aH * Math.sin(th);
    this.A1y = this.hb * Math.sin(th) + this.aH * Math.cos(th);
  }
  // world-frame foot state (root at z = S*p). o.d = along-axis offset from the heel strike point.
  _foot(p, o) {
    const h0 = this.hsOff * this._k;
    if (p < this.beta) {
      this._stance(p, o);
      o.d = o.z - h0;
      o.z = h0 + this._cy * o.d;
      return o;
    }
    const u = (p - this.beta) / (1 - this.beta);
    const su = 1 - this.beta;
    const A0z = h0 + this._cy * this.A0d, A1z = h0 + this.S * this._k + this._cy * this.A1d;
    const span = A1z - A0z;
    o.z = hermite(A0z, A1z, this.V0z * su * 0.8, span * 0.12, u);
    const us = Math.pow(u, 0.8);
    o.y = hermite(this.A0y, this.A1y, this.V0y * su * 0.6, -0.04, u) + this.lift * 16 * us * us * (1 - us) * (1 - us);
    o.d = lerp(this.A0d, this.A1d, smooth(0, 1, u));
    o.pitch = -this.thTO * (1 - smooth(0, 0.55, u)) + this.thHS * smooth(0.5, 1, u) - 0.12 * Math.sin(Math.PI * u);
    o.toe = this.thTO * (1 - smooth(0, 0.3, u)) * 0.6;
    o.contact = 0;
    return o;
  }
  // root-relative ankle for side (0 L, 1 R) at cycle phase phi. Writes into o (x, y, z, pitch, toe, yaw, contact)
  footRel(side, phi, o) {
    let p = phi + (side ? 0.5 : 0);
    p -= Math.floor(p);
    this._foot(p, o);
    const sg = side ? -1 : 1;
    o.x = sg * (this.footX + this._sy * o.d);
    o.z -= this.S * this._k * p;
    o.yaw = sg * this.toeOut;
    return o;
  }

  // pelvis height allowed by one leg: hip joint must be within reach of the ankle target
  _legAllow(ax, ay, az, hx, hz, dyHip) {
    const dx = ax - hx, dz = az - hz;
    const r2 = this.reach * this.reach - dx * dx - dz * dz;
    return ay + Math.sqrt(Math.max(r2, 1e-6)) - dyHip;
  }
  _pelvisWalk(phi, out) {
    // lateral sway, rotations (excluding height)
    out.x = this.swayA * Math.sin(TAU * (phi - 0.05));
    out.z = this.surgeA * Math.sin(2 * TAU * (phi - 0.03));
    out.yaw = -this.yawP * Math.cos(TAU * phi);
    out.roll = this.rollP * Math.sin(TAU * (phi + 0.1));
    out.pitch = 0.035 + 0.012 * Math.cos(2 * TAU * (phi - 0.1));
    return out;
  }
  _hipAllow(phi, pv, fl, fr) {
    // hip joints positions relative to pelvis centre given yaw/roll
    const cy = Math.cos(pv.yaw), sy = Math.sin(pv.yaw), sr = Math.sin(pv.roll), cr = Math.cos(pv.roll);
    const hx = this.hipX;
    // left hip (+X): rotate (hx,0,0) by roll (Z) then yaw (Y)
    const lx = hx * cr * cy, ly = hx * sr, lz = -hx * cr * sy;
    const aL = this._legAllow(fl.x, fl.y, fl.z, pv.x + lx, pv.z + lz, ly);
    const aR = this._legAllow(fr.x, fr.y, fr.z, pv.x - lx, pv.z - lz, -ly);
    return smin(aL, aR, 0.005);
  }
  _solveOffset() {
    // choose heel-strike offset that maximises the lowest pelvis height over the cycle
    let best = -1e9, bestOff = 0.3 * this.S;
    const fl = {}, fr = {}, pv = {};
    for (let i = 0; i <= 16; i++) {
      this.hsOff = this.S * (0.04 + 0.4 * (i / 16));
      this._prepSwing();
      let mn = 1e9;
      for (let j = 0; j < 48; j++) {
        const phi = j / 48;
        this.footRel(0, phi, fl); this.footRel(1, phi, fr); this._pelvisWalk(phi, pv);
        mn = Math.min(mn, this._hipAllow(phi, pv, fl, fr));
      }
      if (mn > best) { best = mn; bestOff = this.hsOff; }
    }
    this.hsOff = bestOff;
    this._prepSwing();
    this.minHip = best;
  }
  _solveCap() {
    const fl = {}, fr = {}, pv = {};
    let mn = 1e9, mx = -1e9;
    for (let j = 0; j < 64; j++) {
      const phi = j / 64;
      this.footRel(0, phi, fl); this.footRel(1, phi, fr); this._pelvisWalk(phi, pv);
      const a = this._hipAllow(phi, pv, fl, fr);
      mn = Math.min(mn, a); mx = Math.max(mx, a);
    }
    this.walkLow = mn;
    this.walkCap = Math.min(mn + this.bobTarget, this.restHip - 0.004);
  }

  // --------------------------------------------------------------- full pose
  // carry: { side: 'L'|'R', kind } ; returns this.out
  // strideK: stride factor (stride = strideK * S); the caller advances the phase at speed / (strideK S)
  pose(phase, speed, turnRate, t, carry, strideK = 1) {
    const o = this.out;
    const g = this.g;
    phase = phase || 0; speed = speed || 0; turnRate = turnRate || 0;
    const kS = clamp(strideK || 1, 0.5, 1.06);
    this._k = kS;
    let walkCap = this.capV[this.capV.length - 1];
    for (let i = 1; i < this.capK.length; i++) if (kS <= this.capK[i]) { const f = (kS - this.capK[i - 1]) / (this.capK[i] - this.capK[i - 1]); walkCap = lerp(this.capV[i - 1], this.capV[i], f); break; }
    const phi = phase - Math.floor(phase);
    const w = smooth(0.06, 0.45, speed);                  // walk weight
    const sp = clamp(speed / 1.25, 0.55, 1.3);            // amplitude scale
    const hasT = typeof t === 'number' && isFinite(t);
    const tt = hasT ? t : 0;
    const ns = g.noiseSeed;
    // ---- feet (walk + idle blend)
    const fl = this._fl || (this._fl = {}), fr = this._fr || (this._fr = {});
    this.footRel(0, phi, fl); this.footRel(1, phi, fr);
    // idle stance: weight on one leg, other slightly forward and relaxed
    const il = g.idleLeg;
    const idleSway = hasT ? smoothNoise1(ns + 11, tt * 0.18) : 0;
    const shift = clamp(il * 0.55 + idleSway * 0.5, -1, 1); // + = weight on left
    const ix = this.footX * 1.45, toeOutIdle = this.toeOut + 0.08;
    const idle = [
      { x: ix, y: this.aH, z: il < 0 ? 0.05 : -0.01, pitch: 0, toe: 0, yaw: toeOutIdle, contact: 1 },
      { x: -ix, y: this.aH, z: il > 0 ? 0.05 : -0.01, pitch: 0, toe: 0, yaw: -toeOutIdle, contact: 1 },
    ];
    const feet = [fl, fr];
    for (let s = 0; s < 2; s++) {
      const f = feet[s], id = idle[s];
      if (w < 1) {
        f.x = lerp(id.x, f.x, w); f.y = lerp(id.y, f.y, w); f.z = lerp(id.z, f.z, w);
        f.pitch = lerp(0, f.pitch, w); f.toe = lerp(0, f.toe, w); f.yaw = lerp(id.yaw, f.yaw, w);
        f.contact = lerp(1, f.contact, w);
      }
      o.ankle[s].set(f.x, f.y, f.z);
      o.footYaw[s] = f.yaw; o.footPitch[s] = f.pitch; o.contact[s] = f.contact;
    }
    // ---- pelvis
    const pv = this._pv || (this._pv = {});
    this._pelvisWalk(phi, pv);
    const amp = sp * w;
    pv.x *= amp; pv.z *= amp; pv.yaw *= amp; pv.roll *= amp;
    pv.pitch = lerp(0.03, pv.pitch, w);
    // idle: hip shifted over the weight leg, free hip dropped
    pv.x += (1 - w) * shift * 0.03;
    pv.roll += (1 - w) * -shift * 0.045;
    pv.yaw += (1 - w) * shift * 0.04;
    // turning lean (into the turn) and forward lean with speed
    const lean = -clamp(speed * turnRate / 9.81 * 1.2, -0.12, 0.12);
    pv.roll += lean * 0.5;
    pv.x -= lean * this.restHip * 0.5; // whole-body lean about the feet: hips move to the inside of the turn
    pv.yaw += 0.12 * turnRate * w;
    const allow = this._hipAllow(phi, pv, fl, fr);
    const cap = lerp(this.restHip - 0.008 - (hasT ? 0.002 * (1 + smoothNoise1(ns + 5, tt * 0.25)) : 0), walkCap, w);
    const hipY = smin(allow - 0.001, cap, 0.006);
    o.pelvisPos.set(pv.x, hipY, pv.z);
    const qP = o.abs[BI.pelvis];
    qa(qP, AY, pv.yaw);
    qP.multiply(qa(_q, AZ, pv.roll));
    qP.multiply(qa(_q, AX, pv.pitch));
    o.local[BI.pelvis].copy(qP);
    // ---- spine & chest: counter-rotate, stay upright
    const thoraxYaw = w * this.yawT * sp * Math.cos(TAU * phi) + 0.2 * turnRate * w;
    const breathe = hasT ? 0.012 * Math.sin(tt * TAU / 4.2 + ns) : 0;
    const fwdLean = 0.03 + 0.05 * w * clamp(speed / 1.3, 0, 1.3) + g.lean + 0.07 * g.slouch;
    // target chest world orientation
    const qC = _cq || (_cq = new THREE.Quaternion());
    qa(qC, AY, thoraxYaw);
    qC.multiply(qa(_q, AZ, lean * 0.9 - pv.roll * 0.25 * w * 0));
    qC.multiply(qa(_q, AX, fwdLean + breathe));
    // relative = qP^-1 * qC, split between spine and chest
    _q2.copy(qP).invert().multiply(qC);
    const qs = o.local[BI.spine].identity().slerp(_q2, 0.5);
    o.local[BI.chest].copy(qs);
    o.abs[BI.spine].copy(qP).multiply(qs);
    o.abs[BI.chest].copy(o.abs[BI.spine]).multiply(qs);
    // ---- neck & head: steady head, looking ahead/down, turning into curves
    const look = (hasT ? smoothNoise1(ns + 21, tt * 0.22) * (0.25 + 0.35 * (1 - w)) : 0) + clamp(0.45 * turnRate, -0.45, 0.45);
    const phone = carry && carry.kind === 'phone';
    // phone users look down at the screen and glance up now and then
    const glance = phone && hasT ? 0.4 * smooth(0.35, 0.75, smoothNoise1(ns + 51, tt * 0.16)) : 0;
    const lookP = g.lookDown + (hasT ? smoothNoise1(ns + 31, tt * 0.17) * 0.05 : 0) + (phone ? 0.08 : 0) - glance;
    const qH = _hq || (_hq = new THREE.Quaternion());
    qa(qH, AY, look);
    qH.multiply(qa(_q, AX, lookP));
    qH.multiply(qa(_q, AZ, lean * 0.3));
    _q2.copy(o.abs[BI.chest]).invert().multiply(qH);
    const qn = o.local[BI.neck].identity().slerp(_q2, 0.4);
    o.abs[BI.neck].copy(o.abs[BI.chest]).multiply(qn);
    _q2.copy(o.abs[BI.neck]).invert().multiply(qH);
    o.local[BI.head].copy(_q2);
    o.abs[BI.head].copy(qH);
    // ---- legs (IK)
    for (let s = 0; s < 2; s++) this._leg(s);
    // ---- arms
    const armA = 0.38 * g.armSwing * clamp(speed / 1.3, 0.45, 1.2) * w;
    const lag = 0.035;
    for (let s = 0; s < 2; s++) {
      const sg = s ? -1 : 1;                 // +1 left, -1 right
      const ph = TAU * (phi - lag - (s ? 0 : 0.5));
      let flex = armA * Math.cos(ph) - 0.02;
      // relaxed elbows: ~15 deg at the back of the swing, ~40 deg at the front
      let elbow = 0.25 + (0.1 + 0.35 * w * clamp(speed / 1.3, 0, 1.2)) * (0.5 + 0.5 * Math.cos(ph - 0.35));
      let abd = 0.045 + 0.05 * clamp(this.look.mass, 0, 1) + (this.look.bust > 0.6 ? 0.02 : 0) + (this.look.outfit.skirtLen > 0.1 ? 0.02 : 0);
      let twist = 0, sup = 0, wrist = 0.08, clavE = 0.02 * Math.cos(ph) * w, clavP = 0.03 * Math.cos(ph) * w;
      if (hasT && w < 1) { const n = smoothNoise1(ns + 41 + s, tt * 0.3); flex += n * 0.04 * (1 - w); elbow += n * 0.05 * (1 - w); }
      const side = s ? 'R' : 'L';
      if (carry && carry.side === side) {
        const cp = CARRY[carry.kind];
        if (cp) {
          const k = cp.swing;
          flex = cp.flex + flex * k + (cp.bob || 0) * Math.cos(2 * TAU * phi) * w;
          elbow = cp.elbow + (elbow - 0.3) * k * 0.5;
          abd = cp.abd; twist = cp.twist; sup = cp.sup; wrist = cp.wrist;
        }
      }
      // shoulder bag on this side: keep arm off the bag
      if (this.look.carry === 'bag' && this.look.bagStyle === 'shoulder' && this.look.carrySide === side) { abd += 0.12; flex *= 0.6; }
      qa(o.local[s ? BI.clavR : BI.clavL], AZ, sg * (clavE - 0.03 * g.slouch + (s ? -g.droop : g.droop))).multiply(qa(_q, AY, -sg * (clavP + 0.05 * g.slouch)));
      // twist > 0 = internal rotation (forearm towards the midline); sup > 0 = supination (palm up)
      qzxy(o.local[s ? BI.upperArmR : BI.upperArmL], sg * abd, -flex, -sg * twist);
      qa(o.local[s ? BI.forearmR : BI.forearmL], AX, -elbow).multiply(qa(_q, AY, sg * sup));
      qa(o.local[s ? BI.handR : BI.handL], AX, -wrist).multiply(qa(_q, AZ, sg * 0.05));
    }
    // ---- secondary: hair tail, drape, bag (lagged pendulums, functions of phase)
    const headPitchW = lookP;
    qzxy(o.local[BI.tail], 0.1 * w * Math.sin(TAU * (phi - 0.22)) - lean * 0.6, -headPitchW + 0.08 * w * sp + 0.03 * w * Math.sin(2 * TAU * (phi - 0.12)), -look * 0.5);
    qzxy(o.local[BI.drape], 0.03 * w * Math.sin(TAU * (phi - 0.25)), 0.025 * w * sp + 0.018 * w * Math.sin(2 * TAU * (phi - 0.15)), 0);
    qzxy(o.local[BI.bag], 0.05 * w * Math.sin(TAU * (phi - 0.3)), 0.07 * w * sp + 0.03 * w * Math.sin(2 * TAU * (phi - 0.18)), 0);
    return o;
  }

  _leg(s) {
    const o = this.out, rest = this.rest;
    const thighI = s ? BI.thighR : BI.thighL, shinI = s ? BI.shinR : BI.shinL, footI = s ? BI.footR : BI.footL, toeI = s ? BI.toeR : BI.toeL;
    const qP = o.abs[BI.pelvis];
    // hip joint in root space
    const hip = _hip.copy(rest[thighI]).sub(rest[BI.pelvis]).applyQuaternion(qP).add(o.pelvisPos);
    const A = o.ankle[s];
    const a = this.Lt, b = this.Ls;
    const d0 = _v.copy(A).sub(hip);
    let d = d0.length();
    const dmax = (a + b) * 0.99995, dmin = Math.abs(a - b) + 1e-3;
    const dc = clamp(d, dmin, dmax);
    const dir = d0.multiplyScalar(1 / d);
    // knee pole: forward along the foot yaw, slightly outward
    const yaw = o.footYaw[s] * 0.7;
    const pole = _pole.set(Math.sin(yaw), 0, Math.cos(yaw));
    // perpendicular component of pole
    const pd = pole.dot(dir);
    const perp = _perp.copy(pole).addScaledVector(dir, -pd).normalize();
    const cosA = clamp((a * a + dc * dc - b * b) / (2 * a * dc), -1, 1);
    const sinA = Math.sqrt(1 - cosA * cosA);
    const knee = _knee.copy(hip).addScaledVector(dir, a * cosA).addScaledVector(perp, a * sinA);
    const ankle = _ank.copy(hip).addScaledVector(dir, dc);
    // hinge axis n = dir x perp (points to the character's right for a forward pole)
    const n = _n.copy(dir).cross(perp).normalize();
    // segment frames: Y = up along segment (from child to parent), Z = forward = n x down, X = Y x Z
    setSegQuat(o.abs[thighI], _seg.copy(knee).sub(hip).normalize(), n);
    setSegQuat(o.abs[shinI], _seg.copy(ankle).sub(knee).normalize(), n);
    // foot: yaw + pitch
    const fy = o.footYaw[s], fp = o.footPitch[s];
    const fwd = _fwd.set(Math.sin(fy) * Math.cos(fp), Math.sin(fp), Math.cos(fy) * Math.cos(fp));
    setFootQuat(o.abs[footI], fwd, fy);
    // toe: local dorsiflexion (positive = toes up relative to foot)
    qa(o.local[toeI], AX, -(this._toeLocal(s)));
    o.abs[toeI].copy(o.abs[footI]).multiply(o.local[toeI]);
    // locals
    o.local[thighI].copy(qP).invert().multiply(o.abs[thighI]);
    o.local[shinI].copy(o.abs[thighI]).invert().multiply(o.abs[shinI]);
    o.local[footI].copy(o.abs[shinI]).invert().multiply(o.abs[footI]);
  }
  _toeLocal(s) {
    const f = s ? this._fr : this._fl;
    return clamp(f.toe, 0, 0.8);
  }
}
let _cq = null, _hq = null;
const _hip = new THREE.Vector3(), _pole = new THREE.Vector3(), _perp = new THREE.Vector3(), _knee = new THREE.Vector3();
const _ank = new THREE.Vector3(), _n = new THREE.Vector3(), _seg = new THREE.Vector3(), _fwd = new THREE.Vector3();
const _bx = new THREE.Vector3(), _by = new THREE.Vector3(), _bz = new THREE.Vector3();
// rest segment points down (-Y); forward +Z. down = seg direction. n = hinge axis (character's right, i.e. -X at rest)
function setSegQuat(out, down, n) {
  // Z (forward) = n x down
  _bz.copy(n).cross(down).normalize();
  _by.copy(down).negate();
  _bx.copy(_by).cross(_bz).normalize();
  _m.makeBasis(_bx, _by, _bz);
  out.setFromRotationMatrix(_m);
}
function setFootQuat(out, fwd, yaw) {
  _bz.copy(fwd).normalize();
  _bx.set(Math.cos(yaw), 0, -Math.sin(yaw));
  _by.copy(_bz).cross(_bx).normalize();
  _bx.copy(_by).cross(_bz).normalize();
  _m.makeBasis(_bx, _by, _bz);
  out.setFromRotationMatrix(_m);
}

// Carry poses (radians): arm flexion (+ forward), elbow flexion, abduction, twist (internal +),
// forearm supination (+ palm up), wrist flexion; swing = fraction of normal arm swing kept.
export const CARRY = {
  popcorn: { flex: 0.12, elbow: 1.5, abd: 0.05, twist: 0.35, sup: 0.0, wrist: -0.1, swing: 0.1, bob: 0.012 },
  cup: { flex: 0.1, elbow: 1.4, abd: 0.1, twist: 0.5, sup: 0.0, wrist: -0.15, swing: 0.12, bob: 0.012 },
  phone: { flex: 0.22, elbow: 1.78, abd: 0.02, twist: 0.8, sup: 1.1, wrist: 0.2, swing: 0.05, bob: 0.008 },
  bag: null,
};
