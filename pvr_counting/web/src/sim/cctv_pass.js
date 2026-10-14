// CCTV camera look: renders the scene into an HDR target, then a small bloom
// chain and one "sensor + lens + encoder" pass: barrel distortion, lateral
// chromatic aberration, lens softness with in-camera sharpening, vignette,
// shot/read noise (pure function of T), warm grade, 4:2:0-ish chroma and a
// faint 8x8 block feel.
//
// Distortion model (radially symmetric in pixel space, r normalised so the image
// corner is r = 1):
//   render NDC u = image NDC d * (1 + k1 r_d^2 + k2 r_d^4) / (1 + k1 + k2)
// so the image corners show exactly the camera frustum corners and the centre
// is magnified by (1 + k1 + k2). distortNdc() is the inverse (render -> image).
import * as THREE from 'three';
import { FullScreenQuad } from 'three/addons/postprocessing/Pass.js';

export const DISTORTION = { k1: 0.827, k2: 0.077 };

const ASPECT = 16 / 9;
const NORM = Math.sqrt(ASPECT * ASPECT + 1);

function gain(r) {
  const { k1, k2 } = DISTORTION;
  return (1 + k1 * r * r + k2 * r * r * r * r) / (1 + k1 + k2);
}

// image NDC -> render (pinhole) NDC
export function undistortNdc(x, y) {
  const r = Math.hypot(x * ASPECT, y) / NORM;
  const g = gain(r);
  return [x * g, y * g];
}

// render (pinhole) NDC -> image NDC. Same mapping the shader uses, inverted
// with Newton iterations (monotonic for k1, k2 >= 0).
export function distortNdc(x, y) {
  const { k1, k2 } = DISTORTION;
  const n = 1 + k1 + k2;
  const ru = Math.hypot(x * ASPECT, y) / NORM;
  if (ru < 1e-9) return [x * n, y * n];
  let r = ru; // initial guess
  for (let i = 0; i < 12; i++) {
    const r2 = r * r;
    const f = (r * (1 + k1 * r2 + k2 * r2 * r2)) / n - ru;
    const df = (1 + 3 * k1 * r2 + 5 * k2 * r2 * r2) / n;
    const step = f / df;
    r -= step;
    if (Math.abs(step) < 1e-10) break;
  }
  const s = r / ru;
  return [x * s, y * s];
}

const VERT = /* glsl */ `
varying vec2 vUv;
void main() { vUv = uv; gl_Position = vec4(position.xy, 0.0, 1.0); }
`;

// Bright pass + first downsample (13-tap, Jimenez 2014)
const DOWN_FRAG = /* glsl */ `
precision highp float;
uniform sampler2D tSrc; uniform vec2 uTexel; uniform float uThreshold; uniform float uKnee; uniform bool uPrefilter;
varying vec2 vUv;
vec3 s(vec2 o) { return texture2D(tSrc, vUv + o * uTexel).rgb; }
void main() {
  vec3 a = s(vec2(-2.,-2.)), b = s(vec2(0.,-2.)), c = s(vec2(2.,-2.));
  vec3 d = s(vec2(-1.,-1.)), e = s(vec2(1.,-1.));
  vec3 f = s(vec2(-2.,0.)), g = s(vec2(0.,0.)), h = s(vec2(2.,0.));
  vec3 i = s(vec2(-1.,1.)), j = s(vec2(1.,1.));
  vec3 k = s(vec2(-2.,2.)), l = s(vec2(0.,2.)), m = s(vec2(2.,2.));
  vec3 col = (d+e+i+j)*0.125 + (a+c+k+m)*0.03125 + (b+f+h+l)*0.0625 + g*0.125;
  if (uPrefilter) {
    float br = max(col.r, max(col.g, col.b));
    float soft = clamp(br - uThreshold + uKnee, 0.0, 2.0 * uKnee);
    soft = soft * soft / (4.0 * uKnee + 1e-4);
    float w = max(soft, br - uThreshold) / max(br, 1e-4);
    col *= w;
    col = min(col, vec3(60.0));
  }
  gl_FragColor = vec4(col, 1.0);
}`;

const UP_FRAG = /* glsl */ `
precision highp float;
uniform sampler2D tSrc; uniform sampler2D tBase; uniform vec2 uTexel; uniform float uRadius;
varying vec2 vUv;
void main() {
  vec2 o = uTexel * uRadius;
  vec3 c = texture2D(tSrc, vUv + vec2(-o.x, -o.y)).rgb + texture2D(tSrc, vUv + vec2(o.x, -o.y)).rgb
         + texture2D(tSrc, vUv + vec2(-o.x, o.y)).rgb + texture2D(tSrc, vUv + vec2(o.x, o.y)).rgb;
  c += 2.0 * (texture2D(tSrc, vUv + vec2(0.0, -o.y)).rgb + texture2D(tSrc, vUv + vec2(0.0, o.y)).rgb
            + texture2D(tSrc, vUv + vec2(-o.x, 0.0)).rgb + texture2D(tSrc, vUv + vec2(o.x, 0.0)).rgb);
  c += 4.0 * texture2D(tSrc, vUv).rgb;
  c /= 16.0;
  gl_FragColor = vec4(texture2D(tBase, vUv).rgb + c, 1.0);
}`;

const FINAL_FRAG = /* glsl */ `
precision highp float;
uniform sampler2D tScene; uniform sampler2D tBloom;
uniform vec2 uOutRes;      // output pixels
uniform vec2 uSrcTexel;    // 1 / scene target size
uniform float uK1, uK2, uAspect;
uniform float uTime, uFrame;
uniform float uExposure, uBloom, uCA, uSoft, uSharpen, uVignette;
uniform float uNoise, uChromaNoise, uBlack, uSat, uBlock;
uniform vec3 uWB, uLift, uGain;
uniform float uGamma;
varying vec2 vUv;

// --- hashing (stateless, pure function of pixel + frame) ---
float hash13(vec3 p3) {
  p3 = fract(p3 * 0.1031);
  p3 += dot(p3, p3.zyx + 31.32);
  return fract((p3.x + p3.y) * p3.z);
}
float gauss(vec2 px, float salt) {
  float a = hash13(vec3(px, uFrame * 1.7 + salt));
  float b = hash13(vec3(px + 17.3, uFrame * 1.7 + salt + 5.1));
  float c = hash13(vec3(px - 9.1, uFrame * 1.7 + salt + 11.7));
  return (a + b + c - 1.5) * 2.0; // ~ unit variance
}

vec2 undist(vec2 d) {
  float r2 = (d.x * d.x * uAspect * uAspect + d.y * d.y) / (uAspect * uAspect + 1.0);
  return d * (1.0 + uK1 * r2 + uK2 * r2 * r2) / (1.0 + uK1 + uK2);
}

vec3 soft(vec2 uv, vec2 t) {
  // lens softness: small 5-tap kernel (~1 output px)
  vec3 c = texture2D(tScene, uv).rgb * 0.4;
  c += texture2D(tScene, uv + vec2( t.x,  t.y)).rgb * 0.15;
  c += texture2D(tScene, uv + vec2(-t.x,  t.y)).rgb * 0.15;
  c += texture2D(tScene, uv + vec2( t.x, -t.y)).rgb * 0.15;
  c += texture2D(tScene, uv + vec2(-t.x, -t.y)).rgb * 0.15;
  return c;
}
vec3 wide(vec2 uv, vec2 t) {
  vec3 c = texture2D(tScene, uv + vec2( t.x, 0.0)).rgb;
  c += texture2D(tScene, uv + vec2(-t.x, 0.0)).rgb;
  c += texture2D(tScene, uv + vec2(0.0,  t.y)).rgb;
  c += texture2D(tScene, uv + vec2(0.0, -t.y)).rgb;
  c += texture2D(tScene, uv + vec2( t.x,  t.y) * 0.7).rgb;
  c += texture2D(tScene, uv + vec2(-t.x, -t.y) * 0.7).rgb;
  c += texture2D(tScene, uv + vec2(-t.x,  t.y) * 0.7).rgb;
  c += texture2D(tScene, uv + vec2( t.x, -t.y) * 0.7).rgb;
  return c / 8.0;
}

vec3 tonemap(vec3 x) {
  // camera-like curve: linear toe, smooth shoulder that clips around 1.0 out
  vec3 a = x * (1.0 + x / 9.0) / (1.0 + x);
  return clamp(a * 1.08, 0.0, 1.0);
}
float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
vec3 toSRGB(vec3 c) {
  c = max(c, 0.0);
  return mix(c * 12.92, 1.055 * pow(c, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, c));
}

void main() {
  vec2 px = floor(vUv * uOutRes);                 // output pixel coordinate
  vec2 d = vUv * 2.0 - 1.0;                        // image NDC
  vec2 u = undist(d);                              // pinhole NDC
  float r2 = (d.x * d.x * uAspect * uAspect + d.y * d.y) / (uAspect * uAspect + 1.0);

  // output pixel size expressed in scene uv, scaled by local magnification
  vec2 opx = (1.0 / uOutRes) * (1.0 + uK1 * r2) / (1.0 + uK1 + uK2);
  vec2 t = opx * uSoft;

  // lateral chromatic aberration grows with r^2
  float ca = uCA * r2;
  vec2 uvR = (u * (1.0 + ca)) * 0.5 + 0.5;
  vec2 uvG = u * 0.5 + 0.5;
  vec2 uvB = (u * (1.0 - ca)) * 0.5 + 0.5;
  vec3 c;
  c.r = soft(uvR, t).r;
  c.g = soft(uvG, t).g;
  c.b = soft(uvB, t).b;

  // in-camera sharpening (unsharp mask, luma only) -> faint halos on edges
  vec3 w = wide(uvG, opx * 2.2);
  float lc = luma(c), lw = luma(w);
  c *= 1.0 + uSharpen * clamp((lc - lw) / max(lc, 1e-3), -0.6, 0.6);

  // bloom / veiling glare (sampled with the same distortion)
  vec3 bl = texture2D(tBloom, uvG).rgb;
  c = c + bl * uBloom;

  // exposure, white balance
  c *= uExposure * uWB;

  // vignette (natural cos^4-ish falloff + slight mechanical darkening at the corners)
  float vig = 1.0 - uVignette * r2 - 0.25 * uVignette * r2 * r2 * r2;
  c *= max(vig, 0.0);

  // sensor noise in linear light: shot (signal dependent) + read noise
  float L = max(luma(c), 0.0);
  float sigma = uNoise * sqrt(0.00018 * L + 0.0000009);
  float n = gauss(px, 0.0) * sigma;
  // chroma noise at half resolution (debayer + 4:2:0 make it blotchy)
  vec2 cpx = floor(px * 0.5);
  float cn1 = gauss(cpx, 3.0) * sigma * uChromaNoise;
  float cn2 = gauss(cpx, 7.0) * sigma * uChromaNoise;
  c += vec3(n + cn1, n - 0.4 * cn1 - 0.4 * cn2, n + cn2);

  // camera tone curve + grade
  c = tonemap(c);
  float Y = luma(c);
  c = mix(vec3(Y), c, uSat);
  c = pow(max(c, 0.0), vec3(uGamma));
  c = c * uGain + uLift * (1.0 - c);
  c = max(c, 0.0);

  // encode
  vec3 s = toSRGB(c);

  // encoder feel: reduced chroma resolution + gentle 8x8 block DC wobble in flat darks
  vec3 sw = toSRGB(pow(max(mix(vec3(luma(tonemap(w * uExposure * uWB))), tonemap(w * uExposure * uWB), uSat), 0.0), vec3(uGamma)) * uGain);
  float yS = dot(s, vec3(0.299, 0.587, 0.114));
  float yW = dot(sw, vec3(0.299, 0.587, 0.114));
  vec3 chromaS = s - yS, chromaW = sw - yW;
  s = yS + mix(chromaS, chromaW, 0.55);
  vec2 blk = floor(px / 8.0);
  float gop = floor(uFrame / 12.0);
  float dc = (hash13(vec3(blk, gop)) - 0.5) * uBlock * (1.0 - smoothstep(0.05, 0.35, yS));
  s += dc;
  // quantise (8-bit) with the noise acting as dither
  s = floor(s * 255.0 + 0.5) / 255.0;
  s = max(s, vec3(uBlack));
  gl_FragColor = vec4(s, 1.0);
}`;

export function createCCTVPasses(renderer, scene, camera, w, h, opts = {}) {
  const renderScale = opts.renderScale ?? 1.25;
  const samples = opts.samples ?? 4;
  const params = {
    exposure: 1.0,
    bloom: 0.16,
    bloomThreshold: 1.1,
    bloomKnee: 0.6,
    ca: 0.0045,
    soft: 0.6,
    sharpen: 0.35,
    vignette: 0.32,
    noise: 1.0,
    chromaNoise: 0.6,
    black: 0.006,
    sat: 0.92,
    gamma: 1.0,
    wb: new THREE.Vector3(1.0, 1.0, 0.96),
    lift: new THREE.Vector3(0.004, 0.004, 0.006),
    gain: new THREE.Vector3(1.0, 1.0, 1.0),
    block: 0.006,
    fps: 25,
    ...(opts.params || {}),
  };

  let W = w, H = h, SW = 1, SH = 1;
  const rtOpts = { type: THREE.HalfFloatType, format: THREE.RGBAFormat, depthBuffer: false, generateMipmaps: false, minFilter: THREE.LinearFilter, magFilter: THREE.LinearFilter };
  const rtScene = new THREE.WebGLRenderTarget(4, 4, { ...rtOpts, depthBuffer: true, samples });
  rtScene.texture.colorSpace = THREE.LinearSRGBColorSpace;
  const LEVELS = 6;
  const down = [], up = [];
  for (let i = 0; i < LEVELS; i++) {
    down.push(new THREE.WebGLRenderTarget(4, 4, rtOpts));
    up.push(new THREE.WebGLRenderTarget(4, 4, rtOpts));
  }

  const downMat = new THREE.ShaderMaterial({
    vertexShader: VERT, fragmentShader: DOWN_FRAG, depthTest: false, depthWrite: false,
    uniforms: { tSrc: { value: null }, uTexel: { value: new THREE.Vector2() }, uThreshold: { value: 1 }, uKnee: { value: 0.5 }, uPrefilter: { value: false } },
  });
  const upMat = new THREE.ShaderMaterial({
    vertexShader: VERT, fragmentShader: UP_FRAG, depthTest: false, depthWrite: false,
    uniforms: { tSrc: { value: null }, tBase: { value: null }, uTexel: { value: new THREE.Vector2() }, uRadius: { value: 1.0 } },
  });
  const finalMat = new THREE.ShaderMaterial({
    vertexShader: VERT, fragmentShader: FINAL_FRAG, depthTest: false, depthWrite: false,
    uniforms: {
      tScene: { value: rtScene.texture }, tBloom: { value: null },
      uOutRes: { value: new THREE.Vector2() }, uSrcTexel: { value: new THREE.Vector2() },
      uK1: { value: DISTORTION.k1 }, uK2: { value: DISTORTION.k2 }, uAspect: { value: ASPECT },
      uTime: { value: 0 }, uFrame: { value: 0 },
      uExposure: { value: 1 }, uBloom: { value: 0.1 }, uCA: { value: 0.004 }, uSoft: { value: 0.6 }, uSharpen: { value: 0.3 },
      uVignette: { value: 0.3 }, uNoise: { value: 1 }, uChromaNoise: { value: 0.6 }, uBlack: { value: 0.01 }, uSat: { value: 0.85 },
      uBlock: { value: 0.006 }, uWB: { value: new THREE.Vector3(1, 1, 1) }, uLift: { value: new THREE.Vector3() }, uGain: { value: new THREE.Vector3(1, 1, 1) },
      uGamma: { value: 1 },
    },
  });
  const quad = new FullScreenQuad(downMat);

  function setSize(w2, h2) {
    W = w2; H = h2;
    SW = Math.max(16, Math.round(W * renderScale));
    SH = Math.max(9, Math.round(H * renderScale));
    rtScene.setSize(SW, SH);
    let bw = Math.max(8, Math.round(SW / 2)), bh = Math.max(4, Math.round(SH / 2));
    for (let i = 0; i < LEVELS; i++) {
      down[i].setSize(bw, bh); up[i].setSize(bw, bh);
      bw = Math.max(2, Math.round(bw / 2)); bh = Math.max(2, Math.round(bh / 2));
    }
    finalMat.uniforms.uOutRes.value.set(W, H);
    finalMat.uniforms.uSrcTexel.value.set(1 / SW, 1 / SH);
  }
  setSize(w, h);

  function bloomChain() {
    // downsample
    let src = rtScene.texture, sw = SW, sh = SH;
    for (let i = 0; i < LEVELS; i++) {
      downMat.uniforms.tSrc.value = src;
      downMat.uniforms.uTexel.value.set(1 / sw, 1 / sh);
      downMat.uniforms.uPrefilter.value = i === 0;
      downMat.uniforms.uThreshold.value = params.bloomThreshold;
      downMat.uniforms.uKnee.value = params.bloomKnee;
      quad.material = downMat;
      renderer.setRenderTarget(down[i]);
      quad.render(renderer);
      src = down[i].texture; sw = down[i].width; sh = down[i].height;
    }
    // upsample + accumulate
    let acc = down[LEVELS - 1].texture;
    for (let i = LEVELS - 2; i >= 0; i--) {
      upMat.uniforms.tSrc.value = acc;
      upMat.uniforms.tBase.value = down[i].texture;
      upMat.uniforms.uTexel.value.set(1 / down[i + 1].width, 1 / down[i + 1].height);
      upMat.uniforms.uRadius.value = 1.0;
      quad.material = upMat;
      renderer.setRenderTarget(up[i]);
      quad.render(renderer);
      acc = up[i].texture;
    }
    return acc;
  }

  function render(T, target = null) {
    const prevTM = renderer.toneMapping;
    renderer.toneMapping = THREE.NoToneMapping;
    renderer.setRenderTarget(rtScene);
    renderer.clear(true, true, true);
    renderer.render(scene, camera);
    const bloomTex = bloomChain();

    const u = finalMat.uniforms;
    u.tBloom.value = bloomTex;
    u.uTime.value = T;
    u.uFrame.value = Math.floor(T * params.fps + 1e-6);
    u.uK1.value = DISTORTION.k1; u.uK2.value = DISTORTION.k2;
    u.uExposure.value = params.exposure;
    u.uBloom.value = params.bloom;
    u.uCA.value = params.ca;
    u.uSoft.value = params.soft;
    u.uSharpen.value = params.sharpen;
    u.uVignette.value = params.vignette;
    u.uNoise.value = params.noise;
    u.uChromaNoise.value = params.chromaNoise;
    u.uBlack.value = params.black;
    u.uSat.value = params.sat;
    u.uGamma.value = params.gamma;
    u.uBlock.value = params.block;
    u.uWB.value.copy(params.wb);
    u.uLift.value.copy(params.lift);
    u.uGain.value.copy(params.gain);
    quad.material = finalMat;
    renderer.setRenderTarget(target);
    quad.render(renderer);
    renderer.toneMapping = prevTM;
  }

  function dispose() {
    rtScene.dispose();
    for (const r of down) r.dispose();
    for (const r of up) r.dispose();
    downMat.dispose(); upMat.dispose(); finalMat.dispose(); quad.dispose();
  }

  return { render, setSize, params, dispose, get renderSize() { return [SW, SH]; } };
}
