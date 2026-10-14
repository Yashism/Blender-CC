"""RTLS film: the forklifts' route network and a simulated shift. Pure Python, no Blender.

The network follows the floor plan in layout.py: every aisle's centre line (with a stop at each bay), the south
and north cross-aisles, the traffic lane, the dock corridors, the staging lane heads, the trailer on the open dock
and the charging bays. A shift is simulated for every truck: picks (rack -> staging), loads (staging -> trailer),
putaways (dock apron -> rack), with fork time at every stop, a few waits at the busy junctions, and one truck
standing idle at staging for twelve minutes. The result is a timed track per truck.

    track = simulate()["MHE-07"]      # list of (t, x, y, heading, state)
    pose_at(track, t)                 # -> (x, y, heading, state)
"""
import heapq
import math
import random

from rtls import layout as L

V_MAX = 2.4            # m/s on straights
V_TURN = 1.1           # m/s through corners
ACCEL = 0.8            # m/s^2
FILLET = 1.4           # corner radius (m)
DT = 0.25              # track sample step (s)
SHIFT = 2 * 3600.0     # simulated time (s)

Y_S = L.RACK_Y0 - 2.0  # south cross-aisle centre line
Y_N = L.RACK_Y1 + 2.0  # north cross-aisle centre line


# ------------------------------------------------------------------------------------ the network
def network():
    nodes, edges = {}, {}

    def node(k, x, y):
        nodes[k] = (x, y)

    def edge(a, b):
        d = math.dist(nodes[a], nodes[b])
        edges.setdefault(a, []).append((b, d))
        edges.setdefault(b, []).append((a, d))

    lx = L.LANE_X
    for a in "ABCDE":
        x = L.aisle_cx(a)
        node(("S", a), x, Y_S)
        node(("N", a), x, Y_N)
        prev = ("S", a)
        for i in range(L.N_BAYS):
            node((a, i), x, L.RACK_Y0 + (i + 0.5) * L.BAY)
            edge(prev, (a, i))
            prev = (a, i)
        edge(prev, ("N", a))
    node(("S", "L"), lx, Y_S)
    node(("N", "L"), lx, Y_N)
    for row in ("S", "N"):
        seq = [(row, a) for a in "ABCDE"] + [(row, "L")]
        for p, q in zip(seq, seq[1:]):
            edge(p, q)
    # traffic lane, with junctions for every dock corridor and staging lane
    ys = sorted(set([Y_S, Y_N] + list(L.DOCKS_Y) + list(L.STAGING["lanes"]) + [-11.0, 11.0]))
    lane = []
    for y in ys:
        k = ("S", "L") if y == Y_S else ("N", "L") if y == Y_N else ("lane", round(y, 2))
        if k not in nodes:
            node(k, lx, y)
        lane.append(k)
    for p, q in zip(lane, lane[1:]):
        edge(p, q)
    # dock corridors: lane -> apron -> leveller (-> into the trailer on the open dock)
    for k, yd in enumerate(L.DOCKS_Y):
        node(("apron", k), L.APRON_X + 1.2, yd)
        node(("dock", k), L.X1 - 1.4, yd)
        edge(("lane", round(yd, 2)), ("apron", k))
        edge(("apron", k), ("dock", k))
        if k == L.TRAILER_DOCK:
            node("trailer", L.X1 + 4.5, yd)
            edge(("dock", k), "trailer")
    # staging lane heads (a truck stands here to drop or pick a pallet at the lane's west end)
    for i, ys_ in enumerate(L.STAGING["lanes"]):
        node(("stage", i), L.STAGE_HEAD_X, ys_)
        edge(("lane", round(ys_, 2)), ("stage", i))
    # charging bays under the office, reached from the north end of the lane
    node("charge_j", L.CHARGE["x"][0] + 1.0, Y_N)
    edge(("N", "L"), "charge_j")
    for k in range(3):
        x = L.CHARGE["x"][0] + 1.7 + k * 2.6
        node(("charge", k), x, 12.6)
        node(("charge_in", k), x, Y_N)
        edge("charge_j" if k == 0 else ("charge_in", k - 1), ("charge_in", k))
        edge(("charge_in", k), ("charge", k))
    # drive-in door on the east wall, out to the yard
    dy = L.DRIVE_IN["y"]
    node("door_j", lx, dy)
    node("door_in", L.X1 - 0.8, dy)
    node("yard", L.X1 + 7.0, dy)
    edge(("S", "L"), "door_j")
    edge("door_j", "door_in")
    edge("door_in", "yard")
    return nodes, edges


def route(nodes, edges, a, b):
    """Shortest path (Dijkstra) from node a to node b, as a list of node keys."""
    dist = {a: 0.0}
    prev = {}
    pq = [(0.0, 0, a)]
    n = 0
    while pq:
        d, _, u = heapq.heappop(pq)
        if u == b:
            break
        if d > dist.get(u, 1e18):
            continue
        for v, w in edges.get(u, []):
            nd = d + w
            if nd < dist.get(v, 1e18):
                dist[v] = nd
                prev[v] = u
                n += 1
                heapq.heappush(pq, (nd, n, v))
    path = [b]
    while path[-1] != a:
        path.append(prev[path[-1]])
    return path[::-1]


# ------------------------------------------------------------------------------------ geometry
def fillet(pts, r=FILLET, seg=6):
    """Round every corner of a polyline with an arc of radius up to r. Returns (points, is_corner flags)."""
    if len(pts) < 3:
        return list(pts), [False] * len(pts)
    out, flags = [pts[0]], [False]
    for i in range(1, len(pts) - 1):
        p0, p1, p2 = pts[i - 1], pts[i], pts[i + 1]
        a = (p0[0] - p1[0], p0[1] - p1[1])
        b = (p2[0] - p1[0], p2[1] - p1[1])
        la, lb = math.hypot(*a), math.hypot(*b)
        if la < 1e-6 or lb < 1e-6:
            continue
        ua, ub = (a[0] / la, a[1] / la), (b[0] / lb, b[1] / lb)
        cosang = max(-1.0, min(1.0, ua[0] * ub[0] + ua[1] * ub[1]))
        if cosang < -0.999:                        # straight through
            out.append(p1)
            flags.append(False)
            continue
        cut = min(r, la * 0.45, lb * 0.45)
        s = (p1[0] + ua[0] * cut, p1[1] + ua[1] * cut)
        e = (p1[0] + ub[0] * cut, p1[1] + ub[1] * cut)
        for k in range(seg + 1):                   # quadratic Bezier s -> p1 -> e (close to an arc)
            t = k / seg
            x = (1 - t) ** 2 * s[0] + 2 * (1 - t) * t * p1[0] + t * t * e[0]
            y = (1 - t) ** 2 * s[1] + 2 * (1 - t) * t * p1[1] + t * t * e[1]
            out.append((x, y))
            flags.append(True)
    out.append(pts[-1])
    flags.append(False)
    return out, flags


def drive(pts, flags, t0, v_max=V_MAX, v_turn=V_TURN):
    """Time a path: accelerate, cruise, slow for corners, stop at the end. Returns samples (t, x, y, heading)."""
    n = len(pts)
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(n - 1)]
    vlim = [v_turn if f else v_max for f in flags]
    vlim[0] = vlim[-1] = 0.0
    v = vlim[:]
    for i in range(1, n):                          # forward pass: acceleration limit
        v[i] = min(v[i], math.sqrt(v[i - 1] ** 2 + 2 * ACCEL * seg[i - 1]))
    for i in range(n - 2, -1, -1):                 # backward pass: braking limit
        v[i] = min(v[i], math.sqrt(v[i + 1] ** 2 + 2 * ACCEL * seg[i]))
    out = []
    t = t0
    for i in range(n - 1):
        va, vb = max(v[i], 0.15), max(v[i + 1], 0.15)
        dt = seg[i] / ((va + vb) / 2) if seg[i] > 0 else 0.0
        h = math.atan2(pts[i + 1][1] - pts[i][1], pts[i + 1][0] - pts[i][0])
        out.append((t, pts[i][0], pts[i][1], h))
        t += dt
    if out:
        out.append((t, pts[-1][0], pts[-1][1], out[-1][3]))
    return out


# ------------------------------------------------------------------------------------ the shift
CHOKE = {("S", "L"): 0.45, ("lane", round(L.DOCKS_Y[L.TRAILER_DOCK], 2)): 0.55, ("apron", L.TRAILER_DOCK): 0.4,
         ("S", "E"): 0.35, ("N", "L"): 0.3}
AISLE_WEIGHT = {"A": 0.5, "B": 1.4, "C": 0.8, "D": 2.1, "E": 1.1}      # slotting: fast movers live in D and B


def wander(pts, r, amp=0.22, offset=0.0, taper=2.5):
    """Drivers don't follow the centre line: a constant offset for the leg plus a slow drift along it,
    both easing to zero at the two ends of the leg."""
    if len(pts) < 2:
        return pts
    s = [0.0]
    for a, b in zip(pts, pts[1:]):
        s.append(s[-1] + math.dist(a, b))
    total = s[-1]
    waves = [(r.uniform(3.5, 9.0), r.uniform(0, 6.28), amp * r.uniform(0.5, 1.0)) for _ in range(2)]
    out = []
    n = len(pts)
    for i, p in enumerate(pts):
        a = pts[max(0, i - 1)]
        b = pts[min(n - 1, i + 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        ln = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / ln, dx / ln
        ease = min(1.0, s[i] / taper, (total - s[i]) / taper)
        d = (offset + sum(A * math.sin(2 * math.pi * s[i] / lam + ph) for lam, ph, A in waves)) * max(0.0, ease)
        out.append((p[0] + nx * d, p[1] + ny * d))
    return out


def densify(pts, step=0.5):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) / step))
        for k in range(1, n + 1):
            out.append((a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n))
    return out


def simulate(seed=5, shift=SHIFT):
    nodes, edges = network()
    bays = [(a, i) for a in "ABCDE" for i in range(L.N_BAYS)]
    bay_w = [AISLE_WEIGHT[a] * (1.6 if i in (0, 1, L.N_BAYS - 2, L.N_BAYS - 1) else 1.0) for a, i in bays]
    starts = {"MHE-01": ("B", 4), "MHE-02": ("D", 2), "MHE-03": ("S", "C"), "MHE-04": ("stage", 1),
              "MHE-05": ("apron", 1), "MHE-06": ("N", "D"), "MHE-07": ("lane", round(L.DOCKS_Y[0], 2)),
              "MHE-08": ("charge", 0)}
    tracks = {}
    for ti, name in enumerate(L.FLEET):
        r = random.Random(seed * 100 + ti)
        v_max = r.uniform(1.9, 2.7)                # every driver has their own pace
        v_turn = r.uniform(0.8, 1.3)
        cur = starts[name]
        cur_xy = nodes[cur]
        t = 0.0
        raw = []                                   # (t, x, y, heading, state)
        h = 0.0
        if name == "MHE-08":                       # on charge for the first 40 minutes
            raw.append((t, *cur_xy, math.pi / 2, "charging"))
            t += 2400.0
            raw.append((t, *cur_xy, math.pi / 2, "charging"))
        while t < shift:
            kind = r.choices(("pick", "load", "putaway"), (0.45, 0.3, 0.25))[0]
            if kind == "pick":
                legs = [(r.choices(bays, bay_w)[0], "fork"), (("stage", r.randrange(4)), "drop")]
            elif kind == "load":
                legs = [(("stage", r.randrange(4)), "fork"), ("trailer", "drop")]
            else:
                legs = [(("apron", r.choice((0, 2))), "fork"), (r.choices(bays, bay_w)[0], "drop")]
            for goal, act in legs:
                if goal == cur:
                    continue
                keys = route(nodes, edges, cur, goal)
                gx, gy = nodes[goal]
                jit = 0.6 if goal == "trailer" or goal[0] in ("stage", "apron") else 0.25
                goal_xy = (gx + r.uniform(-jit, jit), gy + r.uniform(-jit * 0.5, jit * 0.5))
                pts = [cur_xy] + [nodes[k] for k in keys[1:-1]] + [goal_xy]
                fp, fl = fillet(pts, r=r.uniform(0.9, 2.2))
                dense = densify(fp)
                dflags = []
                for i, p in enumerate(dense):              # corner flags carried over to the dense points
                    j = min(range(len(fp)), key=lambda k: (fp[k][0] - p[0]) ** 2 + (fp[k][1] - p[1]) ** 2)
                    dflags.append(fl[j])
                dense = wander(dense, r, amp=r.uniform(0.12, 0.3), offset=r.uniform(-0.45, 0.45))
                samples = drive(dense, dflags, t, v_max * r.uniform(0.9, 1.08), v_turn)
                waits = []
                for k in keys[1:-1]:
                    if k in CHOKE and r.random() < CHOKE[k]:
                        waits.append((nodes[k], r.uniform(4.0, 35.0)))
                if r.random() < 0.3 and len(samples) > 20:   # a give-way stop somewhere along the leg
                    q = samples[r.randrange(5, len(samples) - 5)]
                    waits.append(((q[1], q[2]), r.uniform(2.0, 12.0)))
                shift_t = 0.0
                for (tt, xx, yy, hh) in samples:
                    for (wx, wy), wdur in list(waits):
                        if math.hypot(xx - wx, yy - wy) < 1.0:
                            raw.append((tt + shift_t, xx, yy, hh, "waiting"))
                            shift_t += wdur
                            waits.remove(((wx, wy), wdur))
                    raw.append((tt + shift_t, xx, yy, hh, "moving"))
                t = samples[-1][0] + shift_t if samples else t
                h = samples[-1][3] if samples else h
                cur, cur_xy = goal, goal_xy
                dwell = r.uniform(15.0, 55.0)
                raw.append((t, *goal_xy, h, act))
                t += dwell
                raw.append((t, *goal_xy, h, act))
            if name == "MHE-05" and 3000.0 < t < 3600.0:      # the one that waits 12 minutes at staging
                raw.append((t, *cur_xy, h, "idle"))
                t += 720.0
                raw.append((t, *cur_xy, h, "idle"))
        tracks[name] = resample(raw)
    return tracks


def resample(raw, dt=DT):
    """Even time steps (linear between samples; heading from the earlier sample)."""
    raw.sort(key=lambda s: s[0])
    out = []
    j = 0
    t = raw[0][0]
    end = raw[-1][0]
    while t <= end:
        while j < len(raw) - 2 and raw[j + 1][0] <= t:
            j += 1
        a, b = raw[j], raw[min(j + 1, len(raw) - 1)]
        span = b[0] - a[0]
        u = 0.0 if span <= 1e-9 else min(1.0, (t - a[0]) / span)
        out.append((t, a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u, a[3], a[4]))
        t += dt
    return out


def pose_at(track, t):
    i = max(0, min(len(track) - 1, int(round((t - track[0][0]) / DT))))
    s = track[i]
    return s[1], s[2], s[3], s[4]


def window(track, t0, t1):
    i0 = max(0, int((t0 - track[0][0]) / DT))
    i1 = min(len(track), int((t1 - track[0][0]) / DT) + 1)
    return track[i0:i1]


if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    tr = simulate()
    for n, track in tr.items():
        st = {}
        for s in track:
            st[s[4]] = st.get(s[4], 0) + DT
        dist = sum(math.dist(track[i][1:3], track[i + 1][1:3]) for i in range(len(track) - 1))
        print(n, len(track), f"{dist / 1000:.1f} km", {k: round(v / 60, 1) for k, v in st.items()})
