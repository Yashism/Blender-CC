"""Signed-distance sculpting for the v2 characters (pure numpy, plus OpenVDB for meshing).

A character body is a list of primitives (spheres, ellipsoids, capsules, round cones, rounded
boxes) combined with smooth unions and smooth subtractions, so the forms are soft and blended
(no seams at the shoulders, neck or hips) and every size is exact, in metres. The field is
sampled on a voxel grid and turned into a quad mesh with OpenVDB (bundled with Blender), then
remeshed by the caller.

    S = Sculpt()
    S.add(ellipsoid((0, 0, 0.55), (0.24, 0.2, 0.22)), k=0.0)       # first shape
    S.add(capsule((0.17, 0, 0.82), (0.36, 0, 0.82), 0.055), k=0.04)  # blended in over 4 cm
    S.sub(sphere((0.075, -0.17, 1.1), 0.06), k=0.015)                 # an eye socket
    verts, quads = S.mesh(voxel=0.005)

Primitives are functions of point arrays (X, Y, Z of any matching shape), so the same shapes can
be evaluated on mesh vertices later (for colour regions, weights, masks).
"""
import numpy as np


# ------------------------------------------------------------------ helpers

def _v(a):
    return np.asarray(a, dtype=np.float64)


def rot_matrix(rx=0.0, ry=0.0, rz=0.0):
    """XYZ Euler (degrees) -> 3x3 rotation (applied as R @ p, i.e. extrinsic X then Y then Z)."""
    rx, ry, rz = np.radians([rx, ry, rz])
    cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx


def _local(X, Y, Z, c, R=None):
    """Points relative to c, in the primitive's local frame (inverse rotation)."""
    x, y, z = X - c[0], Y - c[1], Z - c[2]
    if R is None:
        return x, y, z
    Ri = np.asarray(R).T
    return (Ri[0, 0] * x + Ri[0, 1] * y + Ri[0, 2] * z,
            Ri[1, 0] * x + Ri[1, 1] * y + Ri[1, 2] * z,
            Ri[2, 0] * x + Ri[2, 1] * y + Ri[2, 2] * z)


# ------------------------------------------------------------------ primitives
# Every primitive carries axis-aligned bounds (.lo, .hi) so the mesher can skip it in voxel
# slabs it cannot reach.

def _bounded(f, lo, hi):
    f.lo, f.hi = np.asarray(lo, float), np.asarray(hi, float)
    return f


def sphere(c, r):
    c = _v(c)
    return _bounded(lambda X, Y, Z: np.sqrt((X - c[0]) ** 2 + (Y - c[1]) ** 2 + (Z - c[2]) ** 2) - r,
                    c - r, c + r)


def ellipsoid(c, radii, R=None):
    """Approximate ellipsoid distance (iq's k0*(k0-1)/k1 form): exact on the surface, good
    enough near it for blending."""
    c, r = _v(c), _v(radii)

    def f(X, Y, Z):
        x, y, z = _local(X, Y, Z, c, R)
        k0 = np.sqrt((x / r[0]) ** 2 + (y / r[1]) ** 2 + (z / r[2]) ** 2)
        k1 = np.sqrt((x / r[0] ** 2) ** 2 + (y / r[1] ** 2) ** 2 + (z / r[2] ** 2) ** 2)
        return k0 * (k0 - 1.0) / np.maximum(k1, 1e-9)
    m = r.max() if R is not None else r
    return _bounded(f, c - m, c + m)


def capsule(a, b, r):
    return round_cone(a, b, r, r)


def round_cone(a, b, ra, rb):
    """A capsule whose radius goes from ra at a to rb at b (sphere-swept, tapering)."""
    a, b = _v(a), _v(b)
    ba = b - a
    L2 = float(ba @ ba)

    def f(X, Y, Z):
        px, py, pz = X - a[0], Y - a[1], Z - a[2]
        h = np.clip((px * ba[0] + py * ba[1] + pz * ba[2]) / L2, 0.0, 1.0)
        dx, dy, dz = px - ba[0] * h, py - ba[1] * h, pz - ba[2] * h
        return np.sqrt(dx * dx + dy * dy + dz * dz) - (ra + (rb - ra) * h)
    m = max(ra, rb)
    return _bounded(f, np.minimum(a, b) - m, np.maximum(a, b) + m)


def chain(points, radii):
    """A tube through several points with a radius per point (blended round cones)."""
    parts = [round_cone(points[i], points[i + 1], radii[i], radii[i + 1]) for i in range(len(points) - 1)]

    def f(X, Y, Z):
        d = parts[0](X, Y, Z)
        for p in parts[1:]:
            d = np.minimum(d, p(X, Y, Z))
        return d
    return _bounded(f, np.min([p.lo for p in parts], 0), np.max([p.hi for p in parts], 0))


def round_box(c, half, r, R=None):
    c, h = _v(c), _v(half)

    def f(X, Y, Z):
        x, y, z = _local(X, Y, Z, c, R)
        qx, qy, qz = np.abs(x) - h[0] + r, np.abs(y) - h[1] + r, np.abs(z) - h[2] + r
        out = np.sqrt(np.maximum(qx, 0) ** 2 + np.maximum(qy, 0) ** 2 + np.maximum(qz, 0) ** 2)
        return out + np.minimum(np.maximum(qx, np.maximum(qy, qz)), 0.0) - r
    m = float(np.linalg.norm(h))
    return _bounded(f, c - m, c + m)


def scaled(f, c, s):
    """f squashed / stretched by s = (sx, sy, sz) about c (approximate distance, fine for
    flattened ears, paddle shapes)."""
    c, s = _v(c), _v(s)
    m = float(s.min())
    g = lambda X, Y, Z: f(c[0] + (X - c[0]) / s[0], c[1] + (Y - c[1]) / s[1], c[2] + (Z - c[2]) / s[2]) * m
    return _bounded(g, c + (f.lo - c) * s, c + (f.hi - c) * s)


def offset(f, r):
    """Grow (r > 0) or shrink the shape by r."""
    g = lambda X, Y, Z: f(X, Y, Z) - r
    return _bounded(g, f.lo - max(r, 0), f.hi + max(r, 0))


def shell(f, outer, inner=0.0):
    """A hollow layer between f grown by `inner` and f grown by `outer` (clothes)."""
    g = lambda X, Y, Z: np.maximum(f(X, Y, Z) - outer, -(f(X, Y, Z) - inner))
    return _bounded(g, f.lo - outer, f.hi + outer)


def union(parts, k):
    """Smooth union of several primitives as one primitive."""
    def g(X, Y, Z):
        d = parts[0](X, Y, Z)
        for p in parts[1:]:
            d = smin(d, p(X, Y, Z), k)
        return d
    return _bounded(g, np.min([p.lo for p in parts], 0), np.max([p.hi for p in parts], 0))


def mirror_x(f):
    """The primitive and its mirror image across x = 0 (for symmetric limbs)."""
    m = max(abs(f.lo[0]), abs(f.hi[0]))
    return _bounded(lambda X, Y, Z: np.minimum(f(X, Y, Z), f(-X, Y, Z)),
                    (-m, f.lo[1], f.lo[2]), (m, f.hi[1], f.hi[2]))


# ------------------------------------------------------------------ booleans

def smin(a, b, k):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


class Sculpt:
    """An ordered list of smooth booleans. bbox = ((x0, y0, z0), (x1, y1, z1)) bounds the grid."""

    def __init__(self, bbox=None):
        self.ops = []
        self.bbox = bbox

    def add(self, f, k=0.03, name=None):
        self.ops.append(("add", f, k, name))
        return self

    def sub(self, f, k=0.01, name=None):
        self.ops.append(("sub", f, k, name))
        return self

    def inter(self, f, k=0.01, name=None):
        self.ops.append(("int", f, k, name))
        return self

    def field(self, X, Y, Z, x_slab=None):
        """The combined distance at the points. x_slab: the x of a constant-x slab (lets the
        primitives that cannot reach it be skipped)."""
        d = None
        for mode, f, k, _ in self.ops:
            if x_slab is not None and d is not None and hasattr(f, "lo"):
                if x_slab < f.lo[0] - k - 0.02 or x_slab > f.hi[0] + k + 0.02:
                    continue
            v = f(X, Y, Z)
            if d is None:
                d = v if mode == "add" else None
                continue
            if mode == "add":
                d = smin(d, v, k)
            elif mode == "sub":
                d = smax(d, -v, k)
            else:
                d = smax(d, v, k)
        return d

    def mesh(self, voxel=0.005, bbox=None, pad=0.03):
        """(verts (N,3) float32, quads (M,4) int) of the zero level set."""
        import openvdb as vdb
        bbox = bbox or self.bbox
        if bbox is None:                                  # the union of the added shapes
            adds = [f for m, f, k, _ in self.ops if m == "add"]
            bbox = (np.min([f.lo for f in adds], 0), np.max([f.hi for f in adds], 0))
        (x0, y0, z0), (x1, y1, z1) = bbox
        xs = np.arange(x0 - pad, x1 + pad, voxel)
        ys = np.arange(y0 - pad, y1 + pad, voxel)
        zs = np.arange(z0 - pad, z1 + pad, voxel)
        d = np.empty((len(xs), len(ys), len(zs)), dtype=np.float32)
        Y2, Z2 = np.meshgrid(ys, zs, indexing="ij")
        for i, x in enumerate(xs):                      # slab by slab: bounded memory
            X2 = np.full_like(Y2, x)
            d[i] = self.field(X2, Y2, Z2, x_slab=x)
        g = vdb.FloatGrid(background=float(voxel * 4))
        g.copyFromArray(d, ijk=(0, 0, 0), tolerance=0)
        g.transform = vdb.createLinearTransform(voxelSize=voxel)
        pts, quads = g.convertToQuads(isovalue=0.0)
        pts = np.asarray(pts, dtype=np.float64) + np.array([xs[0], ys[0], zs[0]])
        return pts.astype(np.float32), np.asarray(quads, dtype=np.int64)
