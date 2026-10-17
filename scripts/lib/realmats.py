"""Photoreal procedural materials for the RAMS hero films (Cycles).

Everything is built at real-world scale (noise scales are per metre) so close-ups and wide
shots hold up. Wear is layered the way it happens in a working warehouse:

    base finish -> orange peel -> edge chips (primer, then bare steel) -> scuffs in the
    fork zone -> grime in crevices and near the floor -> dust on everything that faces up

Bitmaps come from scripts/w01/make_textures.py (assets/textures/<set>/).
"""
import os

import bpy

from .palette import srgb_to_linear

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEX = os.path.join(ROOT, "assets", "textures", "w01")


# ------------------------------------------------------------------ node plumbing

def lin(hexstr, a=1.0):
    h = hexstr.lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4)) + (a,)


class G:
    """Tiny node-graph builder: G(mat).n('ShaderNodeTexNoise', Scale=40) etc."""

    def __init__(self, mat):
        self.mat = mat
        self.nt = mat.node_tree
        for n in list(self.nt.nodes):
            self.nt.nodes.remove(n)
        self.out = self.nt.nodes.new("ShaderNodeOutputMaterial")
        self._x = 0

    def _set(self, sock, v):
        if isinstance(v, bpy.types.NodeSocket):
            self.nt.links.new(v, sock)
        elif isinstance(v, bpy.types.Node):
            self.nt.links.new(v.outputs[0], sock)
        else:
            if isinstance(v, (int, float)) and hasattr(sock.default_value, "__len__"):
                n = len(sock.default_value)
                v = (v,) * n if n != 4 else (v, v, v, 1.0)
            elif isinstance(v, tuple) and hasattr(sock.default_value, "__len__"):
                if len(sock.default_value) == 4 and len(v) == 3:
                    v = (*v, 1.0)
                elif len(sock.default_value) == 3 and len(v) == 4:
                    v = v[:3]
            sock.default_value = v

    def n(self, kind, *args, props=None, **kw):
        node = self.nt.nodes.new(kind)
        node.location = (self._x, 0)
        self._x -= 40
        for k, v in (props or {}).items():
            setattr(node, k, v)
        for i, v in enumerate(args):
            if v is not None:
                self._set(node.inputs[i], v)
        for k, v in kw.items():
            self._set(node.inputs[k.replace("_", " ")], v)
        return node

    # -- maths -------------------------------------------------------------
    def math(self, op, a, b=None, clamp=False):
        node = self.n("ShaderNodeMath", props={"operation": op, "use_clamp": clamp})
        self._set(node.inputs[0], a)
        if b is not None:
            self._set(node.inputs[1], b)
        return node.outputs[0]

    def add(self, a, b, clamp=False):
        return self.math("ADD", a, b, clamp)

    def mul(self, a, b, clamp=False):
        return self.math("MULTIPLY", a, b, clamp)

    def sub(self, a, b, clamp=False):
        return self.math("SUBTRACT", a, b, clamp)

    def inv(self, a):
        return self.math("SUBTRACT", 1.0, a, True)

    def mr(self, v, a, b, c=0.0, d=1.0, clamp=True, smooth=False):
        node = self.n("ShaderNodeMapRange", v, a, b, c, d,
                      props={"clamp": clamp, "interpolation_type": "SMOOTHSTEP" if smooth else "LINEAR"})
        return node.outputs[0]

    def mixf(self, fac, a, b):
        node = self.n("ShaderNodeMix", props={"data_type": "FLOAT", "clamp_factor": True})
        self._set(node.inputs[0], fac)
        self._set(node.inputs[2], a)
        self._set(node.inputs[3], b)
        return node.outputs[0]

    def mixc(self, fac, a, b, blend="MIX"):
        node = self.n("ShaderNodeMix", props={"data_type": "RGBA", "blend_type": blend,
                                              "clamp_factor": True, "clamp_result": blend != "MIX"})
        self._set(node.inputs[0], fac)
        self._set(node.inputs[6], a)
        self._set(node.inputs[7], b)
        return node.outputs[2]

    def mixs(self, fac, a, b):
        node = self.n("ShaderNodeMixShader")
        self._set(node.inputs[0], fac)
        self._set(node.inputs[1], a)
        self._set(node.inputs[2], b)
        return node.outputs[0]

    # -- coordinates and textures ------------------------------------------------
    def coords(self, space="Object", seed_offset=True, scale=(1, 1, 1)):
        tc = self.n("ShaderNodeTexCoord")
        v = tc.outputs[space]
        if seed_offset:
            oi = self.n("ShaderNodeObjectInfo")
            off = self.n("ShaderNodeVectorMath", oi.outputs["Random"], (137.0, 59.0, 23.0),
                         props={"operation": "MULTIPLY"})
            v = self.n("ShaderNodeVectorMath", v, off.outputs[0], props={"operation": "ADD"}).outputs[0]
        if scale != (1, 1, 1):
            v = self.n("ShaderNodeVectorMath", v, scale, props={"operation": "MULTIPLY"}).outputs[0]
        return v

    def noise(self, vec, scale, detail=4.0, rough=0.55, distortion=0.0, dims="3D", out="Fac"):
        node = self.n("ShaderNodeTexNoise", props={"noise_dimensions": dims})
        self._set(node.inputs["Vector"], vec)
        self._set(node.inputs["Scale"], scale)
        self._set(node.inputs["Detail"], detail)
        self._set(node.inputs["Roughness"], rough)
        self._set(node.inputs["Distortion"], distortion)
        return node.outputs[out]

    def voronoi(self, vec, scale, feature="F1", out="Distance", rand=1.0):
        node = self.n("ShaderNodeTexVoronoi", props={"feature": feature})
        self._set(node.inputs["Vector"], vec)
        self._set(node.inputs["Scale"], scale)
        node.inputs["Randomness"].default_value = rand
        return node.outputs[out]

    def wave(self, vec, scale, distortion=0.0, detail=2.0, kind="BANDS", direction="X", profile="SIN"):
        props = {"wave_type": kind, "wave_profile": profile}
        props["bands_direction" if kind == "BANDS" else "rings_direction"] = direction
        node = self.n("ShaderNodeTexWave", props=props)
        self._set(node.inputs["Vector"], vec)
        self._set(node.inputs["Scale"], scale)
        self._set(node.inputs["Distortion"], distortion)
        self._set(node.inputs["Detail"], detail)
        return node.outputs["Fac"]

    def image(self, name, vec=None, interp="Linear", ext="REPEAT", colorspace="sRGB", out="Color"):
        path = os.path.join(TEX, name)
        img = bpy.data.images.get(name) or bpy.data.images.load(path, check_existing=True)
        img.colorspace_settings.name = colorspace
        node = self.n("ShaderNodeTexImage", vec, props={"image": img, "interpolation": interp,
                                                          "extension": ext})
        return node.outputs[out]

    def geo(self, out):
        return self.n("ShaderNodeNewGeometry").outputs[out]

    def sep(self, vec):
        s = self.n("ShaderNodeSeparateXYZ", vec)
        return s.outputs[0], s.outputs[1], s.outputs[2]

    def obj_normal(self):
        vt = self.n("ShaderNodeVectorTransform", self.geo("Normal"),
                    props={"vector_type": "NORMAL", "convert_from": "WORLD", "convert_to": "OBJECT"})
        return vt.outputs[0]

    def edge_mask(self, radius=0.003, lo=0.03, hi=0.25, samples=6):
        """Convex/concave edge factor from the Bevel node (Cycles only)."""
        bv = self.n("ShaderNodeBevel", radius, props={"samples": samples})
        dot = self.n("ShaderNodeVectorMath", bv.outputs[0], self.geo("Normal"),
                     props={"operation": "DOT_PRODUCT"})
        return self.mr(self.inv(dot.outputs["Value"]), lo, hi)

    def ao(self, distance=0.05, samples=8):
        node = self.n("ShaderNodeAmbientOcclusion", (1, 1, 1, 1), distance,
                      props={"samples": samples, "only_local": True})
        return node.outputs["AO"]

    def bump(self, height, strength=0.2, distance=0.001, normal=None):
        node = self.n("ShaderNodeBump", strength, distance, props={"invert": False})
        self._set(node.inputs["Height"], height)
        if normal is not None:
            self._set(node.inputs["Normal"], normal)
        return node.outputs["Normal"]

    def principled(self, **kw):
        return self.n("ShaderNodeBsdfPrincipled", **kw)

    def output(self, shader, displacement=None):
        self._set(self.out.inputs["Surface"], shader)
        if displacement is not None:
            self._set(self.out.inputs["Displacement"], displacement)


def _mat(name):
    m = bpy.data.materials.get(name)
    if m is not None:
        return m, False
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    return m, True


# ------------------------------------------------------------------ shared wear layers

def _grime_dust(g, col, rough, wpos, top_dust=0.6, floor_grime=1.0, ao_dist=0.04, ao_amt=0.7,
                grime_col="#3b342b", dust_col="#a29a8c"):
    """Apply crevice grime, floor-splash grime and top-facing dust. Returns (col, rough, dust)."""
    vec = g.coords("Object")
    n_big = g.noise(vec, 6.0, 6, 0.6)
    # crevice grime
    if ao_amt > 0:
        crev = g.mul(g.inv(g.ao(ao_dist)), ao_amt)
        crev = g.mul(crev, g.mr(n_big, 0.3, 0.7, 0.5, 1.0))
        col = g.mixc(crev, col, lin(grime_col))
        rough = g.mixf(crev, rough, 0.85)
    # splash grime near the floor (world Z)
    if floor_grime > 0:
        _, _, wz = g.sep(wpos)
        low = g.mr(wz, 0.02, 0.45, 1.0, 0.0, smooth=True)
        low = g.mul(low, g.mr(g.noise(vec, 14.0, 8, 0.65), 0.35, 0.75))
        low = g.mul(low, floor_grime)
        col = g.mixc(g.mul(low, 0.75), col, lin("#4a4238"))
        rough = g.mixf(low, rough, 0.8)
    # dust on up-facing surfaces
    dust = 0.0
    if top_dust > 0:
        _, _, nz = g.sep(g.geo("Normal"))
        up = g.mr(nz, 0.55, 0.95)
        dn = g.noise(vec, 30.0, 10, 0.7)
        dust = g.mul(g.mul(up, g.mr(dn, 0.25, 0.7)), top_dust)
        col = g.mixc(dust, col, lin(dust_col))
        rough = g.mixf(dust, rough, 0.95)
    return col, rough, dust


# ------------------------------------------------------------------ steel

def powder_coat(name, color, *, primer="#8a8c88", chip=0.55, scuff_zone=(0.0, 0.7), scuff=1.0,
                holes=False, damage_attr=None, top_dust=0.6, floor_grime=1.0, hero=False,
                gloss=0.36):
    """Powder-coated structural steel (uprights, beams, bracing, guards).

    holes:       alpha-cut teardrop/bracing perforations from bitmaps (non-hero uprights;
                 the object must be an upright built by rack_kit with its front face at x=0).
    damage_attr: name of a colour attribute (0..1) marking a fresh scrape (hero upright).
                 The value node 'dmg_amount' (0..1) grows it.
    """
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    vec = g.coords("Object")
    wpos = g.geo("Position")
    base = lin(color)
    # subtle batch-to-batch / panel variation
    var = g.noise(vec, 2.5, 3, 0.5)
    col = g.mixc(g.mr(var, 0.3, 0.7), g.mixc(1.0, base, (0.92, 0.92, 0.92, 1), "MULTIPLY"),
                 g.mixc(1.0, base, (1.06, 1.06, 1.06, 1), "MULTIPLY"))
    rough = g.add(gloss, g.mul(g.sub(g.noise(vec, 9.0, 6, 0.6), 0.5), 0.18))
    # orange peel micro relief
    peel = g.noise(vec, 1100.0, 2, 0.5)
    nrm = g.bump(peel, 0.12, 0.00015)

    # fork-zone scuffs: short horizontal rub marks (long in plan, a few mm tall), densest low
    _, _, wz = g.sep(wpos)
    zone = g.mr(wz, scuff_zone[1], scuff_zone[0] + 0.05, 0.0, 1.0, smooth=True)
    s1 = g.mr(g.noise(g.coords("Object", True, (2.5, 2.5, 120.0)), 1.0, 3, 0.5), 0.66, 0.74)
    s2 = g.mr(g.noise(g.coords("Object", True, (6.0, 6.0, 420.0)), 1.0, 2, 0.5), 0.68, 0.73)
    patches = g.mr(g.noise(vec, 5.0, 4, 0.6), 0.45, 0.62)
    sc = g.mul(g.add(g.mul(s1, 0.7), s2, True), g.mul(g.mul(zone, scuff), patches))
    col = g.mixc(g.mul(sc, 0.35), col, lin("#b9b8b0"))
    rough = g.mixf(sc, rough, 0.55)
    nrm = g.bump(g.mul(sc, -0.3), 0.15, 0.0001, nrm)

    # chips on edges: primer, and bare steel in the middle of the bigger chips (hero only:
    # the Bevel node is expensive and edges this small never read in wide shots)
    if hero and chip > 0:
        em = g.edge_mask(0.004)
        cn = g.noise(vec, 55.0, 10, 0.72)
        chipf = g.mr(g.add(g.mul(em, 0.7), g.mul(cn, 0.6)), 1.0 - chip * 0.45, 1.05 - chip * 0.45)
        bare = g.mr(g.add(g.mul(em, 0.7), g.mul(cn, 0.6)), 1.08 - chip * 0.45, 1.12 - chip * 0.45)
        col = g.mixc(chipf, col, lin(primer))
        col = g.mixc(bare, col, lin("#6e6f70"))
        rough = g.mixf(chipf, rough, 0.62)
        metal = g.mul(bare, 1.0)
        nrm = g.bump(g.mul(chipf, -1.0), 0.25, 0.0002, nrm)
    else:
        metal = 0.0

    if damage_attr:
        at = g.n("ShaderNodeAttribute", props={"attribute_name": damage_attr, "attribute_type": "GEOMETRY"})
        amt = g.n("ShaderNodeValue")
        amt.name = amt.label = "dmg_amount"
        amt.outputs[0].default_value = 0.0
        d = g.mul(at.outputs["Fac"], amt.outputs[0])
        n1 = g.mr(g.noise(vec, 320.0, 12, 0.75), 0.32, 0.68, -1.0, 1.0)
        n2 = g.mr(g.noise(g.coords("Object", True, (1.0, 1.0, 5.0)), 70.0, 8, 0.7), 0.32, 0.68, -1.0, 1.0)
        brk = g.add(g.mul(n1, 0.45), g.mul(n2, 0.3))
        # paint flaked off along the fold (dark, freshly exposed steel), bright where the tip slid
        flake = g.mr(g.add(d, brk), 0.78, 0.82)
        steel = g.mr(g.add(d, g.mul(brk, 0.8)), 0.98, 1.02)
        # hairline crazing of the powder coat around the fold
        craze = g.voronoi(g.coords("Object", True, (1.0, 1.0, 1.0)), 900.0, "DISTANCE_TO_EDGE", "Distance")
        craze = g.mul(g.mr(craze, 0.022, 0.0), g.mr(g.add(d, g.mul(brk, 0.3)), 0.45, 0.7))
        col = g.mixc(g.mul(craze, 0.55), col, lin("#18202e"))
        col = g.mixc(flake, col, lin("#4d5052"))
        col = g.mixc(steel, col, lin("#b5b8ba"))
        rough = g.mixf(flake, rough, 0.5)
        rough = g.mixf(steel, rough, 0.22)
        metal = g.add(metal, g.add(g.mul(flake, 0.35), g.mul(steel, 0.65)), True)
        scratch = g.noise(g.coords("Object", True, (1.0, 1.0, 900.0)), 1.0, 2, 0.5)
        nrm = g.bump(g.add(g.mul(flake, -0.5), g.mul(g.mul(scratch, steel), 0.5)), 0.5, 0.0001, nrm)
        nrm = g.bump(g.mul(craze, -1.0), 0.6, 0.00008, nrm)

    col, rough, _ = _grime_dust(g, col, rough, wpos, top_dust, floor_grime,
                                ao_amt=0.7 if hero else 0.0)
    bsdf = g.principled(Base_Color=col, Metallic=metal, Roughness=rough, Normal=nrm,
                        Specular_IOR_Level=0.5, Coat_Weight=0.08, Coat_Roughness=0.3)
    shader = bsdf.outputs[0]
    if holes:
        on = g.obj_normal()
        nx, ny, _ = g.sep(on)
        ox, oy, oz = g.sep(g.n("ShaderNodeTexCoord").outputs["Object"])
        # front face: u across the 90 mm face, v up in 50 mm tiles
        fu = g.mul(g.add(oy, 0.045), 1.0 / 0.090)
        fv = g.mul(oz, 1.0 / 0.050)
        fvec = g.n("ShaderNodeCombineXYZ", fu, fv, 0.0).outputs[0]
        fa = g.image("holes_front.png", fvec, "Cubic", "REPEAT", "Non-Color")
        su = g.mul(ox, 1.0 / 0.070)
        svec = g.n("ShaderNodeCombineXYZ", su, fv, 0.0).outputs[0]
        sa = g.image("holes_side.png", svec, "Cubic", "REPEAT", "Non-Color")
        front = g.mul(g.mr(g.math("ABSOLUTE", nx), 0.7, 0.8), g.mr(ox, 0.012, 0.004))
        side = g.mr(g.math("ABSOLUTE", ny), 0.7, 0.8)
        hole = g.add(g.mul(front, g.inv(g.mr(fa, 0.45, 0.55))), g.mul(side, g.inv(g.mr(sa, 0.45, 0.55))), True)
        shader = g.mixs(hole, shader, g.n("ShaderNodeBsdfTransparent").outputs[0])
    g.output(shader)
    return m


def galvanized(name="galvanized", tint="#a9adb0", rough=0.34, top_dust=0.5):
    """Hot-dip galvanised steel: spangle crystals, white-rust blooms, grime."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    vec = g.coords("Object")
    wpos = g.geo("Position")
    sp = g.voronoi(vec, 45.0, "F1", "Color")
    spv = g.n("ShaderNodeSeparateColor", sp).outputs[0]
    col = g.mixc(g.mr(spv, 0.0, 1.0, 0.0, 0.25), lin(tint), lin("#c9ccce"))
    blotch = g.mr(g.noise(vec, 8.0, 6, 0.6), 0.55, 0.75)
    col = g.mixc(g.mul(blotch, 0.5), col, lin("#c7c6bf"))
    r = g.add(rough, g.mul(g.sub(spv, 0.5), 0.16))
    r = g.mixf(blotch, r, 0.6)
    col, r, _ = _grime_dust(g, col, r, wpos, top_dust, 0.8, 0.03, 0.6)
    bsdf = g.principled(Base_Color=col, Metallic=0.95, Roughness=r,
                        Normal=g.bump(g.noise(vec, 400.0, 3), 0.1, 0.0002))
    g.output(bsdf)
    return m


def fork_steel(name="fork_steel"):
    """Forged fork blades: black paint worn to bright steel on the tips, heels and edges."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    vec = g.coords("Object")
    wpos = g.geo("Position")
    em = g.edge_mask(0.006, 0.02, 0.2)
    ox, _, oz = g.sep(g.n("ShaderNodeTexCoord").outputs["Object"])
    _, _, nz = g.sep(g.geo("Normal"))
    # tips and undersides are polished bright by pallets and floors
    tip = g.mr(ox, 0.80, 1.10)
    under = g.mr(nz, -0.5, -0.9)
    wear_in = g.add(g.add(g.mul(em, 0.8), g.mul(tip, 0.7)), g.mul(under, 0.6))
    wear = g.mr(g.add(wear_in, g.mul(g.noise(vec, 24.0, 8, 0.7), 0.5)), 0.55, 0.7)
    lines = g.wave(g.coords("Object", False, (1.0, 1.0, 1.0)), 600.0, 3.0, 2.0, "BANDS", "Y")
    col = g.mixc(wear, lin("#1d1d1e"), lin("#8d8f91"))
    rough = g.mixf(wear, 0.55, 0.22)
    rust = g.mr(g.noise(vec, 18.0, 8, 0.7), 0.68, 0.8)
    col = g.mixc(g.mul(rust, 0.6), col, lin("#5a3a22"))
    rough = g.mixf(rust, rough, 0.8)
    col, rough, _ = _grime_dust(g, col, rough, wpos, 0.3, 0.0, 0.03, 0.5)
    bsdf = g.principled(Base_Color=col, Metallic=g.mixf(wear, 0.4, 1.0), Roughness=rough,
                        Normal=g.bump(g.mul(lines, wear), 0.3, 0.0001))
    g.output(bsdf)
    return m


def painted_metal(name, color, rough=0.32, wear=0.5, coat=0.4):
    """Vehicle paint (reach truck body/mast)."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    vec = g.coords("Object")
    wpos = g.geo("Position")
    em = g.edge_mask(0.005, 0.03, 0.25)
    chip = g.mr(g.add(g.mul(em, 0.7), g.mul(g.noise(vec, 40.0, 8, 0.7), 0.6)), 1.0 - wear * 0.4, 1.06 - wear * 0.4)
    col = g.mixc(chip, lin(color), lin("#3c3d3e"))
    r = g.mixf(chip, rough, 0.5)
    col, r, _ = _grime_dust(g, col, r, wpos, 0.4, 0.8, 0.05, 0.6)
    bsdf = g.principled(Base_Color=col, Roughness=r, Metallic=g.mul(chip, 0.8), Coat_Weight=coat,
                        Coat_Roughness=0.12, Normal=g.bump(g.noise(vec, 900.0, 2), 0.06, 0.0001))
    g.output(bsdf)
    return m


# ------------------------------------------------------------------ floor

def concrete_floor(name="floor_concrete", maps="floor_maps.png", region=(-7.0, 7.0, -14.0, 40.0),
                   joint_pitch=6.0):
    """Power-trowelled, sealed warehouse slab: mottle, aggregate, saw joints, tyre rubber,
    oil drips, dust against the racks and worn yellow aisle lines (from floor_maps.png)."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    tc = g.n("ShaderNodeTexCoord")
    obj = tc.outputs["Object"]
    ox, oy, _ = g.sep(obj)
    x0, x1, y0, y1 = region
    u = g.mul(g.sub(ox, x0), 1.0 / (x1 - x0))
    v = g.mul(g.sub(oy, y0), 1.0 / (y1 - y0))
    uv = g.n("ShaderNodeCombineXYZ", u, v, 0.0).outputs[0]
    mp = g.n("ShaderNodeTexImage", uv, props={"image": bpy.data.images.load(os.path.join(TEX, maps), check_existing=True),
                                              "interpolation": "Cubic", "extension": "EXTEND"})
    mp.image.colorspace_settings.name = "Non-Color"
    sepc = g.n("ShaderNodeSeparateColor", mp.outputs["Color"])
    rubber, stain, dust = sepc.outputs[0], sepc.outputs[1], sepc.outputs[2]
    line = mp.outputs["Alpha"]

    # base slab colour: large trowel mottle + mid blotches + fine aggregate speckle
    m1 = g.noise(obj, 0.35, 6, 0.6, 0.3)
    m2 = g.noise(obj, 2.2, 8, 0.65)
    col = g.mixc(g.mr(m1, 0.35, 0.65), lin("#77746e"), lin("#9a968e"))
    col = g.mixc(g.mul(g.mr(m2, 0.4, 0.75), 0.6), col, lin("#6a675f"))
    agg = g.voronoi(obj, 520.0, "F1", "Distance")
    speck = g.mr(agg, 0.12, 0.0)
    col = g.mixc(g.mul(speck, 0.35), col, lin("#3f3d39"))
    swirl = g.noise(g.coords("Object", False, (1.0, 1.0, 1.0)), 1.4, 4, 0.5, 6.0)
    rough = g.add(0.16, g.mul(g.mr(swirl, 0.3, 0.7), 0.26))

    # saw-cut joints every joint_pitch metres in both directions (6 mm wide, dark, recessed)
    def joint(coord):
        f = g.math("FRACT", g.add(g.mul(coord, 1.0 / joint_pitch), 0.5))
        dist = g.mul(g.math("ABSOLUTE", g.sub(f, 0.5)), joint_pitch)
        return g.mr(dist, 0.004, 0.0025)
    jt = g.add(joint(ox), joint(oy), True)

    # tyre rubber
    col = g.mixc(g.mul(rubber, 0.75), col, lin("#2a2826"))
    rough = g.mixf(rubber, rough, 0.5)
    # oil / water stains: darker and glossier
    col = g.mixc(g.mul(stain, 0.55), col, lin("#3b3934"))
    rough = g.mixf(stain, rough, 0.12)
    # dust: lighter and matte
    dfine = g.noise(obj, 40.0, 8, 0.7)
    dst = g.mul(dust, g.mr(dfine, 0.2, 0.8, 0.6, 1.0))
    col = g.mixc(g.mul(dst, 0.7), col, lin("#b3ada1"))
    rough = g.mixf(dst, rough, 0.9)
    # painted line
    lchip = g.mr(g.noise(obj, 90.0, 6, 0.7), 0.25, 0.4)
    lmask = g.mul(line, lchip)
    col = g.mixc(lmask, col, lin("#e2a90f"))
    rough = g.mixf(lmask, rough, 0.45)
    # joints last
    col = g.mixc(jt, col, lin("#2b2926"))
    rough = g.mixf(jt, rough, 0.9)

    height = g.add(g.mul(jt, -1.0), g.add(g.mul(lmask, 0.25), g.mul(g.noise(obj, 300.0, 4), 0.08)))
    nrm = g.bump(height, 0.35, 0.002)
    bsdf = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.55,
                        Coat_Weight=g.mixf(dst, 0.35, 0.0), Coat_Roughness=0.08)
    g.output(bsdf)
    return m


# ------------------------------------------------------------------ packaging

def cardboard(name, variant=0, n_variants=6, board=("#b0844f", "#c79a62")):
    """Single-wall kraft carton. UVs from loads.carton(): side faces map to one print
    variant (x in [variant/n, (variant+1)/n]), tops/bottoms to plain board (v < 0)."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    vec = g.coords("Object")
    wpos = g.geo("Position")
    uv = g.n("ShaderNodeUVMap").outputs[0]
    oi = g.n("ShaderNodeObjectInfo")
    base = g.mixc(g.mr(oi.outputs["Random"], 0.0, 1.0), lin(board[0]), lin(board[1]))
    blot = g.noise(vec, 8.0, 6, 0.6)
    col = g.mixc(g.mul(g.mr(blot, 0.3, 0.7), 0.5), base, lin("#9b7243"))
    fib = g.noise(vec, 700.0, 3, 0.6)
    col = g.mixc(g.mul(g.mr(fib, 0.4, 0.7), 0.25), col, lin("#d1a873"))
    # flexo print (ink mask: white = no ink)
    ink = g.image("carton_print.png", uv, "Linear", "CLIP")
    lum = g.n("ShaderNodeRGBToBW", ink).outputs[0]
    _, sv, _ = g.sep(uv)
    inkf = g.mul(g.mul(g.inv(lum), 0.92), g.mr(sv, -0.02, 0.0))
    col = g.mixc(inkf, col, g.mixc(1.0, ink, (0.75, 0.75, 0.75, 1), "MULTIPLY"))
    # flutes read only at grazing light
    flute = g.wave(g.coords("Object", False, (1.0, 1.0, 1.0)), 260.0, 0.0, 0.0, "BANDS", "Z")
    em = g.edge_mask(0.006, 0.02, 0.3)
    fuzz = g.mul(em, g.mr(g.noise(vec, 120.0, 8, 0.7), 0.4, 0.7))
    col = g.mixc(g.mul(fuzz, 0.6), col, lin("#d8b88e"))
    rough = g.add(0.78, g.mul(inkf, -0.18))
    col, rough, _ = _grime_dust(g, col, rough, wpos, 0.5, 0.6, 0.06, 0.5)
    nrm = g.bump(g.add(g.mul(flute, 0.15), g.mul(blot, 0.5)), 0.15, 0.0006)
    bsdf = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.3,
                        Sheen_Weight=0.25, Sheen_Roughness=0.5)
    g.output(bsdf)
    return m


def packing_tape(name="packing_tape"):
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    uv = g.n("ShaderNodeUVMap").outputs[0]
    t = g.image("tape.png", uv, "Linear", "REPEAT")
    wr = g.noise(g.coords("Object"), 160.0, 4, 0.6)
    bsdf = g.principled(Base_Color=t, Roughness=g.add(0.18, g.mul(wr, 0.12)), Coat_Weight=0.6,
                        Coat_Roughness=0.08, Normal=g.bump(wr, 0.25, 0.0004))
    g.output(bsdf)
    return m


def paper_label(name, image, rough=0.45, region=None):
    """Printed paper/thermal label. region = (u0, u1) selects a variant strip of the atlas."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    uv = g.n("ShaderNodeUVMap").outputs[0]
    if region:
        su, sv, _ = g.sep(uv)
        su = g.add(region[0], g.mul(su, region[1] - region[0]))
        uv = g.n("ShaderNodeCombineXYZ", su, sv, 0.0).outputs[0]
    t = g.image(image, uv, "Linear", "EXTEND")
    vec = g.coords("Object")
    dirt = g.mr(g.noise(vec, 30.0, 8, 0.7), 0.55, 0.8)
    col = g.mixc(g.mul(dirt, 0.25), t, lin("#8c826f"))
    bsdf = g.principled(Base_Color=col, Roughness=rough, Coat_Weight=0.15,
                        Normal=g.bump(g.noise(vec, 400.0, 3), 0.1, 0.0002))
    g.output(bsdf)
    return m


def stretch_wrap(name="stretch_wrap"):
    """LLDPE stretch film: clear with milky folds, sharp speculars, horizontal wrinkles."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    vec = g.coords("Object")
    wr = g.noise(g.coords("Object", True, (6.0, 6.0, 1.0)), 9.0, 6, 0.65, 0.4)
    wr2 = g.noise(g.coords("Object", True, (1.0, 1.0, 14.0)), 6.0, 4, 0.6)
    lw = g.n("ShaderNodeLayerWeight", 0.25, g.bump(g.add(wr, g.mul(wr2, 0.6)), 0.6, 0.004))
    milky = g.mr(g.add(lw.outputs["Facing"], g.mul(wr2, 0.4)), 0.55, 1.0, 0.05, 0.55)
    gloss = g.principled(Base_Color=(0.85, 0.87, 0.9, 1), Roughness=0.08, Specular_IOR_Level=0.7,
                         Normal=g.bump(g.add(wr, g.mul(wr2, 0.6)), 0.6, 0.004))
    sh = g.mixs(milky, g.n("ShaderNodeBsdfTransparent").outputs[0], gloss.outputs[0])
    g.output(sh)
    return m


def pallet_wood(name="pallet_wood"):
    """Rough-sawn pine pallet boards, weathered, forklift-scuffed."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    vec = g.coords("Object")
    wpos = g.geo("Position")
    oi = g.n("ShaderNodeObjectInfo")
    grain_vec = g.coords("Object", True, (1.0, 6.0, 6.0))   # boards run along local X
    rings = g.wave(grain_vec, 3.0, 9.0, 3.0, "BANDS", "X")
    fine = g.noise(g.coords("Object", True, (0.15, 1.0, 1.0)), 220.0, 6, 0.7)
    base = g.mixc(g.mr(oi.outputs["Random"], 0.0, 1.0), lin("#b3925f"), lin("#c9ab78"))
    col = g.mixc(g.mul(g.mr(rings, 0.3, 0.8), 0.45), base, lin("#8f6d42"))
    col = g.mixc(g.mul(g.mr(fine, 0.4, 0.7), 0.3), col, lin("#7a5a35"))
    age = g.mr(g.noise(vec, 3.0, 6, 0.6), 0.35, 0.75)
    col = g.mixc(g.mul(age, 0.55), col, lin("#7c7466"))
    knot = g.mr(g.voronoi(g.coords("Object", True, (0.4, 1.0, 1.0)), 6.0, "F1", "Distance"), 0.06, 0.02)
    col = g.mixc(g.mul(knot, 0.8), col, lin("#5b3f22"))
    col, rough, _ = _grime_dust(g, col, 0.82, wpos, 0.5, 0.9, 0.05, 0.75)
    nrm = g.bump(g.add(g.mul(fine, 0.7), g.mul(rings, 0.3)), 0.35, 0.0015)
    bsdf = g.principled(Base_Color=col, Roughness=rough, Normal=nrm, Specular_IOR_Level=0.3)
    g.output(bsdf)
    return m


def rubber(name="rubber", color="#141414"):
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    vec = g.coords("Object")
    col, r, _ = _grime_dust(g, lin(color), 0.75, g.geo("Position"), 0.6, 0.5, 0.03, 0.4,
                            dust_col="#7d776c")
    g.output(g.principled(Base_Color=col, Roughness=r, Normal=g.bump(g.noise(vec, 500.0, 3), 0.2, 0.0003)))
    return m


def plastic(name, color, rough=0.4):
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    vec = g.coords("Object")
    col, r, _ = _grime_dust(g, lin(color), rough, g.geo("Position"), 0.5, 0.6, 0.04, 0.5)
    g.output(g.principled(Base_Color=col, Roughness=r, Normal=g.bump(g.noise(vec, 300.0, 3), 0.08, 0.0002)))
    return m


def emission(name, color="#fff4e6", strength=20.0):
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    g.output(g.n("ShaderNodeEmission", lin(color), strength))
    return m


def decal_image(name, image, rough=0.4, metallic=0.0, coat=0.0, emit=0.0):
    """A flat printed item (signs, plates, tags) mapped by UV 0..1."""
    m, fresh = _mat(name)
    if not fresh:
        return m
    g = G(m)
    uv = g.n("ShaderNodeUVMap").outputs[0]
    t = g.image(image, uv, "Cubic", "EXTEND")
    vec = g.coords("Object")
    dirt = g.mr(g.noise(vec, 25.0, 8, 0.7), 0.6, 0.85)
    col = g.mixc(g.mul(dirt, 0.2), t, lin("#776f60"))
    bsdf = g.principled(Base_Color=col, Roughness=g.add(rough, g.mul(dirt, 0.2)), Metallic=metallic,
                        Coat_Weight=coat, Coat_Roughness=0.15, Emission_Color=t, Emission_Strength=emit,
                        Normal=g.bump(g.noise(vec, 350.0, 3), 0.06, 0.0002))
    g.output(bsdf)
    return m
