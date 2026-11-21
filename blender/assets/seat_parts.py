"""Shared mesh builder, materials, marquetry and preview rig for the seating /
furniture assets (pew, deacon_bench, lectern, rope_post). Not an asset itself.

Everything an asset needs goes into ONE bmesh (class B) so the result is a
single mesh object that can be instanced cheaply.

UV layers on every mesh:
  UVMap  smart-projected, for baking.
  aux    wood faces: a random (u, v) per board, read by the wood shader to
         give each board its own grain and tone;
         marquetry faces: real UVs into the generated inlay atlas.
"""
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402

INLAY_PNG = os.path.join(common.ASSETS, "seat_inlay.png")


# ---------------------------------------------------------------- materials
def _n(nt, kind, **props):
    n = nt.nodes.new(kind)
    for k, v in props.items():
        setattr(n, k, v)
    return n


def _math(nt, op, a, b=None):
    n = _n(nt, "ShaderNodeMath", operation=op)
    for i, v in enumerate((a, b)):
        if v is None:
            continue
        if isinstance(v, (int, float)):
            n.inputs[i].default_value = v
        else:
            nt.links.new(v, n.inputs[i])
    return n.outputs[0]


def _bevel(nt, radius=0.003):
    bv = _n(nt, "ShaderNodeBevel", samples=6)
    bv.inputs["Radius"].default_value = radius
    return bv.outputs[0]


def wood(name, dark, mid, light, axis="X", wear=0.3, coat_rough=(0.035, 0.12), ao_floor=0.30):
    """Stained hardwood under a hard gloss varnish.
    Straight ribbon grain along `axis` (object space), offset per board through
    the `aux` UV layer; darker in joints (AO), rubbed lighter on edges (bevel
    normal vs. face normal); rounded edges via the Bevel node; clearcoat with
    slightly varying roughness."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    L = nt.links.new
    b = common.bsdf(m)
    tc = _n(nt, "ShaderNodeTexCoord")
    uv = _n(nt, "ShaderNodeUVMap", uv_map="aux")
    sep = _n(nt, "ShaderNodeSeparateXYZ")
    L(uv.outputs[0], sep.inputs[0])
    r1, r2 = sep.outputs[0], sep.outputs[1]
    off = _n(nt, "ShaderNodeCombineXYZ")
    L(_math(nt, "MULTIPLY", r1, 9.0), off.inputs[0])
    L(_math(nt, "MULTIPLY", r2, 9.0), off.inputs[1])
    L(_math(nt, "MULTIPLY", r1, 5.0), off.inputs[2])
    add = _n(nt, "ShaderNodeVectorMath", operation="ADD")
    L(tc.outputs["Object"], add.inputs[0])
    L(off.outputs[0], add.inputs[1])

    def grain(long, cross, detail, distortion):
        mp = _n(nt, "ShaderNodeMapping")
        mp.inputs["Scale"].default_value = {"X": (long, cross, cross), "Y": (cross, long, cross),
                                            "Z": (cross, cross, long)}[axis]
        nz = _n(nt, "ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 1.0
        nz.inputs["Detail"].default_value = detail
        nz.inputs["Roughness"].default_value = 0.55
        nz.inputs["Distortion"].default_value = distortion
        L(add.outputs[0], mp.inputs["Vector"])
        L(mp.outputs[0], nz.inputs["Vector"])
        return nz.outputs[0]

    ribbon = grain(0.7, 15.0, 1.5, 0.05)        # broad ribbon stripe
    fine = grain(4.0, 230.0, 2.0, 0.0)          # fine pore lines
    low = grain(1.3, 2.2, 1.0, 0.0)             # slow tonal drift / gloss variation
    fac = _math(nt, "ADD", _math(nt, "MULTIPLY", ribbon, 0.60), _math(nt, "MULTIPLY", fine, 0.40))
    fac = _math(nt, "ADD", fac, _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", r2, 0.5), 0.20))
    ramp = _n(nt, "ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.30, (*dark, 1)
    e[1].position, e[1].color = 0.74, (*light, 1)
    mid_e = e.new(0.52)
    mid_e.color = (*mid, 1)
    L(fac, ramp.inputs[0])
    # joints: ambient occlusion over a couple of centimetres
    ao = _n(nt, "ShaderNodeAmbientOcclusion", samples=4)
    ao.inputs["Distance"].default_value = 0.03
    aof = _n(nt, "ShaderNodeMapRange")
    aof.inputs[1].default_value, aof.inputs[2].default_value = 0.25, 0.85
    aof.inputs[3].default_value, aof.inputs[4].default_value = ao_floor, 1.0
    L(ao.outputs["AO"], aof.inputs[0])
    dk = _n(nt, "ShaderNodeVectorMath", operation="SCALE")
    L(ramp.outputs[0], dk.inputs[0])
    L(aof.outputs[0], dk.inputs["Scale"])
    # edges: where the bevelled normal leaves the surface normal
    bev = _bevel(nt, 0.0032)
    geo = _n(nt, "ShaderNodeNewGeometry")
    dot = _n(nt, "ShaderNodeVectorMath", operation="DOT_PRODUCT")
    L(bev, dot.inputs[0])
    L(geo.outputs["Normal"], dot.inputs[1])
    edge = _math(nt, "MULTIPLY", _math(nt, "SUBTRACT", 1.0, dot.outputs["Value"]), 7.0)
    wn = _n(nt, "ShaderNodeTexNoise")
    wn.inputs["Scale"].default_value = 55.0
    wn.inputs["Detail"].default_value = 3.0
    L(add.outputs[0], wn.inputs["Vector"])
    wmask = _n(nt, "ShaderNodeMapRange")
    wmask.inputs[1].default_value, wmask.inputs[2].default_value = 0.42, 0.68
    L(wn.outputs[0], wmask.inputs[0])
    edge = _math(nt, "MULTIPLY", _math(nt, "MULTIPLY", edge, wmask.outputs[0]), wear)
    edge_c = _n(nt, "ShaderNodeClamp")
    L(edge, edge_c.inputs[0])
    mix = _n(nt, "ShaderNodeMix", data_type="RGBA")
    L(edge_c.outputs[0], mix.inputs[0])
    L(dk.outputs[0], mix.inputs[6])
    mix.inputs[7].default_value = (min(1, light[0] * 2.2), light[1] * 2.6, light[2] * 2.6, 1)
    L(mix.outputs[2], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.42
    L(bev, b.inputs["Normal"])
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat IOR"].default_value = 1.5
    cr = _n(nt, "ShaderNodeMapRange")
    cr.inputs[1].default_value, cr.inputs[2].default_value = 0.3, 0.7
    cr.inputs[3].default_value, cr.inputs[4].default_value = coat_rough
    L(low, cr.inputs[0])
    L(cr.outputs[0], b.inputs["Coat Roughness"])
    L(bev, b.inputs["Coat Normal"])
    return m


def fabric(name, rgb, weave=900.0, bump=0.25, sheen=0.6, mottle=0.12):
    """Cloth: sheen, fine weave bump, soft tonal unevenness."""
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    L = nt.links.new
    b = common.bsdf(m)
    tc = _n(nt, "ShaderNodeTexCoord")
    lo = _n(nt, "ShaderNodeTexNoise")
    lo.inputs["Scale"].default_value = 7.0
    lo.inputs["Detail"].default_value = 3.0
    L(tc.outputs["Object"], lo.inputs["Vector"])
    hi = _n(nt, "ShaderNodeTexNoise")
    hi.inputs["Scale"].default_value = weave
    hi.inputs["Detail"].default_value = 1.0
    L(tc.outputs["Object"], hi.inputs["Vector"])
    val = _n(nt, "ShaderNodeMapRange")
    val.inputs[1].default_value, val.inputs[2].default_value = 0.25, 0.75
    val.inputs[3].default_value, val.inputs[4].default_value = 1.0 - mottle, 1.0 + mottle
    L(lo.outputs[0], val.inputs[0])
    col = _n(nt, "ShaderNodeVectorMath", operation="SCALE")
    col.inputs[0].default_value = rgb
    L(val.outputs[0], col.inputs["Scale"])
    L(col.outputs[0], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.9
    b.inputs["Sheen Weight"].default_value = sheen
    b.inputs["Sheen Roughness"].default_value = 0.35
    b.inputs["Sheen Tint"].default_value = (min(1, rgb[0] * 3.5), min(1, rgb[1] * 6), min(1, rgb[2] * 5), 1)
    h = _math(nt, "ADD", _math(nt, "MULTIPLY", hi.outputs[0], 0.35), _math(nt, "MULTIPLY", lo.outputs[0], 0.65))
    bp = _n(nt, "ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.004
    L(h, bp.inputs["Height"])
    L(bp.outputs[0], b.inputs["Normal"])
    return m


def inlay_image():
    """Draw the marquetry atlas (bone / dark banding and the tiny mosaic
    centres) and save it next to the assets. Regions (u, v):
      lozenge  u 0..1,   v 0.70..1    long bar, bands follow its outline
      diamond  u 0..0.5, v 0..0.5     square set on its point
      star     u 0.5..1, v 0..0.5     eight-point star of the end posts
    Band order outside-in, read off IMG_7899 / IMG_7910: stained rim, bone
    line, dark line, bone line, then the mosaic of bone and grey-blue dots
    on near-black."""
    img = bpy.data.images.get("seat_inlay")
    if img:
        return img
    import numpy as np
    S = 1024
    v, u = np.mgrid[0:S, 0:S].astype(np.float32) / (S - 1)
    rgb = np.zeros((S, S, 3), np.float32)
    rgb[:] = (0.13, 0.045, 0.03)
    BONE, DARK, RIM = (0.88, 0.78, 0.58), (0.07, 0.035, 0.03), (0.16, 0.05, 0.03)
    BLUE, MOS = (0.50, 0.55, 0.62), (0.045, 0.035, 0.05)

    def paint(mask, c):
        rgb[mask] = c

    def bands(d, q1, q2, region):
        paint(region & (d >= 0.0), RIM)
        paint(region & (d >= 0.05), BONE)
        paint(region & (d >= 0.56), DARK)
        paint(region & (d >= 0.63), BONE)
        paint(region & (d >= 0.72), MOS)
        f1, f2 = q1 - np.floor(q1), q2 - np.floor(q2)
        dot = (np.abs(f1 - 0.5) + np.abs(f2 - 0.5)) < 0.30
        par = (np.floor(q1) + np.floor(q2)) % 2 == 0
        core = region & (d >= 0.74)
        paint(core & dot & par, BONE)
        paint(core & dot & ~par, BLUE)

    # lozenge
    reg = v >= 0.70
    A = (u * 2 - 1) * LOZ_ASPECT
    P = ((v - 0.70) / 0.30) * 2 - 1
    d = np.minimum(np.minimum(1 - np.abs(P), LOZ_ASPECT - np.abs(A)),
                   (LOZ_ASPECT + 1 - LOZ_CHAMFER - np.abs(A) - np.abs(P)) / 1.4142)
    bands(d, (A + P) / 0.26, (A - P) / 0.26, reg)
    # diamond
    reg = (v < 0.5) & (u < 0.5)
    a, p = u * 4 - 1, v * 4 - 1
    d = 1 - (np.abs(a) + np.abs(p))
    bands(d * 1.15, (a + p) / 0.21, (a - p) / 0.21, reg & (d >= 0))
    # eight-point star: bone, cut into wedges by dark lines, dark eye with a bone dot
    reg = (v < 0.5) & (u >= 0.5)
    a, p = (u - 0.5) * 4 - 1, v * 4 - 1
    sq, di = np.maximum(np.abs(a), np.abs(p)), np.abs(a) + np.abs(p)
    inside = reg & ((sq < 0.70) | (di < 0.99))
    edge = np.minimum(np.where(sq < 0.70, 0.70 - sq, 1), np.where(di < 0.99, (0.99 - di) / 1.414, 1))
    edge = np.maximum(np.where(sq < 0.70, 0.70 - sq, -1), np.where(di < 0.99, (0.99 - di) / 1.414, -1))
    paint(inside, BONE)
    paint(inside & (edge < 0.035), RIM)
    lines = (np.abs(a) < 0.035) | (np.abs(p) < 0.035) | (np.abs(np.abs(a) - np.abs(p)) < 0.05)
    paint(inside & lines & (edge >= 0.035), DARK)
    paint(inside & (di < 0.36), DARK)
    paint(inside & (di < 0.20), BONE)
    paint(inside & (np.abs(sq - 0.42) < 0.03) & (edge >= 0.035), DARK)

    px = np.concatenate([rgb, np.ones((S, S, 1), np.float32)], axis=2)
    img = bpy.data.images.new("seat_inlay", S, S, alpha=False)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = INLAY_PNG
    img.file_format = "PNG"
    img.save()
    img.pack()
    return img


def inlay_material():
    m = bpy.data.materials.get("SeatInlay")
    if m:
        return m
    m = bpy.data.materials.new("SeatInlay")
    m.use_nodes = True
    nt = m.node_tree
    b = common.bsdf(m)
    uv = _n(nt, "ShaderNodeUVMap", uv_map="aux")
    tex = _n(nt, "ShaderNodeTexImage")
    tex.image = inlay_image()
    nt.links.new(uv.outputs[0], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = 0.35
    b.inputs["Coat Weight"].default_value = 1.0
    b.inputs["Coat Roughness"].default_value = 0.07
    bev = _bevel(nt, 0.0015)
    nt.links.new(bev, b.inputs["Normal"])
    nt.links.new(bev, b.inputs["Coat Normal"])
    return m


PEW_TONES = ((0.016, 0.0035, 0.002), (0.055, 0.012, 0.005), (0.125, 0.030, 0.011))


def pew_materials():
    """Deep red-brown mahogany, gloss varnish (nave pews and deacon benches)."""
    d, mi, li = PEW_TONES
    return dict(
        wx=wood("PewWood_X", d, mi, li, "X"),
        wy=wood("PewWood_Y", d, mi, li, "Y"),
        wz=wood("PewWood_Z", d, mi, li, "Z"),
        rail=wood("PewWood_Rail", d, mi, li, "X", wear=1.0),      # cap rail: handled, rubbed
        arm=wood("PewWood_Arm", d, mi, li, "Y", wear=1.0),
        field=wood("PewWood_Field", (0.012, 0.003, 0.002), (0.040, 0.009, 0.004), (0.085, 0.021, 0.008), "Z",
                   wear=0.0, ao_floor=0.85),
        inlay=inlay_material(),
        cushion=fabric("PewCushion", (0.150, 0.006, 0.020)),
    )


# ------------------------------------------------------------------ builder
def rrect(w, h, rt, rb, seg_t=3, seg_b=1):
    """Rounded-rectangle section: u in [-w/2, w/2], v in [0, h]."""
    pts = []

    def arc(cx, cy, r, a0, seg):
        for i in range(seg + 1):
            a = math.radians(a0 + 90.0 * i / seg)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    arc(-w / 2 + rb, rb, rb, 180, seg_b)
    arc(w / 2 - rb, rb, rb, 270, seg_b)
    arc(w / 2 - rt, h - rt, rt, 0, seg_t)
    arc(-w / 2 + rt, h - rt, rt, 90, seg_t)
    return pts


class B:
    def __init__(self, seed=1):
        self.bm = bmesh.new()
        self.uv_main = self.bm.loops.layers.uv.new("UVMap")
        self.uv_aux = self.bm.loops.layers.uv.new("aux")
        self.mats = []
        self.solid = []      # faces whose normals are fixed by recalc
        self.lathe_verts = []
        self.rng = random.Random(seed)
        self.board = (0.5, 0.5)
        self.hold = False

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def new_board(self):
        if not self.hold:
            self.board = (self.rng.random(), self.rng.random())

    # -- primitives ------------------------------------------------------
    def _face(self, verts, mat, hint=None, uvs=None):
        f = self.bm.faces.new(verts)
        f.material_index = self.mi(mat)
        for i, lp in enumerate(f.loops):
            lp[self.uv_aux].uv = uvs[i] if uvs else self.board
        if hint is None:
            self.solid.append(f)
        else:
            f.normal_update()
            if f.normal.dot(hint) < 0:
                f.normal_flip()
        return f

    def poly(self, pts, mat, hint, uvs=None):
        """Single flat face. hint = wanted normal direction."""
        return self._face([self.bm.verts.new(p) for p in pts], mat, Vector(hint), uvs)

    def loft(self, ring_a, ring_b, mat, cap_a=False, cap_b=False, outward=False, cap_mat=None, cap_uvs=None):
        """Side faces between two equal-length point rings (+ optional caps).
        outward=True: orient away from the ring axis (for open shells)."""
        self.new_board()
        self._loft(ring_a, ring_b, mat, cap_a, cap_b, outward, cap_mat, cap_uvs)

    def _loft(self, ring_a, ring_b, mat, cap_a, cap_b, outward, cap_mat=None, cap_uvs=None, va=None):
        va = va or [self.bm.verts.new(p) for p in ring_a]
        vb = [self.bm.verts.new(p) for p in ring_b]
        n = len(va)
        ctr = sum((Vector(p) for p in list(ring_a) + list(ring_b)), Vector()) / (2 * n)
        for i in range(n):
            j = (i + 1) % n
            quad = [va[i], va[j], vb[j], vb[i]]
            if outward:
                mid = sum((v.co for v in quad), Vector()) / 4
                self._face(quad, mat, mid - ctr)
            else:
                self._face(quad, mat)
        axis = (sum((Vector(p) for p in ring_b), Vector()) - sum((Vector(p) for p in ring_a), Vector()))
        if cap_a:
            self._face(va, cap_mat or mat, -axis if outward else None)
        if cap_b:
            self._face(vb, cap_mat or mat, axis if outward else None, cap_uvs)
        return vb

    def sweep(self, rings, mat, cap_a=True, cap_b=True):
        """Closed skin through a list of equal-length rings (shared verts)."""
        self.new_board()
        va = None
        for k in range(len(rings) - 1):
            va = self._loft(rings[k], rings[k + 1], mat, cap_a and k == 0, cap_b and k == len(rings) - 2,
                            False, va=va)

    def stack(self, profile, cx, cy, mat):
        """Rectangular rings [(half_x, half_y, z), ...] lofted bottom to top."""
        self.sweep([[(cx - ex, cy - ey, z), (cx + ex, cy - ey, z), (cx + ex, cy + ey, z), (cx - ex, cy + ey, z)]
                    for ex, ey, z in profile], mat)

    @staticmethod
    def _map(axis, u, v, w):
        return {"x": (w, u, v), "y": (u, w, v), "z": (u, v, w)}[axis]

    def prism(self, pts2d, w0, w1, axis, mat):
        """Closed extrusion of a 2D outline along an axis.
        axis 'x': outline is (y, z); 'y': (x, z); 'z': (x, y)."""
        a = [self._map(axis, u, v, w0) for u, v in pts2d]
        b = [self._map(axis, u, v, w1) for u, v in pts2d]
        self.loft(a, b, mat, cap_a=True, cap_b=True)

    def box(self, x0, x1, y0, y1, z0, z1, mat):
        self.prism([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1, "z", mat)

    def lathe(self, profile, segs, cx, cy, mat):
        """Revolve [(r, z), ...] round the vertical axis at (cx, cy)."""
        self.new_board()
        rings = []
        for r, z in profile:
            ring = [self.bm.verts.new((cx + r * math.cos(2 * math.pi * i / segs),
                                       cy + r * math.sin(2 * math.pi * i / segs), z))
                    for i in range(segs)]
            rings.append(ring)
            self.lathe_verts += ring
        for a, b in zip(rings, rings[1:]):
            for i in range(segs):
                j = (i + 1) % segs
                self._face([a[i], a[j], b[j], b[i]], mat)

    def tube(self, path, radius, sides, mat):
        rings = []
        for k, p in enumerate(path):
            p = Vector(p)
            t = (Vector(path[min(k + 1, len(path) - 1)]) - Vector(path[max(k - 1, 0)])).normalized()
            side = t.cross(Vector((0, 1, 0)))
            side = side.normalized() if side.length > 1e-6 else Vector((1, 0, 0))
            up = side.cross(t)
            rings.append([p + radius * (math.cos(2 * math.pi * i / sides) * side +
                                        math.sin(2 * math.pi * i / sides) * up)
                          for i in range(sides)])
        self.sweep(rings, mat)

    # -- finish ----------------------------------------------------------
    def finish(self, name, coll):
        bm = self.bm
        if self.lathe_verts:
            bmesh.ops.remove_doubles(bm, verts=[v for v in self.lathe_verts if v.is_valid], dist=1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=[f for f in self.solid if f.is_valid])
        for f in bm.faces:
            f.smooth = True
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        me.set_sharp_from_angle(angle=math.radians(40))
        me.uv_layers.active = me.uv_layers["UVMap"]
        me.uv_layers["UVMap"].active_render = True
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.003)
        bpy.ops.object.mode_set(mode="OBJECT")
        ob.select_set(False)
        return ob


# ------------------------------------------------------------- marquetry
class Plane:
    """2D drawing frame on a surface: origin O, in-plane axes U, V, normal N."""

    def __init__(self, O, U, V):
        self.O, self.U, self.V = Vector(O), Vector(U).normalized(), Vector(V).normalized()
        self.N = self.U.cross(self.V)

    def p(self, u, v, h=0.0):
        return self.O + self.U * u + self.V * v + self.N * h

    def rot(self, deg, du=0.0, dv=0.0):
        a = math.radians(deg)
        U = self.U * math.cos(a) + self.V * math.sin(a)
        V = self.V * math.cos(a) - self.U * math.sin(a)
        return Plane(self.O + self.U * du + self.V * dv, U, V)


# proportions of the motif, in units of half the square's side (from IMG_7899)
LOZ_R, LOZ_HL, LOZ_HW = 0.70, 0.52, 0.185      # lozenge centre radius, half length, half width (top face)
LOZ_ASPECT = LOZ_HL / LOZ_HW
LOZ_CHAMFER = 0.62                            # corner cut, in half-widths
DIA_R, DIA_D = 0.70, 0.30                    # diamond centre radius, half diagonal (top face)
BLOCK_BEVEL = 0.052                           # how far each block's foot spreads past its top


def _block(b, pl, top, uvs, relief, M, wood_mat):
    """One raised marquetry block: bevelled wooden sides, inlaid top."""
    n = len(top)
    cu = sum(p[0] for p in top) / n
    cv = sum(p[1] for p in top) / n
    base = []
    for u, v in top:
        du, dv = u - cu, v - cv
        ln = math.hypot(du, dv)
        base.append(pl.p(u + du / ln * pl._spread, v + dv / ln * pl._spread, 0.0))
    b.loft(base, [pl.p(u, v, relief) for u, v in top], wood_mat, cap_b=True, outward=True,
           cap_mat=M["inlay"], cap_uvs=uvs)


def inlay_unit(b, pl, size, M, wood_mat, relief=0.009, lozenges=True, diamonds=True, field=True):
    """The square marquetry motif of the pew ends, bench ends and lectern:
    four long lozenges set in an X and four diamonds on the axes between
    them, each a raised bevelled block with an inlaid top, standing on a
    dark recessed field."""
    s = size / 2
    pl._spread = BLOCK_BEVEL * s
    if field:
        b.new_board()
        b.poly([pl.p(-s, -s, 0.0006), pl.p(s, -s, 0.0006), pl.p(s, s, 0.0006), pl.p(-s, s, 0.0006)], M["field"], pl.N)
    hl, hw, c = LOZ_HL * s, LOZ_HW * s, LOZ_CHAMFER * LOZ_HW * s
    if lozenges:
        for q in range(4):
            ang = math.radians(45 + 90 * q)
            ca, sa = math.cos(ang), math.sin(ang)
            cx, cy = LOZ_R * s * ca, LOZ_R * s * sa
            loc = [(-hl, -hw + c), (-hl + c, -hw), (hl - c, -hw), (hl, -hw + c),
                   (hl, hw - c), (hl - c, hw), (-hl + c, hw), (-hl, hw - c)]
            top = [(cx + a * ca - p_ * sa, cy + a * sa + p_ * ca) for a, p_ in loc]
            uvs = [((a / hl + 1) / 2, 0.70 + 0.30 * (p_ / hw + 1) / 2) for a, p_ in loc]
            _block(b, pl, top, uvs, relief, M, wood_mat)
    if diamonds:
        d = DIA_D * s
        for q in range(4):
            ca, sa = math.cos(math.radians(90 * q)), math.sin(math.radians(90 * q))
            cx, cy = DIA_R * s * ca, DIA_R * s * sa
            top = [(cx - d, cy), (cx, cy - d), (cx + d, cy), (cx, cy + d)]
            uvs = [(0.0, 0.25), (0.25, 0.0), (0.5, 0.25), (0.25, 0.5)]
            _block(b, pl, top, uvs, relief, M, wood_mat)


def photo_material():
    """textures/patterns/pew_inlay.jpg (a rectified photo of one lectern
    marquetry square) on the `aux` UVs. None when the file is missing."""
    path = os.path.join(common.TEX, "patterns", "pew_inlay.jpg")
    if not os.path.exists(path):
        return None
    m = bpy.data.materials.get("LecternInlayPhoto")
    if m:
        return m
    m = bpy.data.materials.new("LecternInlayPhoto")
    m.use_nodes = True
    nt = m.node_tree
    bs = common.bsdf(m)
    uv = _n(nt, "ShaderNodeUVMap", uv_map="aux")
    tex = _n(nt, "ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    nt.links.new(uv.outputs[0], tex.inputs["Vector"])
    dim = _n(nt, "ShaderNodeVectorMath", operation="SCALE")       # photo is flash-lit: bring it down to the body
    dim.inputs["Scale"].default_value = 0.42
    nt.links.new(tex.outputs["Color"], dim.inputs[0])
    nt.links.new(dim.outputs[0], bs.inputs["Base Color"])
    bs.inputs["Roughness"].default_value = 0.4
    bs.inputs["Coat Weight"].default_value = 1.0
    bs.inputs["Coat Roughness"].default_value = 0.10
    return m


def photo_panel(b, pl, size, mat, depth=0.006):
    """One marquetry square as the photo, set `depth` into the surface."""
    s = size / 2
    b.poly([pl.p(-s, -s, -depth), pl.p(s, -s, -depth), pl.p(s, s, -depth), pl.p(-s, s, -depth)], mat, pl.N,
           [(0, 0), (1, 0), (1, 1), (0, 1)])


def inlay_cluster(b, pl, size, M, wood_mat, relief=0.007):
    """Four diamonds set point to point (narrow faces of the lectern)."""
    s = size / 2
    pl._spread = 0.07 * s
    d = 0.40 * s
    for q in range(4):
        ca, sa = math.cos(math.radians(90 * q)), math.sin(math.radians(90 * q))
        cx, cy = 0.52 * s * ca, 0.52 * s * sa
        top = [(cx - d, cy), (cx, cy - d), (cx + d, cy), (cx, cy + d)]
        _block(b, pl, top, [(0.0, 0.25), (0.25, 0.0), (0.5, 0.25), (0.25, 0.5)], relief, M, wood_mat)


def star_medallion(b, pl, r, M):
    """Eight-point inlaid star flush in the end post: a square and the same
    square set on its point, both showing the star region of the atlas."""
    k = 0.70 * r
    b.poly([pl.p(-k, -k, 0.0005), pl.p(k, -k, 0.0005), pl.p(k, k, 0.0005), pl.p(-k, k, 0.0005)], M["inlay"], pl.N,
           [(0.5 + 0.25 * (1 + u * 0.70), 0.25 * (1 + v * 0.70)) for u, v in ((-1, -1), (1, -1), (1, 1), (-1, 1))])
    k = 0.99 * r
    b.poly([pl.p(-k, 0, 0.0008), pl.p(0, -k, 0.0008), pl.p(k, 0, 0.0008), pl.p(0, k, 0.0008)], M["inlay"], pl.N,
           [(0.5 + 0.25 * (1 + u * 0.99), 0.25 * (1 + v * 0.99)) for u, v in ((-1, 0), (0, -1), (1, 0), (0, 1))])


# ----------------------------------------------------------- floor plan
# The photos (PANO_20190107, MVIMG_20190817_111953, IMG_7888, IMG_7905) show
# FOUR pew blocks across the nave: a main block each side of the centre aisle,
# a narrow side aisle, then a short pew that runs up to the heater on the wall.
# common.PEW_LEN describes one block per side, so the split is derived here
# from the room numbers instead.
WALL_GAP = 0.15                       # heater cover depth between side pew and wall
SIDE_AISLE_W = 0.65
_SPAN = common.NAVE_W / 2 - WALL_GAP - common.AISLE_W / 2
MAIN_PEW_LEN = round((_SPAN - SIDE_AISLE_W) * 0.685, 2)
SIDE_PEW_LEN = round(_SPAN - SIDE_AISLE_W - MAIN_PEW_LEN, 2)
MAIN_PEW_X = common.AISLE_W / 2 + MAIN_PEW_LEN / 2                 # |x| of block centre
SIDE_PEW_X = common.NAVE_W / 2 - WALL_GAP - SIDE_PEW_LEN / 2


# ------------------------------------------------------------------ bench
BACK_Y0 = 0.150        # back panel centre line at seat level (local +Y = behind the sitter)
BACK_RAKE = 0.115      # y gained per metre of height
HALF_D = 0.28          # half depth of the end panels


def cushion(b, M, x0, x1, y0, y1, z0, h, piping=True):
    """Upholstered seat pad: bulged sides, crowned top that wanders a little
    along its length, pinched rounded ends, piping along the top edges."""
    rng = b.rng
    n = max(3, round((x1 - x0) / 0.23))
    xs = [x0, x0 + 0.007, x0 + 0.022] + [x0 + (x1 - x0) * i / n for i in range(1, n)] + [x1 - 0.022, x1 - 0.007, x1]
    rings, front, back = [], [], []
    for i, x in enumerate(xs):
        end = min(i, len(xs) - 1 - i)
        k = (0.55, 0.86, 1.0)[end] if end < 3 else 1.0
        ins = (0.012, 0.004, 0.0)[end] if end < 3 else 0.0
        hh = h * k * (1 + (0.07 * (rng.random() - 0.5) if end >= 3 else 0))
        crown = 0.006 * k + (0.004 * (rng.random() - 0.5) if end >= 3 else 0)
        a, c = y0 + ins, y1 - ins
        sec = [(a + 0.010, 0.0), (c - 0.010, 0.0), (c - 0.001, 0.008), (c + 0.004, hh * 0.42), (c - 0.001, hh * 0.80),
               (c - 0.018, hh), ((a + c) / 2 + 0.03, hh + crown), ((a + c) / 2 - 0.05, hh + crown * 0.8),
               (a + 0.018, hh), (a + 0.001, hh * 0.80), (a - 0.004, hh * 0.42), (a + 0.001, 0.008)]
        rings.append([(x, y, z0 + z) for y, z in sec])
        if 1 <= i <= len(xs) - 2:
            front.append((x, a + 0.004, z0 + hh * 0.90))
            back.append((x, c - 0.004, z0 + hh * 0.90))
    b.sweep(rings, M["cushion"])
    if piping:
        b.hold = True
        b.tube(front, 0.0042, 4, M["cushion"])
        b.tube(back, 0.0042, 4, M["cushion"])
        b.hold = False


def build_bench(b, M, length, back_h, seat_h, n_panels, n_supports, book_rail, inlay=0.33, pads=1):
    """Pew-type bench. Sitter faces -Y, origin floor centre. Used for the nave
    pews (book_rail=True) and the chorus deacon bench (open underside)."""
    wx, wy, wz = M["wx"], M["wy"], M["wz"]
    SL, PO, REC = 0.050, 0.085, 0.010          # end slab / post thickness, depth of the inlay recess
    cx = length / 2 - PO / 2                   # slab centre plane
    seat_top = seat_h - 0.048                  # wood seat; the pad brings it to about seat_h
    zb1 = back_h - 0.038                       # top of the back frame (cap rail sits on it)
    zb0 = seat_top - 0.07

    def yb(z):
        return BACK_Y0 + (z - zb0) * BACK_RAKE

    # armrest: underside heights at the post and at the front edge (IMG_7910, IMG_7988)
    arm_post, arm_front = back_h - 0.290, back_h - 0.385
    run = 0.17 + HALF_D
    post_y0, post_y1 = 0.17, HALF_D - 0.005
    zp = back_h + 0.045                        # top of the post shaft

    for sgn in (-1, 1):
        x = sgn * cx
        xin, xcore, xout = x - sgn * SL / 2, x + sgn * (SL / 2 - REC), x + sgn * SL / 2
        py = (-HALF_D + post_y0) / 2
        pz = 0.072 + (arm_front - 0.072) / 2
        h = inlay / 2
        # end slab: core + a face skin that leaves the square recess open
        b.prism([(-HALF_D, 0.05), (HALF_D - 0.01, 0.05), (HALF_D - 0.01, arm_post), (post_y0, arm_post),
                 (-HALF_D, arm_front)], *sorted((xin, xcore)), "x", wz)
        b.hold = True
        xs = sorted((xcore, xout))
        b.prism([(-HALF_D, 0.05), (post_y0, 0.05), (post_y0, pz - h), (-HALF_D, pz - h)], *xs, "x", wz)
        b.prism([(-HALF_D, pz + h), (post_y0, pz + h), (post_y0, arm_post), (-HALF_D, arm_front)], *xs, "x", wz)
        b.prism([(-HALF_D, pz - h), (py - h, pz - h), (py - h, pz + h), (-HALF_D, pz + h)], *xs, "x", wz)
        b.prism([(py + h, pz - h), (post_y0, pz - h), (post_y0, pz + h), (py + h, pz + h)], *xs, "x", wz)
        b.hold = False
        # moulded plinth
        prof = [(0.041, 0.0), (0.041, 0.044), (0.037, 0.052), (0.034, 0.063), (0.027, 0.076)]
        b.prism([(x + u, z) for u, z in prof] + [(x - u, z) for u, z in reversed(prof)],
                -HALF_D - 0.014, HALF_D + 0.004, "y", wy)
        # post with its stepped cap
        ex, ey, yc = PO / 2, (post_y1 - post_y0) / 2, (post_y0 + post_y1) / 2
        b.stack([(ex, ey, 0.06), (ex, ey, zp), (ex - 0.005, ey - 0.005, zp + 0.010),
                 (ex + 0.008, ey + 0.008, zp + 0.020), (ex + 0.020, ey + 0.020, zp + 0.030),
                 (ex + 0.020, ey + 0.020, zp + 0.058), (ex + 0.010, ey + 0.010, zp + 0.070)], x, yc, wz)
        # armrest: rounded board sloping down to a bullnose, bed mould under it
        dy, dz = -run, -(arm_post - arm_front)
        ln = math.hypot(dy, dz)
        dy, dz = dy / ln, dz / ln
        ny, nz = dz, -dy                                    # up, square to the slope
        sec = rrect(0.108, 0.046, 0.014, 0.004)
        rings = []
        for t, ks, kw in ((-0.004, 1, 1), (ln + 0.006, 1, 1), (ln + 0.017, 0.90, 0.99), (ln + 0.026, 0.68, 0.97),
                          (ln + 0.031, 0.40, 0.95)):
            rings.append([(x + u * kw, post_y0 + dy * t + ny * (0.023 + (v - 0.023) * ks),
                           arm_post + dz * t + nz * (0.023 + (v - 0.023) * ks)) for u, v in sec])
        b.sweep(rings, M["arm"])
        b.prism([(post_y0, arm_post - 0.016), (post_y0, arm_post + 0.002), (-HALF_D + 0.004, arm_front + 0.002),
                 (-HALF_D + 0.004, arm_front - 0.016)], x - 0.036, x + 0.036, "x", wy)
        # marquetry
        inlay_unit(b, Plane((xcore, py, pz), (0, sgn, 0), (0, 0, 1)), inlay, M, wz, relief=REC)
        star_medallion(b, Plane((x + sgn * PO / 2, yc, back_h - 0.045), (0, sgn, 0), (0, 0, 1)), 0.036, M)

    xi = cx - SL / 2                              # inner face of the slabs
    # seat board with a rounded nose, apron under it
    zt, yf = seat_top, -0.225
    b.prism([(0.165, zt - 0.04), (0.165, zt), (yf + 0.014, zt), (yf + 0.004, zt - 0.006), (yf, zt - 0.02),
             (yf + 0.004, zt - 0.034), (yf + 0.014, zt - 0.04)], -xi, xi, "x", wx)
    b.box(-xi, xi, yf + 0.012, yf + 0.034, zt - 0.115, zt - 0.04, wx)
    gap = 0.012
    for i in range(pads):
        x0 = -xi + 0.006 + i * (2 * xi - 0.012) / pads
        x1 = x0 + (2 * xi - 0.012) / pads
        cushion(b, M, x0 + (gap / 2 if i else 0), x1 - (gap / 2 if i < pads - 1 else 0), yf + 0.012, 0.142,
                zt, 0.050)

    # raked back: thin panels in a thicker frame, chamfered moulding round each panel
    def slab(z0, z1, t, x0, x1, mat):
        b.prism([(yb(z0) - t / 2, z0), (yb(z0) + t / 2, z0), (yb(z1) + t / 2, z1), (yb(z1) - t / 2, z1)],
                x0, x1, "x", mat)
    FT, PT = 0.036, 0.014
    zr0, zr1 = zb0 + 0.085, zb1 - 0.075
    slab(zb0, zb1, PT, -xi, xi, wx)
    slab(zb0, zr0, FT, -xi, xi, wx)
    slab(zr1, zb1, FT, -xi, xi, wx)
    sw = 0.062
    pitch = (2 * xi - sw) / n_panels
    for i in range(n_panels + 1):
        x0 = -xi + i * pitch
        slab(zr0, zr1, FT, x0, x0 + sw, wz)
    for i in range(n_panels):
        x0, x1 = -xi + i * pitch + sw, -xi + (i + 1) * pitch
        for side in (-1, 1):                       # front and back faces
            def pt(xx, z, depth):
                return (xx, yb(z) + side * (FT / 2 - depth), z)
            m = 0.013
            b.hold = True
            b.loft([pt(x0, zr0, 0), pt(x1, zr0, 0), pt(x1, zr1, 0), pt(x0, zr1, 0)],
                   [pt(x0 + m, zr0 + m, (FT - PT) / 2), pt(x1 - m, zr0 + m, (FT - PT) / 2),
                    pt(x1 - m, zr1 - m, (FT - PT) / 2), pt(x0 + m, zr1 - m, (FT - PT) / 2)], wx, outward=True)
            b.hold = False
    # moulded cap rail
    yc = yb(zb1)
    cap = [(-0.027, -0.004), (0.027, -0.004), (0.031, 0.005), (0.037, 0.010), (0.039, 0.021), (0.034, 0.031),
           (0.020, 0.038), (-0.014, 0.038), (-0.029, 0.032), (-0.035, 0.021), (-0.033, 0.010), (-0.027, 0.005)]
    b.prism([(yc + u, zb1 + v) for u, v in cap], -xi, xi, "x", M["rail"])

    # under-seat supports and rails
    for i in range(n_supports):
        x = -xi + (i + 1) * 2 * xi / (n_supports + 1)
        if book_rail:
            b.box(x - 0.022, x + 0.022, -0.200, 0.262, 0.0, zt - 0.04, wz)
            b.stack([(0.022, 0.050, zt - 0.04), (0.022, 0.050, zt + 0.15), (0.016, 0.044, zt + 0.165)], x, 0.214, wz)
        else:
            b.box(x - 0.024, x + 0.024, -0.200, 0.185, 0.0, zt - 0.04, wz)
    if book_rail:
        zr = zt + 0.07
        b.box(-xi, xi, 0.165, 0.250, zr, zr + 0.014, wx)              # shelf
        b.prism([(0.246, zr - 0.012), (0.268, zr - 0.012), (0.268, zr + 0.056), (0.262, zr + 0.064),
                 (0.252, zr + 0.064), (0.246, zr + 0.056)], -xi, xi, "x", M["rail"])     # lip rail
        b.box(-xi, xi, 0.236, 0.262, 0.215, 0.275, wx)                # lower rail
        b.box(-xi, xi, 0.205, 0.245, 0.060, 0.110, wx)                # foot stretcher
    else:
        b.box(-xi, xi, -0.030, 0.030, 0.105, 0.155, wx)               # centre stretcher
        b.box(-xi, xi, 0.150, 0.180, zt - 0.13, zt - 0.04, wx)


# ---------------------------------------------------------------- preview
def tri_count(coll):
    n = 0
    for ob in coll.all_objects:
        if ob.type == "MESH":
            ob.data.calc_loop_triangles()
            n += len(ob.data.loop_triangles)
    return n


def carpet_material():
    m = fabric("PreviewCarpet", (0.115, 0.004, 0.009), weave=420.0, bump=1.0, sheen=0.4, mottle=0.2)
    return m


def room(x0, x1, y0, y1, height, windows=()):
    """Stand-in church interior for previews: red carpet, white plaster walls,
    dark wood ceiling, bright tall windows (emissive) for the varnish to
    reflect. windows = [(wall 'x0'|'x1'|'y1', centre, width, sill, top), ...]"""
    s = bpy.context.scene
    white = common.flat_material("PreviewPlaster", (0.80, 0.78, 0.74), 0.9)
    ceil = common.flat_material("PreviewCeiling", (0.05, 0.02, 0.012), 0.5)
    glow = bpy.data.materials.new("PreviewWindow")
    glow.use_nodes = True
    gb = common.bsdf(glow)
    gb.inputs["Emission Color"].default_value = (0.85, 0.92, 1.0, 1)
    gb.inputs["Emission Strength"].default_value = 5.0

    def quad(name, pts, mat):
        me = bpy.data.meshes.new(name)
        me.from_pydata(pts, [], [(0, 1, 2, 3)])
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        s.collection.objects.link(ob)
    quad("PreviewFloor", [(x0, y0, -0.001), (x1, y0, -0.001), (x1, y1, -0.001), (x0, y1, -0.001)], carpet_material())
    quad("PreviewCeil", [(x0, y0, height), (x1, y0, height), (x1, y1, height), (x0, y1, height)], ceil)
    quad("PreviewWallX0", [(x0, y0, 0), (x0, y1, 0), (x0, y1, height), (x0, y0, height)], white)
    quad("PreviewWallX1", [(x1, y0, 0), (x1, y1, 0), (x1, y1, height), (x1, y0, height)], white)
    quad("PreviewWallY0", [(x0, y0, 0), (x1, y0, 0), (x1, y0, height), (x0, y0, height)], white)
    quad("PreviewWallY1", [(x0, y1, 0), (x1, y1, 0), (x1, y1, height), (x0, y1, height)], white)
    for wall, c, w, sill, top in windows:
        e = 0.01
        if wall == "x0":
            pts = [(x0 + e, c - w / 2, sill), (x0 + e, c + w / 2, sill), (x0 + e, c + w / 2, top), (x0 + e, c - w / 2, top)]
        elif wall == "x1":
            pts = [(x1 - e, c - w / 2, sill), (x1 - e, c + w / 2, sill), (x1 - e, c + w / 2, top), (x1 - e, c - w / 2, top)]
        else:
            pts = [(c - w / 2, y1 - e, sill), (c + w / 2, y1 - e, sill), (c + w / 2, y1 - e, top), (c - w / 2, y1 - e, top)]
        quad("PreviewWindow", pts, glow)
    w = bpy.data.worlds.new("PreviewWorld")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.02, 0.02, 0.02, 1)
    s.world = w


def lights(specs):
    """specs = [((x, y, z), watts, size), ...] warm ceiling fittings pointing down."""
    s = bpy.context.scene
    for i, (loc, power, size) in enumerate(specs):
        ld = bpy.data.lights.new("PreviewLight%d" % i, "AREA")
        ld.energy, ld.size = power, size
        ld.color = (1.0, 0.86, 0.68)
        lo = bpy.data.objects.new("PreviewLight%d" % i, ld)
        lo.location = loc
        s.collection.objects.link(lo)


def preview(name, cam, look, lens=40, samples=32, size=(640, 480), setup=True, half=4.5, height=4.2):
    """Preview in a small church-like room (see room()). Call AFTER
    common.save so none of this ends up in the asset file. setup=False
    re-uses the room and lights from an earlier call."""
    if setup:
        room(-half, half, -half, half, height,
             windows=[("x0", -2.4, 0.9, 1.1, 3.6), ("x0", 0.0, 0.9, 1.1, 3.6), ("x0", 2.4, 0.9, 1.1, 3.6),
                      ("y1", -1.5, 0.9, 1.1, 3.6), ("y1", 1.5, 0.9, 1.1, 3.6)])
        lights([((0.0, -1.0, height - 0.3), 270, 1.6), ((1.5, 1.5, height - 0.3), 170, 1.2)])
        vs = bpy.context.scene.view_settings
        try:
            vs.look = "AgX - Medium High Contrast"
        except TypeError:
            pass
    common.render_preview(name, cam, look, lens=lens, size=size, samples=samples)
