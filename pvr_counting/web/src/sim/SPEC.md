# Procedural CCTV feed: spec (pure code, no AI footage)

The slide shows a live "camera POV" of a cinema auditorium entrance with people
walking in and out, tracking boxes, a counting line and big IN / OUT / INSIDE KPIs.
This folder builds the **camera image and the people**, 100% in code with three.js,
rendered live in the browser. The dashboard (KPIs, boxes, chart) is built separately
and only talks to the `Feed` interface below.

Look target: `pvr_counting/media/look_ref.jpg` (1920x1080). Match its framing,
materials, lighting and "real security camera" feel as closely as possible.

Hard rules
- three.js 0.170.0 from `web/node_modules/three` (import from `'three'` and
  `'three/addons/...'`). Bundled with esbuild (see `web/build.mjs` / `web/tools/`).
- No external assets, no network at runtime, no AI generated media. Every texture is
  made in code (CanvasTexture / DataTexture / shader). Fonts are not needed here.
- Deterministic: the image for time `T` (seconds) is a pure function of `T` and the
  seed. No `Math.random()`, no `Date.now()`, no accumulated state that depends on frame
  rate. Use the seeded PRNG in `rng.js`.
- Must run in real time on a normal laptop (integrated GPU) at 1920x1080, and must
  also render correctly in headless Chromium (SwiftShader WebGL2) for screenshots and
  video export. Keep shadow-casting lights to 4 or fewer, use merged geometry per person.

## World

Metres, Y up, floor at y = 0. The camera looks toward -Z.

| Thing | Where |
| --- | --- |
| Corridor floor | x in [-4.6, 4.6], z in [-5.0, 3.6]. Dark maroon cinema carpet with a small repeating motif |
| Door wall | plane z = -5.0, facing +Z, height 3.2. Dark charcoal acoustic fabric panels, thin brass trims, warm backlit vertical LED strips |
| Doorway | centred x = 0, opening x in [-1.3, 1.3], height 2.6, brass frame |
| Door leaves | two padded/upholstered leaves (button-tufted dark fabric, brass push bars), hinged at x = ±1.3, swung open into the corridor about 70° |
| Side walls | x = ±4.6 (may angle slightly), same panel + LED-strip treatment as the reference |
| Ceiling | y = 3.25, dark, a few small round downlight fixtures |
| Auditorium (behind door) | z from -5.0 to about -22. Dark. Centre aisle of steps rising away, tiny warm step lights along the aisle, rows of dark seats both sides, a big screen at the far end glowing pale blue, lighting the room very faintly |
| Ticket podium | wood, about (2.25, 0, -4.35), 0.55 w x 1.05 h x 0.45 d, small glowing tablet on top |
| Stanchions | 2–3 chrome posts with black retractable belts, right of the podium, e.g. (2.95, -4.2), (3.55, -3.3) |
| Counting line | on the floor at z = -3.3, from x = -2.4 to x = +2.4. Door side (z < -3.3) is "inside". Foot crossing from z > -3.3 to z < -3.3 = **in**, the reverse = **out** |

Camera: ceiling CCTV dome, roughly at (0, 3.7, 2.6) looking down ~38–42° toward the
doorway, wide lens (vertical FOV ~60–65° before distortion, about 2.8 mm on a 1/2.7"
sensor) plus mild barrel distortion in post. Tune position/FOV so the framing matches
`look_ref.jpg`: doorway upper-middle, door top near the top edge, carpet filling the
lower two thirds, side walls converging at the edges.

Lighting: warm 3000 K downlights making soft pools on the carpet, warm wall LED strips,
everything else dim; cool faint spill from the auditorium screen through the doorway.
Exposure and grade like the reference: dim interior, slightly desaturated, warm.

CCTV look (post): mild barrel distortion, slight softness, sensor noise (animated by
`T`, luminance + a little chroma, stronger in shadows), subtle vignette, tiny chromatic
aberration at the edges, a very faint compression feel. It must read as a real camera,
not a game.

## Module contracts

All under `web/src/sim/`.

### `rng.js` (shared, already written)
`mulberry32(seed) -> () => float in [0,1)`, `hash2(a, b) -> float in [0,1)`,
`smoothNoise1(seed, t) -> float in [-1,1]` (smooth 1-D value noise).

### `environment.js`
```js
export const LINE = { z: -3.3, x0: -2.4, x1: 2.4 };
export function buildEnvironment(scene, renderer) -> {
  camera,          // THREE.PerspectiveCamera, aspect 16:9, positioned and aimed
  update(T),       // optional per-time changes (flicker of the screen glow etc.), pure in T
}
```
### `cctv_pass.js`
```js
export const DISTORTION = { k1, k2 };           // radial coefficients used by the shader
export function distortNdc(x, y) -> [x', y'];   // same mapping in JS (NDC in, NDC out) so
                                                // projected boxes line up with the image
export function createCCTVPasses(renderer, scene, camera, w, h) -> {
  render(T),                                    // renders scene + post for time T
  setSize(w, h)
}
```
### `humans.js`
```js
export function createHuman(seed, opts) -> Human
// opts: { kind: 'adult' | 'child', sex: 'm' | 'f', carry: null | 'popcorn' | 'cup' | 'bag' | 'phone' }
// Human: {
//   object,          // THREE.Object3D, origin on the floor between the feet, facing +Z
//   height,          // standing height in metres
//   strideLength,    // metres travelled per full walk cycle (two steps)
//   setPose(phase, speed, turnRate),  // phase in cycles (0..1 repeats), speed m/s
//                                      // (0 = standing idle), turnRate rad/s (lean/look)
//   boxPoints(out),  // fill `out` (array of THREE.Vector3) with WORLD positions that
//                    // bound the visible body: head top, both hands, both feet (toe and
//                    // heel), shoulders, elbows, knees, hip. Call after updateMatrixWorld.
//   dispose()
// }
```
Indian multiplex audience: mixed adults and a few children; skin tones in the South
Asian range; mostly black/dark-brown hair (various cuts, some long hair, buns, braids);
clothes: t-shirts, shirts, hoodies, jeans, chinos, kurtas (long tunic) with churidar,
salwar-kameez with dupatta, a saree (draped skirt + pallu over the shoulder), sneakers,
sandals. Some carry a popcorn tub, a drink cup, a handbag or a phone.
The walk must look natural from a high CCTV angle: heel strike, knee bend, hip sway
and rotation, counter-swinging arms, slight vertical bob, head steady.

### `crowd.js` (pure JS, no three.js)
```js
export function createCrowd({ seed = 7, horizon = 3600, line = LINE }) -> {
  agents,                 // [{ id, seed, kind: 'in' | 'out', group, t0, t1, human: {kind, sex, carry}, speed }]
  stateAt(agent, t),      // null if not active, else { x, z, heading, speed, dist, turnRate, alpha }
                          // heading: yaw in radians, 0 = facing +Z (toward the camera)
                          // dist: metres walked since t0 (phase = dist / strideLength)
                          // alpha: 0..1 for fading in/out at the edges or into the dark auditorium
  activeAt(t),            // agents active at t (fast, use an index)
  events,                 // sorted [{ t, id, dir: 'in' | 'out', x, z }], foot crossing LINE.z
}
```
Traffic: pre-show, about one person every 2–3 s on average, roughly 70 % going in,
30 % coming out, in bursts. Singles, couples and families (2–4 walking together side
by side or staggered). "In" people enter from the bottom edge of the frame (behind and
below the camera, z ≈ 3.6) or the bottom corners, walk to the doorway and on into the
auditorium until they vanish in the dark (z ≈ -8). "Out" people appear from the dark
auditorium, come through the doorway and walk toward the camera, leaving at the bottom
or bottom corners. Smooth curved paths, natural speed variation (1.0–1.45 m/s adults,
slower with kids), nobody overlaps anybody (keep >= 0.45 m between body centres, plan
it at generation time), nobody walks through the podium, stanchions or door leaves.
Every in/out person crosses the counting line exactly once, inside its x span.

### `feed_sim3d.js` (integration)
```js
export async function createSimFeed(host, { seed = 7, quality = 'high' }) -> Feed
```
The Feed interface the dashboard uses:
```js
Feed = {
  kind: 'sim',
  width: 1920, height: 1080,              // native image space for all coordinates below
  line: [[x0, y0], [x1, y1]],             // counting line endpoints in image px (projected + distorted)
  canvas,                                 // the canvas the feed draws into (appended to host, fills it)
  clock(),                                // live presentation time in seconds since start()
  start(),                                // start live mode
  seek(T),                                // Promise; export mode: make everything ready for T
  render(T),                              // draw the camera image for time T
  people(T),                              // [{ id, x, y, w, h, conf }] tight detector-like boxes in image px,
                                          // projected via boxPoints + distortNdc, clipped to the frame,
                                          // with tiny deterministic jitter and a smooth conf in 0.80..0.98.
                                          // Only people meaningfully visible (alpha, in frame, not deep in
                                          // the dark auditorium).
  footAt(id, t),                          // [x, y] image px of that person's foot point at time t, or null
  events(T),                              // all crossings with t <= T: [{ t, id, dir, x, y }] (image px)
}
```
`host` is a positioned element sized to the video panel (CSS px, 16:9). The canvas fills
it and renders at `min(1920, host width × devicePixelRatio)` wide. `people`, `line`,
`footAt` and `events` always use the 1920x1080 space.

## Checks every module owner runs

`web/tools/shot.mjs` renders pages headlessly (Playwright + SwiftShader). Look at your
own screenshots with the Read tool and iterate until they look right.
