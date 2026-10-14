// Entry for the pure-code slide: the camera image is a three.js scene rendered live.
// URL options (mainly for the MP4 export): ?q=high|medium|low, ?blur=0|2 (export motion blur sub-frames).
import { runSlide } from './slide/app.js';
import { createSimFeed } from './sim/feed_sim3d.js';

const q = new URLSearchParams(location.search);
runSlide((host) => createSimFeed(host, {
  seed: 7,
  quality: q.get('q') || 'high',
  motionBlur: q.has('blur') ? +q.get('blur') : 2,
}));
