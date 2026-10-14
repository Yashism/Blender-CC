// Entry for the AI-footage slide: real CCTV-style clip + offline YOLO tracks.
import { runSlide } from './slide/app.js';
import { createVideoFeed } from './slide/feed_video.js';

function blobUrl(id, type) {
  const el = document.getElementById(id);
  if (!el) return null;
  const bin = atob(el.textContent.trim());
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return URL.createObjectURL(new Blob([bytes], { type }));
}

runSlide(async (host) => {
  const data = JSON.parse(document.getElementById('tracks').textContent);
  const sources = [];
  // an external clip can be given with ?video=... (used by the headless MP4 export)
  const ext = new URLSearchParams(location.search).get('video');
  if (ext) sources.push({ src: ext });
  const mp4 = blobUrl('clip-mp4', 'video/mp4');
  if (mp4) sources.push({ src: mp4, type: 'video/mp4; codecs="avc1.640029"' });
  return createVideoFeed(host, { sources, data });
});
