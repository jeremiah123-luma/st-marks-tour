"""Iconostasis -> collection `Iconostasis`, saved as blender/assets/iconostasis.blend.

Origin: floor, centre of the screen. Front face at local y=0 facing -Y; the body
occupies y = 0..ICONO_D, mouldings/relief stand a few cm proud (negative y).

Run: Blender -b --python blender/assets/iconostasis.py [-- [fast] overall left right door top centre lamp supper cruc marq | none]
(no view names = the six standard previews at 960 px; `fast` = 640 px / 32 samples; `none` = build and save only).

Every object is saved with an identity transform and no parent offset (repeats
are baked into joined meshes), so the asset can be moved as a whole by any means.
"""
import os
import sys
import math

import bpy
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common  # noqa: E402

common.reset_scene()
COL = common.collection("Iconostasis")

W = common.NAVE_W
H = common.ICONO_H
D = common.ICONO_D
HW = W / 2

# ---- layout. Every size is a common.py constant times a ratio measured off the
# photos (ratios of the screen's own width/height), so nothing here goes stale
# when common.py is rescaled. Only object-scale details (TV, mouldings) are metres.
SX = common.SIDE_DOOR_X
CDW, CDH = common.DOOR_W * 1.2, common.DOOR_H            # centre (royal) door
SDW, SDH = common.DOOR_W * 0.70, common.DOOR_H * 0.76    # side doors are smaller
FR, CFR = 0.135, 0.17            # door frame stile widths (side, centre)
SFRAME_TOP = SDH + 0.12
CFRAME_TOP = CDH + 0.10
SFX = SDW / 2 + FR               # side frame half width
CFX = CDW / 2 + CFR
BASE_H = 0.18
RAIL0, RAIL1 = H * 0.695, H * 0.725      # rail under the apostle row
ROW0, ROW1 = RAIL1, H * 0.955            # apostle row
TV_W, TV_H = 1.43, 0.81                  # 65 inch panel
TV_Z0 = RAIL0 - 0.02 - TV_H
EDGE = SX + SFX                  # marquetry starts here, lattice ends here
TRIP_W, TRIP_H, TRIP_Z = W * 0.111, H * 0.205, H * 0.228
TRIP_X = (EDGE + HW) / 2
ICON_X, ICON_W, ICON_H, ICON_Z = W * 0.129, 0.56, 0.86, H * 0.245
LS_OUT = W * 0.165               # Last Supper frame, outer width
LS_FR = 0.05
AP_END = W * 0.012               # plain end post each side of the row
AP_ARCH = (W - LS_OUT - 2 * AP_END) / (12 + 14 * 0.27)   # arch frame outer width
AP_PANEL = AP_ARCH * 0.27                                # carved panel between arches
AP_PITCH = AP_ARCH + AP_PANEL
AP_TRIM = AP_ARCH * 0.115
AP_W = AP_ARCH - 2 * AP_TRIM                             # painted icon width
AP_Z0 = ROW0 + 0.035 + AP_TRIM                           # icon bottom
AP_Z1 = AP_Z0 + AP_W * 1.36                              # icon arch top
AP_X0 = LS_OUT / 2 + AP_PANEL + AP_ARCH / 2              # first arch centre


def srgb(r, g, b):
    f = lambda c: ((c / 255 + 0.055) / 1.055) ** 2.4 if c > 10 else c / 255 / 12.92
    return (f(r), f(g), f(b))


# ---------------------------------------------------------------- materials
def wood(name, dark, light, axis="Z", scale=3.0, rough=0.42, bump=0.08, stretch=14.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = common.bsdf(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    sc = [stretch, stretch, stretch]
    sc["XYZ".index(axis)] = 1.0
    mp.inputs["Scale"].default_value = sc
    no = nt.nodes.new("ShaderNodeTexNoise")
    no.inputs["Scale"].default_value = scale
    no.inputs["Detail"].default_value = 8.0
    no.inputs["Distortion"].default_value = 0.9
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.36
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].position = 0.66
    ramp.color_ramp.elements[1].color = (*light, 1)
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    nt.links.new(tc.outputs["Object"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], no.inputs["Vector"])
    nt.links.new(no.outputs[0], ramp.inputs[0])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(no.outputs[0], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    return m


def setin(b, name, val):
    if name in b.inputs:
        b.inputs[name].default_value = val


M_PINE = wood("wood_pine", srgb(112, 54, 22), srgb(176, 104, 48), "Z", 2.2, 0.38, 0.10)
M_PINE_H = wood("wood_pine_h", srgb(112, 54, 22), srgb(172, 100, 46), "X", 2.2, 0.38, 0.10)
M_BODY = wood("wood_body", srgb(92, 48, 24), srgb(130, 72, 36), "Z", 2.5)
M_GROUND = wood("marq_ground", srgb(132, 70, 30), srgb(176, 104, 48), "Z", 5.0, 0.40, 0.06, 9.0)
M_MAPLE = wood("marq_maple", srgb(205, 158, 98), srgb(232, 190, 128), "X", 4.0, 0.42, 0.04)
M_WALNUT = wood("marq_walnut", srgb(40, 22, 14), srgb(66, 36, 22), "Z", 4.0, 0.45, 0.05)
M_BEAD = wood("lattice_bead", srgb(196, 150, 96), srgb(226, 184, 126), "X", 5.0, 0.40, 0.03)
M_ROW = wood("wood_row", srgb(100, 42, 20), srgb(146, 70, 32), "Z", 3.0, 0.36)
M_ROW_H = wood("wood_row_h", srgb(100, 42, 20), srgb(146, 70, 32), "X", 3.0, 0.36)
M_CARVED = wood("wood_carved", srgb(52, 24, 14), srgb(92, 44, 24), "Z", 6.0, 0.55)   # only until carved_vine.jpg exists
M_LBACK = common.flat_material("lattice_back", srgb(30, 17, 11), 0.7)
M_BRASS = common.flat_material("brass", srgb(200, 150, 60), 0.3, 1.0)
M_GOLD = common.flat_material("gold_fringe", srgb(212, 170, 80), 0.38, 1.0)
M_TV = common.flat_material("tv_black", (0.004, 0.004, 0.005), 0.06)
M_TVB = common.flat_material("tv_bezel", (0.01, 0.01, 0.01), 0.35)
M_IVORY = common.flat_material("globe_ivory", srgb(235, 222, 190), 0.3)
_b = common.bsdf(M_IVORY)
setin(_b, "Emission Color", (*srgb(255, 225, 170), 1))
setin(_b, "Emission Strength", 0.05)
M_GLASS = common.flat_material("lamp_glass", srgb(200, 14, 14), 0.12)
_b = common.bsdf(M_GLASS)
setin(_b, "Transmission Weight", 0.55)
setin(_b, "Emission Color", (*srgb(255, 30, 20), 1))
setin(_b, "Emission Strength", 1.6)
M_PIERCED = bpy.data.materials.new("lamp_pierced_brass")   # brass basket, red glow through the piercings
M_PIERCED.use_nodes = True
_b = common.bsdf(M_PIERCED)
_nt = M_PIERCED.node_tree
_tc = _nt.nodes.new("ShaderNodeTexCoord")
_vo = _nt.nodes.new("ShaderNodeTexVoronoi")
_vo.inputs["Scale"].default_value = 95.0
_rp = _nt.nodes.new("ShaderNodeValToRGB")
_rp.color_ramp.elements[0].position = 0.30
_rp.color_ramp.elements[0].color = (*srgb(230, 20, 16), 1)
_rp.color_ramp.elements[1].position = 0.42
_rp.color_ramp.elements[1].color = (*srgb(205, 155, 60), 1)
_re = _nt.nodes.new("ShaderNodeValToRGB")
_re.color_ramp.elements[0].position = 0.30
_re.color_ramp.elements[0].color = (1, 1, 1, 1)
_re.color_ramp.elements[1].position = 0.42
_re.color_ramp.elements[1].color = (0, 0, 0, 1)
_nt.links.new(_tc.outputs["Object"], _vo.inputs["Vector"])
_nt.links.new(_vo.outputs["Distance"], _rp.inputs[0])
_nt.links.new(_vo.outputs["Distance"], _re.inputs[0])
_nt.links.new(_rp.outputs["Color"], _b.inputs["Base Color"])
_nt.links.new(_rp.outputs["Color"], _b.inputs["Emission Color"])
_nt.links.new(_re.outputs["Color"], _b.inputs["Emission Strength"])
_nt.links.new(_re.outputs["Color"], _b.inputs["Roughness"])
_b.inputs["Metallic"].default_value = 0.8
BURG = srgb(96, 12, 30)


def velvet(name, tex):
    m = common.image_material(name, "icons/%s.jpg" % tex, fallback=BURG, rough=0.9)
    b = common.bsdf(m)
    setin(b, "Sheen Weight", 1.0)
    setin(b, "Sheen Roughness", 0.35)
    setin(b, "Sheen Tint", (*srgb(230, 90, 110), 1))
    return m


def icon_mat(tex):
    return common.image_material("icon_" + tex, "icons/%s.jpg" % tex, fallback=srgb(214, 165, 60), rough=0.4)


# ---------------------------------------------------------------- mesh helpers
class MB:
    def __init__(self):
        self.bm = bmesh.new()
        self.uv = None

    def face(self, pts, want, mat=0, smooth=False, uvs=None):
        vs = [self.bm.verts.new(p) for p in pts]
        f = self.bm.faces.new(vs)
        f.normal_update()
        if f.normal.dot(Vector(want)) < 0:
            f.normal_flip()
        f.material_index = mat
        f.smooth = smooth
        if uvs:
            if self.uv is None:
                self.uv = self.bm.loops.layers.uv.new("UVMap")
            lut = {v: uv for v, uv in zip(vs, uvs)}
            for lp in f.loops:
                lp[self.uv].uv = lut[lp.vert]
        return f

    def box(self, x0, x1, y0, y1, z0, z1, mat=0, skip=""):
        F = {
            "f": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
            "b": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
            "l": ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
            "r": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
            "d": ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
            "u": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
        }
        for k, (p, w) in F.items():
            if k not in skip:
                self.face(p, w, mat)

    def finish(self, name, mats, loc=(0, 0, 0), parent=None):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
        ng = [f for f in bm.faces if len(f.verts) > 4]
        if ng:
            bmesh.ops.triangulate(bm, faces=ng)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for m in mats:
            me.materials.append(m)
        return place(name, me, loc, parent)


def place(name, me, loc=(0, 0, 0), parent=None):
    ob = bpy.data.objects.new(name, me)
    COL.objects.link(ob)
    ob.location = loc
    if parent:
        ob.parent = parent
    return ob


def arc_pts(cx, w, zt, n, rise=None, grow=0.0):
    r = w / 2
    rise = rise or r
    sp = zt - rise
    return [(cx + (r + grow) * math.cos(math.pi * (1 - i / n)),
             sp + (rise + grow) * math.sin(math.pi * (1 - i / n))) for i in range(n + 1)]


def arch_board(mb, x0, x1, z0, z1, y0, y1, openings, mat=0, n=16, back=False, top=True):
    """Board x0..x1, z0..z1, y0(front)..y1 with round-arched openings
    [(cx, w, zbottom, ztop)], built from boxes + arch strips (no booleans)."""
    skip = "" if back else "b"
    x = x0
    for cx, w, zb, zt in sorted(openings):
        l, r = cx - w / 2, cx + w / 2
        if l - x > 1e-4:
            mb.box(x, l, y0, y1, z0, z1, mat, skip)
        if zb - z0 > 1e-4:
            mb.box(l, r, y0, y1, z0, zb, mat, skip + "lr")
        pts = arc_pts(cx, w, zt, n)
        sp = zt - w / 2
        for (xa, za), (xb, zb2) in zip(pts, pts[1:]):
            mb.face([(xa, y0, za), (xb, y0, zb2), (xb, y0, z1), (xa, y0, z1)], (0, -1, 0), mat)
            if back:
                mb.face([(xa, y1, za), (xb, y1, zb2), (xb, y1, z1), (xa, y1, z1)], (0, 1, 0), mat)
            xm, zm = (xa + xb) / 2, (za + zb2) / 2
            mb.face([(xa, y0, za), (xb, y0, zb2), (xb, y1, zb2), (xa, y1, za)],
                    (cx - xm, 0, sp - zm - 1e-3), mat)
        if top:
            mb.face([(l, y0, z1), (r, y0, z1), (r, y1, z1), (l, y1, z1)], (0, 0, 1), mat)
        x = r
    if x1 - x > 1e-4:
        mb.box(x, x1, y0, y1, z0, z1, mat, skip)


def arch_trim(mb, cx, w, zb, zt, tw, yb, proud, mat=0, n=16, sill=True):
    """Raised moulding ring around an arched opening."""
    r = w / 2
    sp = zt - r
    inner = [(cx - r, zb)] + arc_pts(cx, w, zt, n) + [(cx + r, zb)]
    outer = [(cx - r - tw, zb)] + arc_pts(cx, w, zt, n, grow=tw) + [(cx + r + tw, zb)]
    mid = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(inner, outer)]
    yf = yb - proud
    ym = yb - proud * 0.55
    for i in range(len(inner) - 1):
        ia, ib, oa, ob, ma, mb2 = inner[i], inner[i + 1], outer[i], outer[i + 1], mid[i], mid[i + 1]
        xm, zm = (ia[0] + ib[0]) / 2, (ia[1] + ib[1]) / 2
        wi = Vector((cx - xm, 0, min(0.0, sp - zm)))
        if wi.length < 1e-6:
            wi = Vector((0, 0, -1))
        mb.face([(ia[0], yb, ia[1]), (ib[0], yb, ib[1]), (ib[0], yf, ib[1]), (ia[0], yf, ia[1])], wi, mat)
        mb.face([(ia[0], yf, ia[1]), (ib[0], yf, ib[1]), (mb2[0], yf, mb2[1]), (ma[0], yf, ma[1])], (0, -1, 0), mat)
        mb.face([(ma[0], yf, ma[1]), (mb2[0], yf, mb2[1]), (ob[0], ym, ob[1]), (oa[0], ym, oa[1])],
                Vector((0, -1, 0)) - wi.normalized() * 0.3, mat)
        mb.face([(oa[0], ym, oa[1]), (ob[0], ym, ob[1]), (ob[0], yb, ob[1]), (oa[0], yb, oa[1])], -wi, mat)
    if sill:
        mb.box(cx - r - tw, cx + r + tw, yf, yb, zb - tw, zb, mat, "b")


def arched_icon(name, cx, w, zb, zt, y, mat, n=16, parent=None, loc=(0, 0, 0)):
    mb = MB()
    pts = [(cx - w / 2, zb), (cx + w / 2, zb)] + arc_pts(cx, w, zt, n)[::-1]
    uvs = [((px - cx) / w + 0.5, (pz - zb) / (zt - zb)) for px, pz in pts]
    mb.face([(px, y, pz) for px, pz in pts], (0, -1, 0), 0, False, uvs)
    return mb.finish(name, [mat], loc, parent)


def rect_icon(name, x0, x1, z0, z1, y, mat):
    mb = MB()
    mb.face([(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)], (0, -1, 0), 0, False,
            [(0, 0), (1, 0), (1, 1), (0, 1)])
    return mb.finish(name, [mat])


def poly_offset(pts, d):
    """Offset a CCW polygon outward by d (mitred)."""
    out = []
    n = len(pts)
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e1, e2 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n1, n2 = Vector((e1.y, -e1.x)), Vector((e2.y, -e2.x))
        k = 1 + n1.dot(n2)
        out.append(tuple(p1 + (n1 + n2) * (d / max(k, 0.2))))
    return out


def extrude_poly(mb, pts, yb, hgt, mat=0, bevel=0.0, smooth=False):
    """Raised flat relief: CCW polygon in (x, z) standing hgt proud of y=yb."""
    top = poly_offset(pts, -bevel) if bevel else pts
    mb.face([(x, yb - hgt, z) for x, z in top], (0, -1, 0), mat, smooth)
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        ta, tb = top[i], top[(i + 1) % n]
        e = Vector((b[0] - a[0], b[1] - a[1]))
        mb.face([(a[0], yb, a[1]), (b[0], yb, b[1]), (tb[0], yb - hgt, tb[1]), (ta[0], yb - hgt, ta[1])],
                (e.y, -0.2, -e.x), mat, smooth)


def strip_loop(mb, pts, yb, w, h, bevel, mat=0):
    """Raised bevelled strip following a closed CCW polygon centreline."""
    A = poly_offset(pts, w / 2)
    B = poly_offset(pts, w / 2 - bevel)
    C = poly_offset(pts, -(w / 2 - bevel))
    Dd = poly_offset(pts, -w / 2)
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        for (p, q, ya, yb2) in ((A, B, yb, yb - h), (B, C, yb - h, yb - h), (C, Dd, yb - h, yb)):
            mb.face([(p[i][0], ya, p[i][1]), (p[j][0], ya, p[j][1]),
                     (q[j][0], yb2, q[j][1]), (q[i][0], yb2, q[i][1])], (0, -1, 0), mat)


def ngon(cx, cz, r, n, rot=0.0, sx=1.0, sz=1.0):
    return [(cx + sx * r * math.cos(rot + 2 * math.pi * i / n),
             cz + sz * r * math.sin(rot + 2 * math.pi * i / n)) for i in range(n)]


def cross_pts(cx, cz, s):
    """Cross pattee outline (CCW), half extent s."""
    out = []
    for k in range(4):
        a = k * math.pi / 2
        d = Vector((math.cos(a), math.sin(a)))
        nn = Vector((-d.y, d.x))
        for p in (d * s - nn * 0.42 * s, d * s + nn * 0.42 * s, (d + nn) * 0.15 * s):
            out.append((cx + p.x, cz + p.y))
    return out


def lathe(mb, prof, o, axis, e1, e2, sides, a0=0.0, a1=2 * math.pi, mat=0, smooth=True):
    """Revolve profile [(r, t)] about `axis` through o. Outside is to the right
    of the profile direction."""
    o, axis, e1, e2 = Vector(o), Vector(axis), Vector(e1), Vector(e2)
    for (r0, t0), (r1, t1) in zip(prof, prof[1:]):
        nr, nz = (t1 - t0), -(r1 - r0)
        for i in range(sides):
            aa = a0 + (a1 - a0) * i / sides
            ab = a0 + (a1 - a0) * (i + 1) / sides
            da, db = e1 * math.cos(aa) + e2 * math.sin(aa), e1 * math.cos(ab) + e2 * math.sin(ab)
            dm = (da + db).normalized()
            pts = [o + da * r0 + axis * t0, o + db * r0 + axis * t0,
                   o + db * r1 + axis * t1, o + da * r1 + axis * t1]
            if r0 < 1e-6:
                pts = pts[1:]
            elif r1 < 1e-6:
                pts = pts[:3]
            mb.face([tuple(p) for p in pts], dm * nr + axis * nz, mat, smooth)


def rod(mb, p0, p1, rad, mat=0, sides=3):
    p0, p1 = Vector(p0), Vector(p1)
    ax = (p1 - p0)
    ln = ax.length
    ax.normalize()
    e1 = ax.orthogonal().normalized()
    e2 = ax.cross(e1)
    lathe(mb, [(rad, 0), (rad, ln)], p0, ax, e1, e2, sides, mat=mat, smooth=False)


def sweep_x(mb, prof, x0, x1, mat=0):
    """Extrude a closed CCW (y-left... ) profile [(y, z)] along x with end caps."""
    n = len(prof)
    area = sum(prof[i][0] * prof[(i + 1) % n][1] - prof[(i + 1) % n][0] * prof[i][1] for i in range(n))
    sg = 1 if area > 0 else -1
    for i in range(n):
        (ya, za), (yb, zb) = prof[i], prof[(i + 1) % n]
        if abs(ya) < 1e-9 and abs(yb) < 1e-9:
            continue  # face against the body
        mb.face([(x0, ya, za), (x1, ya, za), (x1, yb, zb), (x0, yb, zb)],
                (0, sg * (zb - za), -sg * (yb - ya)), mat)
    mb.face([(x0, y, z) for y, z in prof], (-1, 0, 0), mat)
    mb.face([(x1, y, z) for y, z in prof], (1, 0, 0), mat)


# ---------------------------------------------------------------- body
mb = MB()
doors = [(-SX, SDW, 0, SDH), (0, CDW, 0, CDH), (SX, SDW, 0, SDH)]
arch_board(mb, -HW, HW, 0, H, 0, D, doors, 0, n=20, back=True, top=True)
mb.finish("Body", [M_BODY])

# flat grounds for the three thirds (relief modules sit on these)
mb = MB()
for s in (-1, 1):
    xa, xb = sorted((s * EDGE, s * HW))
    mb.face([(xa, -0.002, BASE_H), (xb, -0.002, BASE_H), (xb, -0.002, RAIL0), (xa, -0.002, RAIL0)], (0, -1, 0), 0)
mb.finish("MarquetryGround", [M_GROUND])

mb = MB()
arch_board(mb, -EDGE, EDGE, BASE_H, RAIL0, -0.002, 0.0,
           [(-SX, SDW, BASE_H, SDH), (0, CDW, BASE_H, CDH), (SX, SDW, BASE_H, SDH)], 0, n=20, top=False)
mb.finish("LatticeGround", [M_LBACK])

# ---------------------------------------------------------------- marquetry + bead lattice (tiled photo textures + bump)
def pattern_mat(name, tex, fallback, bump_dist, rough):
    """textures/patterns/<tex>.jpg tiled, with <tex>_height.jpg as bump; falls
    back to plain procedural wood until the files exist."""
    if not os.path.exists(os.path.join(common.TEX, "patterns", tex + ".jpg")):
        return fallback
    m = common.image_material(name, "patterns/%s.jpg" % tex, rough=rough)
    hp = os.path.join(common.TEX, "patterns", tex + "_height.jpg")
    if os.path.exists(hp):
        nt = m.node_tree
        ht = nt.nodes.new("ShaderNodeTexImage")
        ht.image = bpy.data.images.load(hp, check_existing=True)
        ht.image.colorspace_settings.name = "Non-Color"
        bp = nt.nodes.new("ShaderNodeBump")
        bp.inputs["Distance"].default_value = bump_dist
        bp.inputs["Strength"].default_value = 1.0
        nt.links.new(ht.outputs["Color"], bp.inputs["Height"])
        nt.links.new(bp.outputs["Normal"], common.bsdf(m).inputs["Normal"])
    return m


def planar_uv(ob, su, sv, x0=0.0, z0=0.0, mirror_about=None):
    """Front-projected UVs in tile units, so a pattern repeats at real scale."""
    me = ob.data
    uv = me.uv_layers.new(name="UVMap") if not me.uv_layers else me.uv_layers[0]
    for lp in me.loops:
        co = me.vertices[lp.vertex_index].co
        uv.data[lp.index].uv = ((co.x - x0) / su, (co.z - z0) / sv)


# marquetry: the photos show about six crosses across each outer third; the
# texture holds 2 x 2 crosses, so one image spans two periods
MQ_PERIOD = (HW - EDGE) / 6
mq = bpy.data.objects["MarquetryGround"]
mq.data.materials.clear()
mq.data.materials.append(pattern_mat("marquetry_cross", "marquetry_cross", M_GROUND, 0.012, 0.42))
planar_uv(mq, 2 * MQ_PERIOD, 2 * MQ_PERIOD, EDGE, BASE_H)
# bead lattice: block + bead = 0.09 m in the close-ups; the texture holds 4 of them
LT_IMG = 0.36
lt = bpy.data.objects["LatticeGround"]
lt.data.materials.clear()
lt.data.materials.append(pattern_mat("bead_lattice", "bead_lattice", M_LBACK, 0.03, 0.45))
planar_uv(lt, LT_IMG, LT_IMG, 0.0, BASE_H)

# ---------------------------------------------------------------- baseboard, rail, cornice, dividers
mb = MB()
for xa, xb in ((-HW, -EDGE), (-SX + SFX, -CFX), (CFX, SX - SFX), (EDGE, HW)):
    mb.box(xa, xb, -0.035, 0, 0, BASE_H, 0, "b")
    mb.box(xa, xb, -0.045, 0, BASE_H - 0.03, BASE_H, 0, "b")
mb.finish("Baseboard", [M_PINE_H])

mb = MB()
for s in (-1, 1):   # pine strip where marquetry meets the lattice / TV column
    xa, xb = sorted((s * EDGE, s * (EDGE + 0.045)))
    mb.box(xa, xb, -0.04, 0, SFRAME_TOP, RAIL0, 0, "b")
    xa, xb = sorted((s * HW, s * (HW - 0.06)))
    mb.box(xa, xb, -0.04, 0, 0, RAIL0, 0, "b")
mb.finish("Dividers", [M_PINE])

mb = MB()
sweep_x(mb, [(0, RAIL0), (-0.035, RAIL0), (-0.06, RAIL0 + 0.03), (-0.06, RAIL1 - 0.045),
             (-0.045, RAIL1 - 0.03), (-0.045, RAIL1), (0, RAIL1)], -HW, HW)
mb.finish("Rail", [M_ROW_H])

CORN0 = ROW1
mb = MB()
FAS0 = CORN0 + 0.055
sweep_x(mb, [(0, CORN0), (-0.04, CORN0), (-0.06, CORN0 + 0.02), (-0.16, CORN0 + 0.04), (-0.18, FAS0),
             (-0.18, H), (0, H)], -HW, HW)
# incised long hexagons along the fascia
nloz = 14
lp = W / nloz
zc = (FAS0 + H) / 2
hh = (H - FAS0) / 2 - 0.028
for k in range(nloz):
    cx = -HW + (k + 0.5) * lp
    hl = lp / 2 - 0.06
    pts = [(cx - hl, zc), (cx - hl + hh, zc - hh), (cx + hl - hh, zc - hh), (cx + hl, zc),
           (cx + hl - hh, zc + hh), (cx - hl + hh, zc + hh)]
    strip_loop(mb, pts, -0.18, 0.009, 0.004, 0.002, 0)
    strip_loop(mb, ngon(cx + lp / 2, zc, 0.022, 4), -0.18, 0.008, 0.004, 0.002, 0)
mb.finish("Cornice", [M_ROW_H])

# ---------------------------------------------------------------- doors: frames, curtains, crosses
def curtain(name, fr_name, cx, w, h, mat):
    nx, nz = 64, 12
    r = w / 2
    sp = h - r

    def ztop(x):
        d = abs(x - cx)
        return sp + math.sqrt(max(r * r - d * d, 0.0))

    def fold(x, z):
        u = (x - cx) / w + 0.5
        amp = (0.004 + 0.020 * max(0.0, 1 - z / h) ** 1.4) * (0.35 + 1.3 * abs(u - 0.5))
        return 0.13 + amp * (0.6 * math.sin(x * 2 * math.pi / 0.21 + cx) + 0.4 * math.sin(x * 2 * math.pi / 0.33 + 1.3))

    mb = MB()
    zb = 0.05
    for i in range(nx):
        xa, xb = cx - r + w * i / nx, cx - r + w * (i + 1) / nx
        ta, tb = ztop(xa), ztop(xb)
        for j in range(nz):
            pts = []
            for x, t, jj in ((xa, ta, j), (xb, tb, j), (xb, tb, j + 1), (xa, ta, j + 1)):
                z = zb + (t - zb) * jj / nz
                pts.append((x, fold(x, z), z))
            mb.face(pts, (0, -1, 0), 0, True, [((p[0] - cx) / w + 0.5, p[2] / h) for p in pts])
    ob = mb.finish(name, [mat])
    mb = MB()   # gold fringe along the hem
    for i in range(nx):
        xa, xb = cx - r + w * i / nx, cx - r + w * (i + 1) / nx
        mb.face([(xa, fold(xa, 0.0) - 0.004, 0.012), (xb, fold(xb, 0.0) - 0.004, 0.012),
                 (xb, fold(xb, zb) - 0.006, zb + 0.012), (xa, fold(xa, zb) - 0.006, zb + 0.012)], (0, -1, 0), 0, True)
    mb.finish(fr_name, [M_FRINGE])
    return ob


M_FRINGE = bpy.data.materials.new("gold_fringe_threads")
M_FRINGE.use_nodes = True
_b = common.bsdf(M_FRINGE)
_b.inputs["Base Color"].default_value = (*srgb(212, 170, 80), 1)
_b.inputs["Metallic"].default_value = 1.0
_b.inputs["Roughness"].default_value = 0.4
_nt = M_FRINGE.node_tree
_tc = _nt.nodes.new("ShaderNodeTexCoord")
_wv = _nt.nodes.new("ShaderNodeTexWave")
_wv.inputs["Scale"].default_value = 60.0
_bp = _nt.nodes.new("ShaderNodeBump")
_bp.inputs["Strength"].default_value = 0.8
_nt.links.new(_tc.outputs["Object"], _wv.inputs["Vector"])
_nt.links.new(_wv.outputs[0], _bp.inputs["Height"])
_nt.links.new(_bp.outputs["Normal"], _b.inputs["Normal"])

FY = -0.05   # door frames stand this far proud
mb = MB()
for s in (-1, 1):
    cx = s * SX
    arch_board(mb, cx - SFX, cx + SFX, 0, SFRAME_TOP, FY, 0, [(cx, SDW, 0, SDH)], 0, n=20)
    arch_trim(mb, cx, SDW, 0, SDH, 0.04, FY, 0.014, 0, n=20, sill=False)
    for t in (-1, 1):
        extrude_poly(mb, cross_pts(cx + t * (SFX - 0.105), SFRAME_TOP - 0.115, 0.07), FY, 0.012, 0, 0.004)
arch_board(mb, -CFX, CFX, 0, CFRAME_TOP, FY, 0, [(0, CDW, 0, CDH)], 0, n=24)
arch_trim(mb, 0, CDW, 0, CDH, 0.05, FY, 0.016, 0, n=24, sill=False)
for t in (-1, 1):   # royal door spandrels: rosette + fluted rays
    rx, rz = t * (CFX - 0.15), CFRAME_TOP - 0.16
    extrude_poly(mb, ngon(rx, rz, 0.115, 16), FY, 0.008, 0, 0.004)
    extrude_poly(mb, cross_pts(rx, rz, 0.085), FY - 0.008, 0.008, 0, 0.003)
    for k in range(5):     # rays down the stile
        x0 = rx - 0.105 + k * 0.047
        ln = 0.30 + 0.07 * (k if t > 0 else 4 - k)
        xa, xb = x0, x0 + 0.026
        extrude_poly(mb, [(xa, rz - 0.15 - ln), (xb, rz - 0.15 - ln), (xb, rz - 0.15), (xa, rz - 0.15)], FY, 0.008, 0, 0.003)
    for k in range(4):     # rays along the head toward the crown of the arch
        z0 = rz + 0.085 - k * 0.042
        ln = 0.42 - 0.085 * k
        xa, xb = sorted((rx - t * 0.15, rx - t * (0.15 + ln)))
        extrude_poly(mb, [(xa, z0 - 0.024), (xb, z0 - 0.024), (xb, z0), (xa, z0)], FY, 0.008, 0, 0.003)
mb.finish("DoorFrames", [M_PINE])

curtain("Icon_curtain_mary", "CurtainFringe_L", -SX, SDW, SDH, velvet("curtain_mary", "curtain_mary"))
# the RIGHT door curtain is St Mark with the lion (batch3 IMG_7956/7957), its own texture
curtain("Icon_curtain_right", "CurtainFringe_R", SX, SDW, SDH, velvet("curtain_right", "curtain_right"))
curtain("Icon_curtain_christ", "CurtainFringe_C", 0, CDW, CDH, velvet("curtain_christ", "curtain_christ"))

# ---------------------------------------------------------------- TVs
for s, nm in ((-1, "L"), (1, "R")):
    mb = MB()
    x0, x1 = s * SX - TV_W / 2, s * SX + TV_W / 2
    mb.box(x0, x1, -0.085, -0.035, TV_Z0, TV_Z0 + TV_H, 1, "f")
    mb.face([(x0 + 0.012, -0.0855, TV_Z0 + 0.012), (x1 - 0.012, -0.0855, TV_Z0 + 0.012),
             (x1 - 0.012, -0.0855, TV_Z0 + TV_H - 0.012), (x0 + 0.012, -0.0855, TV_Z0 + TV_H - 0.012)],
            (0, -1, 0), 0, False, [(0, 0), (1, 0), (1, 1), (0, 1)])
    mb.face([(x0, -0.085, TV_Z0), (x1, -0.085, TV_Z0), (x1, -0.085, TV_Z0 + TV_H), (x0, -0.085, TV_Z0 + TV_H)], (0, -1, 0), 1)
    mb.box(s * SX - 0.2, s * SX + 0.2, -0.035, 0, TV_Z0 + 0.2, TV_Z0 + 0.6, 1, "fb")
    mb.finish("TV_" + nm, [M_TV, M_TVB])

# ---------------------------------------------------------------- triptychs
TB_P = TRIP_W * 0.305            # bay pitch
TB_W = TRIP_W * 0.245            # bay opening width
TB_Z0, TB_Z1 = TRIP_H * 0.09, TRIP_H * 0.80
COLUMN_H = TB_Z1 - TB_W / 2 - TB_Z0 + 0.02
mb = MB()
ch = COLUMN_H
cp = [(0.0, 0.0), (0.026, 0.0), (0.026, 0.03), (0.016, 0.042), (0.020, ch * 0.35), (0.020, ch * 0.62), (0.015, ch - 0.045),
      (0.026, ch - 0.03), (0.026, ch), (0.0, ch)]
lathe(mb, cp, (0, 0, 0), (0, 0, 1), (1, 0, 0), (0, 1, 0), 8)
_c = mb.finish("TriptychColumn", [M_MAPLE])
COLUMN_MESH = _c.data
bpy.data.objects.remove(_c)

TRIPS = {-1: ["mark", "mikhail", "annunciation_panel"], 1: ["john_baptist", "george", "mina_panel"]}
for s in (-1, 1):
    ox, oz = s * TRIP_X, TRIP_Z
    ty = -0.065
    bays = [(ox + k * TB_P, TB_W, oz + TB_Z0, oz + TB_Z1) for k in (-1, 0, 1)]
    mb = MB()
    arch_board(mb, ox - TRIP_W / 2, ox + TRIP_W / 2, oz, oz + TRIP_H, ty, 0, bays, 0, n=16)
    for cx, w, zb, zt in bays:
        arch_trim(mb, cx, w, zb, zt, 0.018, ty, 0.010, 0, n=16, sill=False)
    for t in (-1, 1):
        extrude_poly(mb, cross_pts(ox + t * TB_P / 2, oz + (TB_Z1 + TRIP_H) / 2 - 0.005, TRIP_H * 0.065), ty, 0.010, 0, 0.003)
    mb.box(ox - TRIP_W / 2 - 0.02, ox + TRIP_W / 2 + 0.02, ty - 0.02, 0, oz + TRIP_H - 0.03, oz + TRIP_H + 0.01, 0, "b")
    mb.box(ox - TRIP_W / 2 - 0.02, ox + TRIP_W / 2 + 0.02, ty - 0.03, 0, oz - 0.01, oz + TB_Z0 - 0.015, 0, "b")
    mb.finish("Triptych_%s" % ("L" if s < 0 else "R"), [M_PINE])
    for k, t in enumerate((-1.5, -0.5, 0.5, 1.5)):
        place("TriptychColumn_%s%d" % ("L" if s < 0 else "R", k), COLUMN_MESH, (ox + t * TB_P, ty - 0.018, oz + TB_Z0 - 0.015))
    for (cx, w, zb, zt), tex in zip(bays, TRIPS[s]):
        arched_icon("Icon_" + tex, cx, w, zb, zt, -0.02, icon_mat(tex))

# ---------------------------------------------------------------- Theotokos / Christ icons
for s, tex in ((-1, "theotokos"), (1, "christ")):
    cx = s * ICON_X
    iy = -0.06
    op = (cx, ICON_W - 0.17, ICON_Z + 0.10, ICON_Z + ICON_H - 0.085)
    mb = MB()
    arch_board(mb, cx - ICON_W / 2, cx + ICON_W / 2, ICON_Z, ICON_Z + ICON_H, iy, 0, [op], 0, n=16)
    arch_trim(mb, *op, 0.025, iy, 0.012, 0, n=16, sill=True)
    for t in (-1, 1):   # carved leaf in each upper corner
        extrude_poly(mb, ngon(cx + t * (ICON_W / 2 - 0.06), ICON_Z + ICON_H - 0.065, 0.04, 4), iy, 0.008, 0, 0.004)
    mb.finish("IconFrame_" + tex, [M_PINE])
    arched_icon("Icon_" + tex, op[0], op[1], op[2], op[3], -0.02, icon_mat(tex))

# ---------------------------------------------------------------- apostle row
# Pierced vine-and-leaf carving: photo texture (tools/textures/carved_vine.py,
# one tile = VINE_W x VINE_H metres) with its height map as bump. Mapped with
# real-scale UVs: upright in the panels between the arches, turned on its side
# for the ground behind (spandrels and the band under the cornice), where the
# vine runs along the row.
VINE_W, VINE_H = 0.28, 0.80
M_VINE = pattern_mat("carved_vine", "carved_vine", M_CARVED, 0.012, 0.5)
mb = MB()
gq = [(-HW, ROW0), (HW, ROW0), (HW, ROW1), (-HW, ROW1)]
mb.face([(x, -0.003, z) for x, z in gq], (0, -1, 0), 0, False, [(z / VINE_W, x / VINE_H) for x, z in gq])
mb.finish("ApostleRowGround", [M_VINE])
mb = MB()
for s in (-1, 1):
    xa, xb = sorted((s * HW, s * (HW - AP_END)))
    mb.box(xa, xb, -0.045, 0, ROW0, ROW1, 0, "b")
mb.box(-HW, HW, -0.03, 0, ROW0, ROW0 + 0.03, 0, "b")
mb.finish("ApostleRowPosts", [M_ROW])

AP_HI = AP_Z1 - AP_Z0
mb = MB()
arch_trim(mb, 0, AP_W, 0, AP_HI, AP_TRIM, -0.003, 0.036, 0, n=16, sill=True)
arch_trim(mb, 0, AP_W + AP_TRIM * 0.9, -AP_TRIM * 0.45, AP_HI + AP_TRIM * 0.45, AP_TRIM * 0.55, -0.003, 0.026, 0, n=16, sill=False)
_a = mb.finish("ApostleArch", [M_ROW])
ARCH_MESH = _a.data
bpy.data.objects.remove(_a)


def medallion(mb, cx, cz, r, yb, m_rim, m_disc):
    """Round cross medallion: walnut rim, lighter disc, carved cross pattee."""
    extrude_poly(mb, ngon(cx, cz, r * 1.2, 20), yb, 0.012, m_rim, 0.004)
    extrude_poly(mb, ngon(cx, cz, r, 20), yb - 0.012, 0.007, m_disc, 0.004)
    extrude_poly(mb, cross_pts(cx, cz, r * 0.74), yb - 0.019, 0.006, m_disc, 0.003)


# framed vine panel between two arches + the cross medallion above it (one module)
mb = MB()
pw = AP_PANEL / 2 - 0.006
MED_R = AP_ARCH * 0.115
ph = AP_HI - AP_W / 2 + AP_TRIM
med_z = AP_HI + AP_TRIM - MED_R * 0.9
vq = [(-pw, 0.0), (pw, 0.0), (pw, ph), (-pw, ph)]
mb.face([(x, -0.007, z) for x, z in vq], (0, -1, 0), 0, False, [((x + pw) / (2 * pw) * 0.5, z / VINE_H) for x, z in vq])
for sx in (-1, 1):   # fillets framing the panel
    extrude_poly(mb, [(sx * pw - 0.006, -0.02), (sx * pw + 0.006, -0.02), (sx * pw + 0.006, ph), (sx * pw - 0.006, ph)], -0.003, 0.016, 1, 0.003)
medallion(mb, 0, med_z, MED_R, -0.003, 1, 2)
_p = mb.finish("CarvedPanel", [M_VINE, M_ROW, M_MAPLE])
PANEL_MESH = _p.data
bpy.data.objects.remove(_p)

ap_x = [-(AP_X0 + AP_PITCH * i) for i in range(5, -1, -1)] + [AP_X0 + AP_PITCH * i for i in range(6)]
for k, x in enumerate(ap_x):
    tex = "apostle_%02d" % (k + 1)
    place("ApostleArch_%02d" % (k + 1), ARCH_MESH, (x, 0, AP_Z0))
    arched_icon("Icon_" + tex, 0, AP_W, 0, AP_HI, -0.012, icon_mat(tex), loc=(x, 0, AP_Z0))
pan_x = []
for s in (-1, 1):
    pan_x += [s * (AP_X0 - AP_PITCH / 2 + AP_PITCH * i) for i in range(7)]
for k, x in enumerate(sorted(pan_x)):
    place("CarvedPanel_%02d" % k, PANEL_MESH, (x, 0, AP_Z0 - AP_TRIM))

# Last Supper. Above it the same vine carving runs on in the shadow of the
# shelf, with a row of small cross medallions (batch3 IMG_7952, 7953).
LS_W = LS_OUT - 2 * LS_FR
LS_H = LS_W / 3.4
x0, x1, z0 = -LS_W / 2, LS_W / 2, AP_Z0 - AP_TRIM + LS_FR
z1 = z0 + LS_H
mb = MB()
fw = LS_FR
for (a, b, c, d) in ((x0 - fw, x1 + fw, z0 - fw, z0), (x0 - fw, x1 + fw, z1, z1 + fw), (x0 - fw, x0, z0, z1), (x1, x1 + fw, z0, z1)):
    mb.box(a, b, -0.04, -0.003, c, d, 0, "b")
mb.box(x0 - fw - 0.012, x1 + fw + 0.012, -0.05, -0.003, z1 + fw, z1 + fw + 0.02, 0, "b")
nb = 6
bz = (z1 + fw + 0.02 + ROW1) / 2
br = min(0.042, (ROW1 - z1 - fw - 0.02) * 0.33)
for k in range(nb):
    medallion(mb, -LS_OUT / 2 + (k + 0.5) * LS_OUT / nb, bz, br, -0.003, 0, 1)
mb.finish("LastSupperFrame", [M_ROW_H, M_MAPLE])
rect_icon("Icon_last_supper", x0, x1, z0, z1, -0.012, icon_mat("last_supper"))

# ---------------------------------------------------------------- oil lamps (one mesh, instanced)
# red glass cup sitting in a pierced brass basket, three long chains to a small
# brass cap, short chain to a hook under the cornice (batch3 IMG_7959..7961)
LAMP_Z = AP_Z0 + AP_HI * 0.36            # basket rim height
LAMP_TOP = ROW1 + 0.01
LAMP_DROP = LAMP_TOP - LAMP_Z
mb = MB()
zl = -LAMP_DROP
Zax, Xax, Yax = (0, 0, 1), (1, 0, 0), (0, 1, 0)
lathe(mb, [(0.0, zl - 0.060), (0.026, zl - 0.058), (0.029, zl + 0.062), (0.0, zl + 0.062)], (0, 0, 0), Zax, Xax, Yax, 8, mat=0)
lathe(mb, [(0.0, zl - 0.135), (0.006, zl - 0.125), (0.009, zl - 0.105), (0.030, zl - 0.090), (0.041, zl - 0.082)],
      (0, 0, 0), Zax, Xax, Yax, 8, mat=1)
lathe(mb, [(0.041, zl - 0.082), (0.043, zl - 0.006)], (0, 0, 0), Zax, Xax, Yax, 8, mat=2)
lathe(mb, [(0.043, zl - 0.006), (0.047, zl - 0.002), (0.047, zl + 0.006), (0.031, zl + 0.008)], (0, 0, 0), Zax, Xax, Yax, 8, mat=1)
cap_z = -0.07
for k in range(3):
    a = math.radians(90 + 120 * k)
    rod(mb, (0.046 * math.cos(a), 0.046 * math.sin(a), zl + 0.004), (0.012 * math.cos(a), 0.012 * math.sin(a), cap_z), 0.0022, 1)
lathe(mb, [(0.0, cap_z - 0.006), (0.016, cap_z - 0.004), (0.016, cap_z + 0.004), (0.004, cap_z + 0.012)], (0, 0, 0), Zax, Xax, Yax, 6, mat=1)
rod(mb, (0, 0, cap_z + 0.01), (0, 0, 0), 0.003, 1)
_l = mb.finish("OilLamp", [M_GLASS, M_BRASS, M_PIERCED])
LAMP_MESH = _l.data
bpy.data.objects.remove(_l)
for k, x in enumerate(ap_x):
    place("OilLamp_%02d" % (k + 1), LAMP_MESH, (x, -0.12, LAMP_TOP))

# ---------------------------------------------------------------- ostrich eggs on cords (one mesh, instanced)
EGG_DROP = ROW1 + 0.01 - (RAIL0 + 0.02)
mb = MB()
ep = [(0.0, -0.075), (0.032, -0.062), (0.052, -0.03), (0.057, 0.0), (0.050, 0.035), (0.030, 0.064), (0.0, 0.078)]
lathe(mb, ep, (0, 0, -EGG_DROP), Zax, Xax, Yax, 10, mat=0)
rod(mb, (0, 0, -EGG_DROP + 0.076), (0, 0, 0), 0.0015, 1)
_g = mb.finish("OstrichEgg", [M_IVORY, M_BRASS])
EGG_MESH = _g.data
bpy.data.objects.remove(_g)
for nm, x in (("C", 0.0), ("L", -(AP_X0 + AP_PITCH * 1.5)), ("R", AP_X0 + AP_PITCH * 1.5)):
    place("OstrichEgg_" + nm, EGG_MESH, (x, -0.13, ROW1 + 0.01))

# ---------------------------------------------------------------- crucifix group (on the cornice shelf)
# Painted cut-out boards with real thickness and a bevelled wooden edge. The
# outline (trefoil ends, arched tops) is traced from the texture itself (painted
# board on a black ground), so the cut always matches the art.
grp = bpy.data.objects.new("CrucifixGroup", None)   # stays at the asset origin; children carry their own coordinates
COL.objects.link(grp)
grp.empty_display_size = 0.2
CR_Y = D * 0.25                  # board centre plane, toward the front of the shelf
CR_HT = H * 0.30                 # crucifix height (the arch opening above is ~1.7 m)
M_CEDGE = wood("crucifix_edge", srgb(58, 30, 18), srgb(96, 52, 28), "Z", 5.0, 0.45)
M_CFRAME = wood("crucifix_side_frame", srgb(120, 80, 40), srgb(170, 124, 66), "Z", 5.0, 0.4)


def trace_rows(tex, fallback_rows, n=110):
    """([(v, u_left, u_right)] bottom -> top of the non-black part, image aspect)."""
    path = os.path.join(common.TEX, "icons", tex + ".jpg")
    if not os.path.exists(path):
        return fallback_rows, 0.0
    import numpy as np
    img = bpy.data.images.load(path, check_existing=True)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    mask = px.reshape(h, w, 4)[:, :, :3].max(axis=2) > 0.10
    rows = np.where(mask.sum(axis=1) > max(3, w * 0.01))[0]
    r0, r1 = int(rows[0]), int(rows[-1])
    out = []
    for i in range(n + 1):
        r = r0 + (r1 - r0) * i / n
        band = mask[max(r0, int(r - (r1 - r0) / n / 2)):min(r1, int(r + (r1 - r0) / n / 2)) + 1]
        cols = np.where(band.sum(axis=0) > 0)[0]
        if len(cols) == 0:
            cols = np.array([w // 2 - 1, w // 2 + 1])
        out.append((r / h, cols[0] / w, (cols[-1] + 1) / w))
    return out, w / h


def cutout(tex, rows, aspect, cx, z0, height, th, bev, edge_mat):
    """Board `height` tall standing at z0, 2*th thick, front edge bevelled by
    `bev`. Rows are in image UV space. Returns the edge/back mesh builder; the
    textured front is its own object, Icon_<tex>."""
    v0, v1 = rows[0][0], rows[-1][0]
    k = height / (v1 - v0)            # metres per unit v
    ku = k * aspect                   # metres per unit u
    umid = sum((a + b) / 2 for _, a, b in rows) / len(rows)
    yf, yb = CR_Y - th, CR_Y + th
    X = lambda u: cx + (u - umid) * ku
    Z = lambda v: z0 + (v - v0) * k
    ring = []                         # per row: z, outer l/r, inset l/r (metres) and inset uvs
    for v, l, r in rows:
        b = min(bev, (r - l) * ku * 0.3)
        ring.append((Z(v), X(l), X(r), X(l) + b, X(r) - b, l + b / ku, r - b / ku, v))
    front, board = MB(), MB()
    for (za, la, ra, lia, ria, ula, ura, va), (zb, lb, rb, lib, rib, ulb, urb, vb) in zip(ring, ring[1:]):
        front.face([(lia, yf, za), (ria, yf, za), (rib, yf, zb), (lib, yf, zb)], (0, -1, 0), 0, False,
                   [(ula, va), (ura, va), (urb, vb), (ulb, vb)])
        nl = Vector((-(zb - za), 0, lb - la))          # outward normals of the two silhouettes
        nr = Vector((zb - za, 0, -(rb - ra)))
        fwd = Vector((0, -1, 0))
        board.face([(la, yf + bev, za), (lb, yf + bev, zb), (lib, yf, zb), (lia, yf, za)], nl.normalized() + fwd, 0)
        board.face([(ra, yf + bev, za), (rb, yf + bev, zb), (rib, yf, zb), (ria, yf, za)], nr.normalized() + fwd, 0)
        board.face([(la, yf + bev, za), (lb, yf + bev, zb), (lb, yb, zb), (la, yb, za)], nl, 0)
        board.face([(ra, yf + bev, za), (rb, yf + bev, zb), (rb, yb, zb), (ra, yb, za)], nr, 0)
        board.face([(la, yb, za), (ra, yb, za), (rb, yb, zb), (lb, yb, zb)], (0, 1, 0), 0)
    for (z, l, r, li, ri, _, _, _), up in ((ring[0], -1), (ring[-1], 1)):   # bottom and top ends
        board.face([(l, yf + bev, z), (r, yf + bev, z), (r, yb, z), (l, yb, z)], (0, 0, up), 0)
        board.face([(li, yf, z), (ri, yf, z), (r, yf + bev, z), (l, yf + bev, z)], (0, -1, up), 0)
    front.finish("Icon_" + tex, [icon_mat(tex)], parent=grp)
    return board


_cross_fb = [(v, 0.5 - (0.36 if 0.66 < v < 0.76 else 0.09), 0.5 + (0.36 if 0.66 < v < 0.76 else 0.09))
             for v in [i / 24 for i in range(25)]]
_arch_fb = [(v, 0.5 - 0.5 * (1 if v < 0.7 else math.sqrt(max(0.0, 1 - ((v - 0.7) / 0.3) ** 2))) - 1e-3,
             0.5 + 0.5 * (1 if v < 0.7 else math.sqrt(max(0.0, 1 - ((v - 0.7) / 0.3) ** 2))) + 1e-3)
            for v in [i / 24 for i in range(25)]]
FOOT = 0.03                      # brass feet the boards stand in, resting on the shelf (z = H)
rows, asp = trace_rows("crucifix", _cross_fb)
mb = cutout("crucifix", rows, asp if asp else 0.8, 0.0, H + FOOT * 0.5, CR_HT, 0.016, 0.006, 0)
mb.box(-CR_HT * 0.11, CR_HT * 0.11, CR_Y - 0.05, CR_Y + 0.05, H, H + FOOT, 1)
mb.box(-CR_HT * 0.07, CR_HT * 0.07, CR_Y - 0.032, CR_Y + 0.032, H + FOOT, H + FOOT * 1.8, 1)
mb.finish("CrucifixBoard", [M_CEDGE, M_BRASS], parent=grp)
FL_H, FL_X = CR_HT * 0.36, CR_HT * 0.47
for sgn, tex in ((-1, "crucifix_mary"), (1, "crucifix_john")):
    rows, asp = trace_rows(tex, _arch_fb)
    mb = cutout(tex, rows, asp if asp else 0.65, sgn * FL_X, H + FOOT * 0.5, FL_H, 0.012, 0.009, 0)
    mb.box(sgn * FL_X - 0.07, sgn * FL_X + 0.07, CR_Y - 0.04, CR_Y + 0.04, H, H + FOOT, 1)
    mb.finish("CrucifixSideBoard_" + ("L" if sgn < 0 else "R"), [M_CFRAME, M_BRASS], parent=grp)

# ---------------------------------------------------------------- bake every transform into the mesh data
# The room assembly moves objects by their stored matrices, so nothing in this
# asset may rely on an object location or a parent offset: repeats are built
# from one mesh, then written out in asset coordinates and joined per kind.
for ob in list(COL.objects):
    if ob.type == "MESH" and (ob.location.length > 1e-9 or ob.data.users > 1):
        me = ob.data.copy()
        me.transform(Matrix.Translation(ob.location))
        ob.data = me
        ob.location = (0, 0, 0)
for prefix, name in (("ApostleArch_", "ApostleArches"), ("CarvedPanel_", "CarvedPanels"),
                     ("OilLamp_", "OilLamps"), ("OstrichEgg_", "OstrichEggs"), ("TriptychColumn_", "TriptychColumns")):
    obs = [o for o in COL.objects if o.name.startswith(prefix)]
    if not obs:
        continue
    bm = bmesh.new()
    for o in obs:
        bm.from_mesh(o.data)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for m in obs[0].data.materials:
        me.materials.append(m)
    for o in obs:
        bpy.data.objects.remove(o)
    place(name, me)

# ---------------------------------------------------------------- checks, save
bpy.context.view_layer.update()
total = 0
uniq = {}
bad = []
for ob in COL.objects:
    if ob.type != "MESH":
        continue
    me = ob.data
    me.calc_loop_triangles()
    t = len(me.loop_triangles)
    total += t
    uniq[me.name] = t
    if ob.name.startswith("Icon_") and any(p.normal.y > 0.01 for p in me.polygons):
        bad.append(ob.name)
    if ob.matrix_basis != Matrix.Identity(4):
        bad.append(ob.name + " (transform)")
print("ICONOSTASIS objects=%d tris_total=%d" % (len(COL.objects), total))
print("ICONOSTASIS problems (back-facing icons / non-identity transforms):", sorted(set(bad))[:10])
common.save("iconostasis")

# ---------------------------------------------------------------- previews (not saved in the asset)
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
FAST = "fast" in argv
argv = [a for a in argv if a != "fast"]
if "none" not in argv:
    views = argv or ["overall", "left", "right", "door", "top", "centre"]
    sc = bpy.context.scene
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.05, 0.045, 0.04, 1)
    sc.world = world

    def pv_plane(name, pts, mat):
        me = bpy.data.meshes.new(name)
        me.from_pydata(pts, [], [(0, 1, 2, 3)])
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        sc.collection.objects.link(ob)

    pv_plane("pv_floor", [(-9, -16, 0), (9, -16, 0), (9, 1, 0), (-9, 1, 0)],
             common.flat_material("pv_carpet", srgb(150, 20, 28), 0.95))
    pv_plane("pv_wall", [(-9, D + 0.4, 0), (9, D + 0.4, 0), (9, D + 0.4, 9), (-9, D + 0.4, 9)],
             common.flat_material("pv_wall", srgb(40, 28, 20), 0.8))
    for i, (x, y, z, e) in enumerate(((-W * 0.35, -5.0, H + 0.6, 420), (W * 0.35, -5.0, H + 0.6, 420), (0, -7.0, 2.6, 260),
                                      (-W * 0.28, -3.0, 0.8, 40), (W * 0.28, -3.0, 0.8, 40))):
        ld = bpy.data.lights.new("pv_light%d" % i, "AREA")
        ld.energy = e
        ld.size = 4.0
        ld.color = (1.0, 0.86, 0.68)
        lo = bpy.data.objects.new("pv_light%d" % i, ld)
        sc.collection.objects.link(lo)
        lo.location = (x, y, z)
        lo.rotation_euler = (Vector((x * 0.6, 0, H * 0.55)) - Vector((x, y, z))).to_track_quat("-Z", "Y").to_euler()
    try:
        sc.view_settings.view_transform = "Filmic"
    except TypeError:
        pass
    V = {
        "overall": ((0, -W * 1.12, H * 0.62), (0, 0, H * 0.66), 35, (960, 520)),
        "left": ((-W * 0.33, -5.2, 1.7), (-W * 0.33, 0, 1.75), 35, (960, 720)),
        "right": ((W * 0.33, -5.2, 1.7), (W * 0.33, 0, 1.75), 35, (960, 720)),
        "door": ((-SX + 0.2, -3.6, 1.3), (-SX + 0.2, 0, 1.4), 35, (960, 720)),
        "top": ((-W * 0.2, -3.6, H * 0.74), (-W * 0.2, 0, H * 0.86), 40, (960, 600)),
        "centre": ((0, -5.5, 1.6), (0, 0, H * 0.72), 26, (720, 960)),
        "marq": ((-TRIP_X, -1.5, 2.0), (-TRIP_X + 0.1, 0, 2.1), 35, (960, 720)),
        "cruc": ((0.75, -2.4, H - 0.5), (0.0, CR_Y, H + CR_HT * 0.5), 35, (960, 720)),
        "lamp": ((AP_X0 + AP_PITCH * 0.3, -1.5, ROW0 + 0.2), (AP_X0 + AP_PITCH * 0.3, 0, ROW0 + 0.45), 35, (960, 720)),
        "supper": ((0.3, -2.4, ROW0 - 0.5), (0.0, 0, ROW0 + 0.5), 35, (960, 720)),
    }
    for v in views:
        loc, look, lens, size = V[v]
        if FAST:
            size = (640, int(640 * size[1] / size[0]))
        common.render_preview("iconostasis_" + v + ("_fast" if FAST else ""), loc, look, lens=lens, size=size,
                              samples=32 if FAST else 48)
