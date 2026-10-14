// Entry for the pure-code slide: the camera image is a three.js scene rendered live.
import { runSlide } from './slide/app.js';
import { createSimFeed } from './sim/feed_sim3d.js';

runSlide((host) => createSimFeed(host, { seed: 7, quality: 'high' }));
