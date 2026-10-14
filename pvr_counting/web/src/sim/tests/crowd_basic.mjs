// node src/sim/tests/crowd_basic.mjs  — determinism, separation, one crossing each, traffic mix
import { createCrowd } from '../crowd.js';
const t0 = Date.now();
const c = createCrowd({ seed: 7, horizon: 3600 });
const ms = Date.now() - t0;
const c2 = createCrowd({ seed: 7, horizon: 3600 });
const same = c.events.length === c2.events.length && c.events.every((e, i) => e.t === c2.events[i].t && e.id === c2.events[i].id);
const nIn = c.events.filter((e) => e.dir === 'in').length;
const perAgent = new Map();
for (const e of c.events) perAgent.set(e.id, (perAgent.get(e.id) || 0) + 1);
const missing = c.agents.filter((a) => !perAgent.has(a.id)).length;
const dup = [...perAgent.values()].filter((n) => n > 1).length;
// separation between different groups, visible part only
let minSep = 9, worst = null;
for (let t = 0; t < 900; t += 0.05) {
  const act = c.activeAt(t).map((a) => [a, c.stateAt(a, t)]).filter(([, s]) => s && s.z > -7.0);
  for (let i = 0; i < act.length; i++) for (let j = i + 1; j < act.length; j++) {
    if (act[i][0].group === act[j][0].group) continue;
    const d = Math.hypot(act[i][1].x - act[j][1].x, act[i][1].z - act[j][1].z);
    if (d < minSep) { minSep = d; worst = [t.toFixed(2), act[i][0].id, act[j][0].id]; }
  }
}
// within-group spacing
let minGroup = 9;
for (let t = 0; t < 900; t += 0.05) {
  const act = c.activeAt(t).map((a) => [a, c.stateAt(a, t)]).filter(([, s]) => s && s.z > -7.0);
  for (let i = 0; i < act.length; i++) for (let j = i + 1; j < act.length; j++) {
    if (act[i][0].group !== act[j][0].group) continue;
    minGroup = Math.min(minGroup, Math.hypot(act[i][1].x - act[j][1].x, act[i][1].z - act[j][1].z));
  }
}
const kids = c.agents.filter((a) => a.human.kind === 'child').length;
let maxVisible = 0;
for (let t = 0; t < 900; t += 0.5) maxVisible = Math.max(maxVisible, c.activeAt(t).filter((a) => { const s = c.stateAt(a, t); return s && s.z < 1.4 && s.z > -5.5; }).length);
console.log(JSON.stringify({
  buildMs: ms, deterministic: same, agents: c.agents.length, events: c.events.length, in: nIn, out: c.events.length - nIn,
  perMinIn: (nIn / 60).toFixed(1), perMinOut: ((c.events.length - nIn) / 60).toFixed(1),
  agentsWithoutCrossing: missing, agentsCrossingTwice: dup, minSeparationOtherGroups: minSep.toFixed(3), worst,
  minSeparationWithinGroup: minGroup.toFixed(3), childrenPct: ((100 * kids) / c.agents.length).toFixed(1), maxInView: maxVisible,
}, null, 1));
