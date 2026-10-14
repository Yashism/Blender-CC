// Feed backed by the looping CCTV clip plus offline tracks (see tools/track.py).
// Presentation time T runs on forever; the clip loops every D seconds and each loop
// gets fresh person IDs, so counts and IDs keep growing like a real camera.

export async function createVideoFeed(host, { sources, data, idBase = 201 }) {
  const fps = data.fps;
  const D = data.frames / fps;
  const nTracks = data.tracks.length;

  // frame -> [[track, boxIndex]]
  const byFrame = Array.from({ length: data.frames }, () => []);
  for (const tr of data.tracks) {
    tr.b.forEach((_, i) => { const f = tr.f0 + i; if (f < data.frames) byFrame[f].push([tr, i]); });
  }
  const trackById = new Map(data.tracks.map((t) => [t.id, t]));
  const loopEvents = data.events.map((e) => ({ t: (e.f + 0.5) / fps, id: e.id, dir: e.dir, x: e.x, y: e.y })).sort((a, b) => a.t - b.t);

  const video = document.createElement('video');
  video.muted = true; video.playsInline = true; video.loop = true; video.preload = 'auto';
  video.setAttribute('muted', ''); video.setAttribute('playsinline', '');
  for (const s of sources) {
    if (s.type && !video.canPlayType(s.type)) continue;
    video.src = s.src;
    break;
  }
  host.appendChild(video);
  await new Promise((res, rej) => {
    if (video.readyState >= 2) return res();
    video.addEventListener('loadeddata', res, { once: true });
    video.addEventListener('error', () => rej(new Error('video failed to load')), { once: true });
  });

  // live clock: loops * D + currentTime, wrap detected when currentTime jumps back
  let loops = 0, lastVT = 0, presented = null;
  const tick = () => {
    const vt = video.currentTime;
    if (vt + 1 < lastVT) loops++;
    lastVT = vt;
  };
  if ('requestVideoFrameCallback' in video) {
    const onFrame = (_, meta) => { presented = meta.mediaTime; tick(); video.requestVideoFrameCallback(onFrame); };
    video.requestVideoFrameCallback(onFrame);
  }
  let liveMode = false;

  const split = (T) => {
    const k = Math.max(0, Math.floor(T / D));
    return [k, T - k * D];
  };
  const frameOf = (vt) => Math.min(data.frames - 1, Math.max(0, Math.floor(vt * fps + 1e-4)));
  const gid = (k, id) => idBase + k * nTracks + id - 1;
  const local = (g) => { const z = g - idBase; return [Math.floor(z / nTracks), (z % nTracks) + 1]; };

  function boxAt(tr, f) {
    const i = f - tr.f0;
    if (i < 0 || i >= tr.b.length) return null;
    return tr.b[i];
  }

  const evCache = [];
  return {
    kind: 'video',
    width: data.w, height: data.h,
    line: data.line,
    canvas: video,
    duration: D,
    clock() {
      tick();
      return loops * D + video.currentTime;
    },
    async start() {
      liveMode = true;
      try { await video.play(); return true; } catch (e) { return false; }
    },
    async seek(T) {
      const [, vt] = split(T);
      const target = (frameOf(vt) + 0.5) / fps;
      if (Math.abs(video.currentTime - target) < 1e-3 && video.readyState >= 2) return;
      await new Promise((res) => {
        video.addEventListener('seeked', res, { once: true });
        video.currentTime = target;
      });
      if ('requestVideoFrameCallback' in video) {
        await Promise.race([new Promise((r) => video.requestVideoFrameCallback(() => r())), new Promise((r) => setTimeout(r, 120))]);
      }
    },
    render() {},
    people(T) {
      const [k, vt] = split(T);
      // live: draw the boxes of the frame actually on screen, not the one the clock is near
      const f = liveMode && presented != null && Math.abs(presented - vt) < 0.2 ? frameOf(presented) : frameOf(vt);
      const out = [];
      for (const [tr, i] of byFrame[f]) {
        const [x, y, w, h, c] = tr.b[i];
        // fade boxes in/out at the ends of each track
        const a = Math.min(1, (i + 1) / 5, (tr.b.length - i) / 5);
        out.push({ id: gid(k, tr.id), x, y, w, h, conf: c, a });
      }
      return out;
    },
    footAt(id, t) {
      if (t < 0) return null;
      const [k, lid] = local(id);
      const [kt, vt] = split(t);
      if (kt !== k) return null;
      const b = boxAt(trackById.get(lid), frameOf(vt));
      return b ? [b[0] + b[2] / 2, b[1] + b[3]] : null;
    },
    events(T) {
      if (T < 0) return [];
      const [k, vt] = split(T);
      while (evCache.length < k) {
        const kk = evCache.length;
        evCache.push(loopEvents.map((e) => ({ ...e, t: e.t + kk * D, id: gid(kk, e.id) })));
      }
      const out = [];
      for (let i = 0; i < k; i++) out.push(...evCache[i]);
      for (const e of loopEvents) { if (e.t > vt) break; out.push({ ...e, t: e.t + k * D, id: gid(k, e.id) }); }
      return out;
    },
  };
}
