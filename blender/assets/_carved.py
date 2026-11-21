"""Shared geometry + material helpers for the carved-wood assets
(throne.py, shrine.py, icon_stand.py). Not an asset itself.

Every generator works in a local right-handed (u, v, w) frame and takes an
`xf` callable that maps a local Vector to world space, so the same module can
be laid on a flat panel, wrapped round an arch or put on a hexagon side.
Faces are wound so the normal is +w / outward (three.js culls back faces).
"""
import math
import os
import bpy
import bmesh
from mathutils import Vector

import common

PI = math.pi
X, Y, Z = Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))


# ---------------------------------------------------------------- builder
class Builder:
    def __init__(self):
        self.bm = bmesh.new()
        self.mat = 0

    def v(self, co):
        return self.bm.verts.new(co)

    def f(self, vs):
        try:
            face = self.bm.faces.new(vs)
        except ValueError:
            return None
        face.material_index = self.mat
        return face

    def tris(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)


def ident(p):
    return Vector(p)


def plane(o, u, v):
    """Local (u, v, w) -> world, w = u x v (the outward normal)."""
    o, u, v = Vector(o), Vector(u).normalized(), Vector(v).normalized()
    w = u.cross(v)
    return lambda p: o + u * p[0] + v * p[1] + w * p[2]


def front(x, z, y):
    """Panel facing -Y with its lower-left corner at (x, y, z)."""
    return plane((x, y, z), X, Z)


def side(xs, y, z, sign):
    """Panel facing +X (sign=1) or -X (sign=-1); u runs so that u x Z = normal."""
    return plane((xs, y, z), Y * sign, Z)


def arc(c, R, a0=PI, plane_y=None):
    """Wrap a strip over an arch in the XZ plane facing -Y. u = arc length from
    angle a0 going clockwise as seen from the front (left -> over the top ->
    right), v = radial offset from R, w = toward -Y."""
    c = Vector(c)

    def fn(p):
        a = a0 - p[0] / R
        r = R + p[1]
        return Vector((c.x + r * math.cos(a), c.y - p[2], c.z + r * math.sin(a)))
    return fn


def chain(outer, inner):
    return lambda p: outer(inner(p))


# ---------------------------------------------------------------- solids
def box(B, lo, hi, xf=ident, skip=""):
    lo, hi = Vector(lo), Vector(hi)
    c = {}
    for i in (0, 1):
        for j in (0, 1):
            for k in (0, 1):
                c[i, j, k] = B.v(xf(Vector((hi.x if i else lo.x, hi.y if j else lo.y,
                                            hi.z if k else lo.z))))
    faces = {
        "-x": [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)],
        "+x": [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)],
        "-y": [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
        "+y": [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)],
        "-z": [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)],
        "+z": [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)],
    }
    for k, idx in faces.items():
        if k not in skip:
            B.f([c[i] for i in idx])


def cbox(B, c, s, xf=ident, skip=""):
    c, s = Vector(c), Vector(s) / 2
    box(B, c - s, c + s, xf, skip)


def lathe(B, prof, segs, xf=ident, a0=0.0, a1=2 * PI):
    """Turned shape round local w. prof = [(r, w), ...] bottom to top."""
    full = abs(a1 - a0 - 2 * PI) < 1e-6
    n = segs if full else segs + 1
    rings = []
    for r, h in prof:
        if r < 1e-6:
            rings.append([B.v(xf(Vector((0, 0, h))))])
        else:
            rings.append([B.v(xf(Vector((r * math.cos(a0 + (a1 - a0) * k / segs),
                                         r * math.sin(a0 + (a1 - a0) * k / segs), h))))
                          for k in range(n)])
    for i in range(len(rings) - 1):
        ra, rb = rings[i], rings[i + 1]
        for k in range(segs):
            k2 = (k + 1) % n
            if len(ra) == 1 and len(rb) == 1:
                continue
            if len(ra) == 1:
                B.f([ra[0], rb[k2], rb[k]])
            elif len(rb) == 1:
                B.f([ra[k], ra[k2], rb[0]])
            else:
                B.f([ra[k], ra[k2], rb[k2], rb[k]])


def twist(B, R, h, xf=ident, lobes=5, ppl=4, turns_per_m=3.5, depth=0.22,
          hand=1, ring_twist=0.5):
    """Rope / barley-twist shaft from w=0 to w=h round local w."""
    n = lobes * ppl
    total = 2 * PI * turns_per_m * h
    nr = max(2, int(math.ceil(total / ring_twist)))
    rings = []
    for j in range(nr + 1):
        t = j / nr
        ring = []
        for k in range(n):
            ph = (k % ppl) / ppl
            r = R * (1 - depth + depth * abs(math.sin(PI * ph)) ** 0.7)
            a = 2 * PI * k / n + hand * total * t
            ring.append(B.v(xf(Vector((r * math.cos(a), r * math.sin(a), h * t)))))
        rings.append(ring)
    for j in range(nr):
        for k in range(n):
            k2 = (k + 1) % n
            B.f([rings[j][k], rings[j][k2], rings[j + 1][k2], rings[j + 1][k]])


def prism(B, poly, t, xf=ident, back=True, cap=True):
    """Convex CCW polygon in (u, v) extruded from w=0 to w=t."""
    fr = [B.v(xf(Vector((p[0], p[1], t)))) for p in poly]
    bk = [B.v(xf(Vector((p[0], p[1], 0)))) for p in poly]
    n = len(poly)
    if cap:
        B.f(fr)
    if back:
        B.f(list(reversed(bk)))
    for k in range(n):
        k2 = (k + 1) % n
        B.f([fr[k], bk[k], bk[k2], fr[k2]])


def loft(B, rings, close=True):
    """rings: lists of world points, each CCW seen from the outside-top;
    consecutive rings are joined with outward-facing quads."""
    vr = [[B.v(p) for p in r] for r in rings]
    n = len(vr[0])
    for i in range(len(vr) - 1):
        for k in range(n if close else n - 1):
            k2 = (k + 1) % n
            B.f([vr[i][k], vr[i][k2], vr[i + 1][k2], vr[i + 1][k]])
    return vr


def ngon(R, n, a0=0.0, c=(0, 0)):
    return [(c[0] + R * math.cos(a0 + 2 * PI * k / n), c[1] + R * math.sin(a0 + 2 * PI * k / n))
            for k in range(n)]


def sweep(B, pts, nrm, dep, prof, closed=False, caps=True):
    """Sweep a closed 2D profile [(out, depth), ...] along a path.
    pts = path points, nrm = per-point outward vectors (mitre-scaled),
    dep = depth direction (one Vector or one per point)."""
    n, m = len(pts), len(prof)
    rings = []
    for i in range(n):
        d = dep[i] if isinstance(dep, (list, tuple)) else dep
        rings.append([Vector(pts[i]) + Vector(nrm[i]) * o + Vector(d) * dd for o, dd in prof])
    # orientation test on the first segment
    cen = sum(rings[0], Vector()) / m
    a, b, c2 = rings[0][0], rings[0][1], rings[1][1]
    nor = (b - a).cross(c2 - b)
    flip = nor.dot((a + b) / 2 - cen) < 0
    vr = [[B.v(p) for p in r] for r in rings]
    for i in range(n if closed else n - 1):
        i2 = (i + 1) % n
        for k in range(m):
            k2 = (k + 1) % m
            q = [vr[i][k], vr[i][k2], vr[i2][k2], vr[i2][k]]
            B.f(q[::-1] if flip else q)
    if caps and not closed:
        # start cap faces back along the path, end cap forward
        t0 = Vector(pts[1]) - Vector(pts[0])
        for ring, tdir in ((vr[0], -t0), (vr[-1], Vector(pts[-1]) - Vector(pts[-2]))):
            cs = [v.co for v in ring]
            nn = (cs[1] - cs[0]).cross(cs[2] - cs[1])
            B.f(ring if nn.dot(tdir) > 0 else ring[::-1])


def arch_path(cx, y, z0, w, h, segs=16, closed=False):
    """Round-headed opening: width w, total height h, bottom at z0, in the XZ
    plane at depth y. Returns (pts, normals) from bottom-left over the top to
    bottom-right. closed=True mitres the two bottom corners for a full frame."""
    r = w / 2
    zs = z0 + h - r
    pts, nrm = [], []
    s = math.sqrt(2)
    pts.append(Vector((cx - r, y, z0)))
    nrm.append(Vector((-1, 0, -1)) if closed else Vector((-1, 0, 0)))
    for k in range(segs + 1):
        a = PI - PI * k / segs
        pts.append(Vector((cx + r * math.cos(a), y, zs + r * math.sin(a))))
        nrm.append(Vector((math.cos(a), 0, math.sin(a))))
    pts.append(Vector((cx + r, y, z0)))
    nrm.append(Vector((1, 0, -1)) if closed else Vector((1, 0, 0)))
    return pts, nrm


def arch_poly(w, h, segs=16):
    """CCW outline (u, v) of a round-headed panel, lower-left at the origin."""
    r = w / 2
    pts = [(0, 0), (w, 0)]
    for k in range(segs + 1):
        a = PI * k / segs
        pts.append((r + r * math.cos(a), h - r + r * math.sin(a)))
    return pts


# ---------------------------------------------------------------- carving
def pierced(B, xf, nu, nv, cw, ch, t, hole=0.78, N=16, lobe=0.38, rot=0.0, alt=True, walls=True):
    """Fretwork plate: nu x nv cells, each a quatrefoil cut-out with real
    thickness (front face + hole walls). Local origin = lower-left corner."""
    for i in range(nu):
        for j in range(nv):
            cx, cy = (i + 0.5) * cw, (j + 0.5) * ch
            ph = rot + (PI / 4 if (alt and (i + j) % 2) else 0.0)
            of, inf, inb = [], [], []
            for k in range(N):
                a = 2 * PI * k / N
                c, s = math.cos(a), math.sin(a)
                sc = 1 / max(abs(c), abs(s))
                of.append(B.v(xf(Vector((cx + c * sc * cw / 2, cy + s * sc * ch / 2, t)))))
                r = hole * (1 - lobe + lobe * abs(math.cos(2 * (a - ph))))
                p = (cx + c * r * cw / 2, cy + s * r * ch / 2)
                inf.append(B.v(xf(Vector((p[0], p[1], t)))))
                inb.append(B.v(xf(Vector((p[0], p[1], 0)))))
            for k in range(N):
                k2 = (k + 1) % N
                B.f([of[k], of[k2], inf[k2], inf[k]])
                if walls:
                    B.f([inf[k], inf[k2], inb[k2], inb[k]])


def diamonds(B, xf, nu, nv, cw, ch, h, fill=0.92, top=0.3, boss=0.0):
    """Chip-carved relief: raised lozenge per cell (the grooves between them
    read as an X lattice). boss>0 adds a small pyramid flower centre."""
    for i in range(nu):
        for j in range(nv):
            cx, cy = (i + 0.5) * cw, (j + 0.5) * ch
            d = [(-1, 0), (0, -1), (1, 0), (0, 1)]
            b = [B.v(xf(Vector((cx + dx * cw / 2 * fill, cy + dy * ch / 2 * fill, 0)))) for dx, dy in d]
            tp = [B.v(xf(Vector((cx + dx * cw / 2 * top, cy + dy * ch / 2 * top, h)))) for dx, dy in d]
            for k in range(4):
                k2 = (k + 1) % 4
                B.f([b[k], b[k2], tp[k2], tp[k]])
            if boss:
                ap = B.v(xf(Vector((cx, cy, h + boss))))
                for k in range(4):
                    B.f([tp[k], tp[(k + 1) % 4], ap])
            else:
                B.f(tp)


def rosette(B, xf, r, h, petals=6, ring=True, segs=14):
    """Carved flower medallion centred on the local origin, facing +w."""
    for k in range(petals):
        a = 2 * PI * k / petals
        ra = Vector((math.cos(a), math.sin(a), 0))
        ta = Vector((-math.sin(a), math.cos(a), 0))
        wd = r * 0.5 * math.tan(PI / petals) * 0.85
        P = [ra * r * 0.12, ra * r * 0.5 - ta * wd, ra * r * 0.84, ra * r * 0.5 + ta * wd]
        vs = [B.v(xf(p)) for p in P]
        ap = B.v(xf(ra * r * 0.5 + Vector((0, 0, h))))
        for q in range(4):
            B.f([vs[q], vs[(q + 1) % 4], ap])
    lathe(B, [(r * 0.16, 0), (r * 0.12, h * 0.9), (0, h * 1.1)], 6, xf)
    if ring:
        lathe(B, [(r * 1.04, 0), (r * 1.0, h * 0.7), (r * 0.9, h * 0.7), (r * 0.86, 0)], segs, xf)


def cross_medallion(B, xf, r, h, segs=12):
    """Round disc with a raised equal-armed cross (shrine capitals)."""
    lathe(B, [(r, 0), (r, h * 0.5), (r * 0.86, h * 0.5), (r * 0.8, h * 0.25), (0, h * 0.25)], segs, xf)
    a, b = r * 0.66, r * 0.17
    box(B, (-a, -b, 0), (a, b, h * 0.7), xf, skip="-z")
    box(B, (-b, -a, 0), (b, a, h * 0.78), xf, skip="-z")  # taller: no coplanar overlap


def tabs(B, xf, n, pitch, r, t, drop=None, seg=4, back=True):
    """Row of hanging half-round scallops below v=0 (cornice drops)."""
    drop = r if drop is None else drop
    for i in range(n):
        c = (i + 0.5) * pitch
        poly = [(c - r + r * (1 - math.cos(PI * k / seg)), -drop * math.sin(PI * k / seg))
                for k in range(seg + 1)]
        prism(B, poly, t, xf, back=back)


def merlons(B, xf, n, pitch, wdt, hgt, t, back=True):
    """Row of pointed cresting teeth standing on v=0."""
    for i in range(n):
        c = (i + 0.5) * pitch
        poly = [(c - wdt / 2, 0), (c + wdt / 2, 0), (c + wdt / 2, hgt * 0.45),
                (c, hgt), (c - wdt / 2, hgt * 0.45)]
        prism(B, poly, t, xf, back=back)


def ball_finial(B, xf, r, segs=12, neck=True):
    """Turned ball on a waisted neck, base at w=0. Returns total height."""
    prof = []
    a_start = -PI / 2
    cz = r
    if neck:
        prof = [(r * 0.95, 0), (r * 1.0, r * 0.12), (r * 0.62, r * 0.3), (r * 0.42, r * 0.55),
                (r * 0.66, r * 0.7), (r * 0.66, r * 0.78), (r * 0.42, r * 0.86)]
        a_start = -math.acos(0.42)
        cz = r * 0.86 - r * math.sin(a_start)
    else:
        prof = [(0.0, 0.0)]
    n = 7
    for i in range(1, n + 1):
        a = a_start + (PI / 2 - a_start) * i / n
        prof.append((r * math.cos(a) if i < n else 0.0, cz + r * math.sin(a)))
    lathe(B, prof, segs, xf)
    return cz + r


def urn(B, xf, r, h, segs=6):
    lathe(B, [(r * 0.55, 0), (r * 0.7, h * 0.08), (r * 0.35, h * 0.2), (r * 0.8, h * 0.42),
              (r, h * 0.6), (r * 0.8, h * 0.8), (r * 0.3, h * 0.92), (0, h)], segs, xf)


def cross(B, xf, h, arm, t, bar, bud=True):
    """Upright cross in the local (u, v) plane, foot at the origin, centred on
    w=0, with small budded (trefoil-ish) ends."""
    box(B, (-bar / 2, 0, -t / 2), (bar / 2, h, t / 2), xf)
    zc = h * 0.68
    box(B, (-arm / 2, zc - bar / 2, -t * 0.56), (arm / 2, zc + bar / 2, t * 0.56), xf)  # proud: no coplanar overlap
    if bud:
        for cx, cy in ((0, h), (-arm / 2, zc), (arm / 2, zc)):
            cbox(B, (cx, cy, 0), (bar * 1.9, bar * 1.9, t * 1.25), xf)


# ---------------------------------------------------------------- materials
def wood(name, dark, light, rough=0.32, coat=0.35, grain=(14.0, 14.0, 1.2), bump=0.06):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = common.bsdf(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = grain
    no = nt.nodes.new("ShaderNodeTexNoise")
    no.inputs["Scale"].default_value = 2.2
    no.inputs["Detail"].default_value = 8.0
    no.inputs["Roughness"].default_value = 0.62
    no.inputs["Distortion"].default_value = 1.2
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    e = ramp.color_ramp.elements
    e[0].position, e[0].color = 0.3, (*dark, 1)
    e[1].position, e[1].color = 0.72, (*light, 1)
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    bp.inputs["Distance"].default_value = 0.002
    L = nt.links.new
    L(tc.outputs["Object"], mp.inputs["Vector"])
    L(mp.outputs["Vector"], no.inputs["Vector"])
    L(no.outputs[0], ramp.inputs["Fac"])
    L(ramp.outputs["Color"], b.inputs["Base Color"])
    L(no.outputs[0], bp.inputs["Height"])
    L(bp.outputs["Normal"], b.inputs["Normal"])
    b.inputs["Roughness"].default_value = rough
    b.inputs["Coat Weight"].default_value = coat
    b.inputs["Coat Roughness"].default_value = 0.12
    return m


def velvet(name, rgb):
    m = common.flat_material(name, rgb, rough=0.95)
    b = common.bsdf(m)
    b.inputs["Sheen Weight"].default_value = 1.0
    b.inputs["Sheen Roughness"].default_value = 0.35
    b.inputs["Sheen Tint"].default_value = (1.0, 0.45, 0.5, 1.0)
    return m


# ---------------------------------------------------------------- finishing
def finish(B, name, coll, mats, sharp=0.62, uv=True):
    me = bpy.data.meshes.new(name)
    B.bm.normal_update()
    B.bm.to_mesh(me)
    B.bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    for m in mats:
        me.materials.append(m)
    me.shade_smooth()
    me.set_sharp_from_angle(angle=sharp)
    if uv:
        bpy.context.view_layer.objects.active = ob
        ob.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.smart_project(angle_limit=1.15, island_margin=0.002)
        bpy.ops.object.mode_set(mode="OBJECT")
        ob.select_set(False)
    return ob


def icon_plane(name, coll, poly, xf, mat):
    """Flat icon panel from a CCW (u, v) outline, UVs = bounding box 0..1."""
    bm = bmesh.new()
    us = [p[0] for p in poly]
    vs = [p[1] for p in poly]
    u0, v0, du, dv = min(us), min(vs), max(us) - min(us), max(vs) - min(vs)
    f = bm.faces.new([bm.verts.new(xf(Vector((p[0], p[1], 0)))) for p in poly])
    lay = bm.loops.layers.uv.new("UVMap")
    for lp, p in zip(f.loops, poly):
        lp[lay].uv = ((p[0] - u0) / du, (p[1] - v0) / dv)
    bmesh.ops.triangulate(bm, faces=[f])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    me.materials.append(mat)
    return ob


def tri_count(coll):
    n = 0
    for ob in coll.objects:
        if ob.type == "MESH":
            ob.data.calc_loop_triangles()
            n += len(ob.data.loop_triangles)
    return n


def shift(coll, dy):
    """Move all geometry by dy in Y (bake into mesh data, origins stay at 0)."""
    for ob in coll.objects:
        if ob.type == "MESH":
            for v in ob.data.vertices:
                v.co.y += dy
            ob.data.update()


def studio(wall_y, floor_z=0.0, floor=True, key=(-2.5, -4.0, 3.2), fill=(3.0, -3.0, 1.5),
           key_w=900, fill_w=250, size=3.0):
    """White wall + floor + two area lights for previews (added AFTER save)."""
    from mathutils import Vector as V
    sc = bpy.context.scene.collection
    white = common.flat_material("PreviewWall", (0.82, 0.8, 0.76), 0.7)
    red = common.flat_material("PreviewFloor", (0.35, 0.03, 0.04), 0.9)
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(p) for p in
                      ((-8, wall_y, floor_z - 3), (8, wall_y, floor_z - 3), (8, wall_y, 8), (-8, wall_y, 8))])
    me = bpy.data.meshes.new("PreviewWall")
    bm.to_mesh(me)
    bm.free()
    me.materials.append(white)
    sc.objects.link(bpy.data.objects.new("PreviewWall", me))
    if floor:
        bm = bmesh.new()
        bm.faces.new([bm.verts.new(p) for p in
                      ((-8, wall_y, floor_z), (-8, -12, floor_z), (8, -12, floor_z), (8, wall_y, floor_z))])
        me = bpy.data.meshes.new("PreviewFloor")
        bm.to_mesh(me)
        bm.free()
        me.materials.append(red)
        sc.objects.link(bpy.data.objects.new("PreviewFloor", me))
    for nm, loc, w in (("Key", key, key_w), ("Fill", fill, fill_w)):
        ld = bpy.data.lights.new(nm, "AREA")
        ld.energy = w
        ld.size = size
        ld.color = (1.0, 0.93, 0.82)
        lo = bpy.data.objects.new(nm, ld)
        lo.location = loc
        d = V((0, wall_y - 0.3, floor_z + 1.4)) - V(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        sc.objects.link(lo)
    w = bpy.data.worlds.new("PreviewWorld")
    w.use_nodes = True
    bg = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.9, 0.88, 0.85, 1)
    bg.inputs[1].default_value = 0.35
    bpy.context.scene.world = w
    try:
        bpy.context.scene.view_settings.view_transform = "Standard"
    except TypeError:
        pass


def backface_check(coll):
    """Swap every material for one that shows back faces in red (debug)."""
    m = bpy.data.materials.new("BackfaceCheck")
    m.use_nodes = True
    nt = m.node_tree
    b = common.bsdf(m)
    geo = nt.nodes.new("ShaderNodeNewGeometry")
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.inputs[6].default_value = (0.25, 0.25, 0.25, 1)
    mix.inputs[7].default_value = (1, 0, 0, 1)
    nt.links.new(geo.outputs["Backfacing"], mix.inputs[0])
    nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    for ob in coll.objects:
        if ob.type == "MESH":
            for i in range(len(ob.data.materials)):
                ob.data.materials[i] = m
