"""Shared helpers for the crystal chandelier assets (not an asset by itself).

Every crystal is one point of a vertex-only mesh. A geometry-nodes modifier
instances a tiny faceted prototype on each point. Point attributes:

  rot      FLOAT_VECTOR  euler rotation of the crystal
  scl      FLOAT_VECTOR  scale of the crystal
  kind     INT           which prototype (0 strand bead, 1 lens, 2 drop, 3 small band lens)
  sparkle  FLOAT         random 0..1 per crystal (the twinkle seed)

`sparkle` travels to the instances (read in the shader as an Instancer
attribute) and, in the realised `_export` variant, to every vertex of the
crystal, where it is also written into the colour attribute `Col`
(R = sparkle, G = second random phase, B = 1) and the float `_sparkle`.
"""
import math
import os
import random
import bpy
import bmesh
from mathutils import Vector, Matrix

WARM = (1.0, 0.90, 0.76)          # bulbs / glow: warm white as the camera sees it
LIGHT_RGB = (1.0, 0.89, 0.76)     # the placed lights, "about 4000 K" look


# ---------------------------------------------------------------- materials
def crystal_material():
    """Cheap glass look with no refraction, so it survives baking / GLB:
    - facets that face the viewer glow white-hot (as if the lamp shone through),
      grazing facets fall back to a darker, cooler mirror term;
    - a small share of crystals (sparkle ** 24) burn much brighter;
    - tiny spectral glints looked up by the reflection vector;
    - alpha a little under 1 so the far side shows faintly through the near side
      (set the "crystal alpha" nodes to 1 if blending is a problem on the web).
    """
    name = "ChandelierCrystal"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    N, K = nt.nodes, nt.links
    b = next(n for n in N if n.type == "BSDF_PRINCIPLED")
    # dark dielectric body: the look is carried by emission, so the strong lamp
    # inside the chandelier cannot blow the crystals out to flat white; the 4 %
    # mirror term still catches bulbs and windows as small sharp highlights
    b.inputs["Base Color"].default_value = (0.03, 0.035, 0.04, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.05

    def math(op, a=None, bb=None, c=None, label=None):
        n = N.new("ShaderNodeMath")
        n.operation = op
        for i, v in enumerate((a, bb, c)):
            if v is None:
                continue
            if isinstance(v, (int, float)):
                n.inputs[i].default_value = v
            else:
                K.new(v, n.inputs[i])
        if label:
            n.label = label
        return n.outputs[0]

    a_i = N.new("ShaderNodeAttribute")
    a_i.attribute_type = "INSTANCER"
    a_i.attribute_name = "sparkle"
    a_g = N.new("ShaderNodeAttribute")
    a_g.attribute_type = "GEOMETRY"
    a_g.attribute_name = "sparkle"
    spk = math("MAXIMUM", a_i.outputs["Fac"], a_g.outputs["Fac"])

    lw = N.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.5
    facing = math("SUBTRACT", 1.0, lw.outputs["Facing"])
    core = math("POWER", facing, 6.0, label="core falloff")
    e_face = math("MULTIPLY_ADD", core, 4.0, 0.05, label="facet glow gain / edge glow")

    hot = math("POWER", spk, 40.0, label="share of sparkling crystals")
    e_hot = math("MULTIPLY", hot, 6.0, label="sparkle gain")

    tc = N.new("ShaderNodeTexCoord")
    sv = N.new("ShaderNodeCombineXYZ")
    for i in range(3):
        K.new(spk, sv.inputs[i])
    sc = N.new("ShaderNodeVectorMath")
    sc.operation = "SCALE"
    K.new(sv.outputs[0], sc.inputs[0])
    sc.inputs["Scale"].default_value = 37.0
    off = N.new("ShaderNodeVectorMath")
    off.operation = "ADD"
    K.new(tc.outputs["Reflection"], off.inputs[0])
    K.new(sc.outputs[0], off.inputs[1])
    noise = N.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 7.0
    noise.inputs["Detail"].default_value = 0.0
    K.new(off.outputs[0], noise.inputs["Vector"])
    mr = N.new("ShaderNodeMapRange")
    mr.interpolation_type = "SMOOTHSTEP"
    mr.inputs["From Min"].default_value = 0.68
    mr.inputs["From Max"].default_value = 0.80
    mr.label = "glint mask"
    K.new(noise.outputs["Fac"], mr.inputs["Value"])
    glint = mr.outputs["Result"]
    e_gl = math("MULTIPLY", glint, 6.0, label="glint gain")

    # overall level: set so the crystals read white-hot at the exposure where
    # the lamps light the room (about -2.5 EV with the layout's light powers)
    tot = math("MULTIPLY", math("ADD", math("ADD", e_face, e_hot), e_gl), 6.0, label="crystal brightness")
    K.new(tot, b.inputs["Emission Strength"])

    # colour: cool glassy edge -> warm-white core -> spectral in the glints
    c1 = N.new("ShaderNodeMixRGB")
    c1.inputs[1].default_value = (0.62, 0.78, 1.0, 1)
    c1.inputs[2].default_value = (1.0, 0.95, 0.86, 1)
    K.new(core, c1.inputs[0])
    hsv = N.new("ShaderNodeHueSaturation")
    hsv.inputs["Saturation"].default_value = 2.2
    K.new(noise.outputs["Color"], hsv.inputs["Color"])
    c2 = N.new("ShaderNodeMixRGB")
    K.new(math("MULTIPLY", glint, 0.6), c2.inputs[0])
    K.new(c1.outputs[0], c2.inputs[1])
    K.new(hsv.outputs[0], c2.inputs[2])
    K.new(c2.outputs[0], b.inputs["Emission Color"])

    alpha = math("MULTIPLY_ADD", core, 0.17, 0.80, label="crystal alpha: core gain / edge")
    K.new(math("MINIMUM", alpha, 1.0), b.inputs["Alpha"])
    if hasattr(m, "surface_render_method"):
        m.surface_render_method = "BLENDED"
    return m


def band_material():
    """The rings are wrapped in a mesh of tiny beads: matt, bright, silvery."""
    m = bpy.data.materials.get("ChandelierBeadBand")
    if m:
        return m
    m = bpy.data.materials.new("ChandelierBeadBand")
    m.use_nodes = True
    nt = m.node_tree
    b = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.42, 0.42, 0.44, 1)
    b.inputs["Metallic"].default_value = 0.0
    b.inputs["Roughness"].default_value = 0.5
    b.inputs["Emission Color"].default_value = (1.0, 0.96, 0.9, 1)
    b.inputs["Emission Strength"].default_value = 1.2
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 160.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.6
    bump.inputs["Distance"].default_value = 0.004
    nt.links.new(vor.outputs["Distance"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return m


def chrome_material():
    m = bpy.data.materials.get("ChandelierChrome")
    if m:
        return m
    m = bpy.data.materials.new("ChandelierChrome")
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (0.80, 0.80, 0.82, 1)
    b.inputs["Metallic"].default_value = 1.0
    b.inputs["Roughness"].default_value = 0.18
    return m


def bulb_material():
    m = bpy.data.materials.get("ChandelierBulb")
    if m:
        return m
    m = bpy.data.materials.new("ChandelierBulb")
    m.use_nodes = True
    b = next(n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    b.inputs["Base Color"].default_value = (1, 0.9, 0.75, 1)
    b.inputs["Emission Color"].default_value = (*WARM, 1)
    b.inputs["Emission Strength"].default_value = 45.0
    return m


# ---------------------------------------------------------------- prototypes
def _mesh_from(name, verts, faces, mat):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.materials.append(mat)
    me.update()
    ob = bpy.data.objects.new(name, me)   # deliberately not linked anywhere
    return ob


def proto_bead(name, n, mat):
    """Bipyramid, equator radius .5, apexes at z = +-.5. 2n tris."""
    v = [(0.5 * math.cos(2 * math.pi * i / n), 0.5 * math.sin(2 * math.pi * i / n), 0) for i in range(n)]
    v += [(0, 0, 0.5), (0, 0, -0.5)]
    f = []
    for i in range(n):
        j = (i + 1) % n
        f.append((i, j, n))
        f.append((j, i, n + 1))
    return _mesh_from(name, v, f, mat)


def proto_lens(name, n, mat):
    """Faceted octagon/hexagon lens: rim in XY (radius .5), apexes z = +-.5."""
    off = math.pi / n
    v = [(0.5 * math.cos(off + 2 * math.pi * i / n), 0.5 * math.sin(off + 2 * math.pi * i / n), 0) for i in range(n)]
    v += [(0, 0, 0.5), (0, 0, -0.5)]
    f = []
    for i in range(n):
        j = (i + 1) % n
        f.append((i, j, n))
        f.append((j, i, n + 1))
    return _mesh_from(name, v, f, mat)


def proto_ico(name, mat):
    """Icosahedron, diameter 1: the round faceted ball. 20 tris."""
    t = (1 + 5 ** 0.5) / 2
    v = [(-1, t, 0), (1, t, 0), (-1, -t, 0), (1, -t, 0), (0, -1, t), (0, 1, t), (0, -1, -t), (0, 1, -t),
         (t, 0, -1), (t, 0, 1), (-t, 0, -1), (-t, 0, 1)]
    k = 0.5 / math.sqrt(1 + t * t)
    v = [(a * k, b * k, c * k) for a, b, c in v]
    f = [(0, 11, 5), (0, 5, 1), (0, 1, 7), (0, 7, 10), (0, 10, 11), (1, 5, 9), (5, 11, 4), (11, 10, 2),
         (10, 7, 6), (7, 1, 8), (3, 9, 4), (3, 4, 2), (3, 2, 6), (3, 6, 8), (3, 8, 9), (4, 9, 5), (2, 4, 11),
         (6, 2, 10), (8, 6, 7), (9, 8, 1)]
    return _mesh_from(name, v, f, mat)


def proto_drop(name, mat):
    """Pendant drop: 4-sided, widest low down, point up. 8 tris."""
    n = 4
    v = [(0.5 * math.cos(2 * math.pi * i / n), 0.5 * math.sin(2 * math.pi * i / n), -0.2) for i in range(n)]
    v += [(0, 0, 0.5), (0, 0, -0.5)]
    f = []
    for i in range(n):
        j = (i + 1) % n
        f.append((i, j, n))
        f.append((j, i, n + 1))
    return _mesh_from(name, v, f, mat)


# ---------------------------------------------------------------- crystals
class Crystals:
    """Collects crystal points. All coordinates are asset-local (hang point at
    the origin, body hanging down -Z)."""

    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.pos, self.rot, self.scl, self.kind, self.spk = [], [], [], [], []

    def add(self, p, x_axis, z_axis, scale, kind):
        z = Vector(z_axis).normalized()
        x = Vector(x_axis)
        x = (x - z * x.dot(z))
        if x.length < 1e-6:
            x = z.orthogonal()
        x.normalize()
        y = z.cross(x)
        e = Matrix((x, y, z)).transposed().to_euler()
        self.pos.append(tuple(p))
        self.rot.append((e.x, e.y, e.z))
        self.scl.append(tuple(scale))
        self.kind.append(kind)
        self.spk.append(self.rng.random())

    def rescale(self, k):
        self.pos = [tuple(c * k for c in p) for p in self.pos]
        self.scl = [tuple(c * k for c in p) for p in self.scl]

    def strand(self, ang, r0, z0, r1, z1, n, w, sag=0.0, kind=0):
        """n beads from (r0,z0) to (r1,z1) in the radial plane at angle ang.
        sag bows the strand inward (toward the axis)."""
        ca, sa = math.cos(ang), math.sin(ang)

        def pt(t):
            r = r0 + (r1 - r0) * t - sag * math.sin(math.pi * t)
            z = z0 + (z1 - z0) * t
            return Vector((r * ca, r * sa, z))

        for i in range(n):
            a, b = pt(i / n), pt((i + 1) / n)
            d = b - a
            self.add((a + b) / 2, (-sa, ca, 0), d, (w, w, d.length * 0.97), kind)

    def lens_ring(self, r, z, nr, nz, n, w, h, t, phase=0.0, kind=1):
        """Ring of n lenses at radius r, face normal (nr radial, nz up)."""
        for i in range(n):
            a = 2 * math.pi * (i + phase) / n
            ca, sa = math.cos(a), math.sin(a)
            self.add((r * ca, r * sa, z), (-sa, ca, 0), (nr * ca, nr * sa, nz), (w, h, t), kind)

    def drops(self, r, z, n, w, length, phase=0.0):
        for i in range(n):
            a = 2 * math.pi * (i + phase) / n
            self.add((r * math.cos(a), r * math.sin(a), z - length / 2),
                     (math.cos(a + 0.6), math.sin(a + 0.6), 0), (0, 0, 1), (w, w, length), 2)


def bowl_rings(cr, fr, prof, d_top, d_bot, gap, thick, kind=1, hoop_seg=40, hoop=0.003, s_end=1.0):
    """Concentric necklaces of identical crystals down a bowl profile.
    prof(t), t in 0..1, gives (r, z). Crystals touch along each ring, sit
    `gap` diameters apart ring to ring, shrink from d_top to d_bot, and all
    point the same way (x along the ring, z along the bowl normal).
    Returns the number of rings."""
    M = 400
    pts = [prof(i / M) for i in range(M + 1)]
    acc = [0.0]
    for i in range(M):
        acc.append(acc[-1] + math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]))
    total = acc[-1] * s_end

    def at(s):
        i = 1
        while i < M and acc[i] < s:
            i += 1
        (ra, za), (rb, zb) = pts[i - 1], pts[i]
        seg = math.hypot(rb - ra, zb - za)
        f = (s - acc[i - 1]) / seg
        return ra + (rb - ra) * f, za + (zb - za) * f, -(zb - za) / seg, (rb - ra) / seg

    s, k = d_top * 0.5, 0
    while s < total:
        r, z, nr, nz = at(s)
        d = d_top + (d_bot - d_top) * s / total
        n = max(5, int(2 * math.pi * r / d))
        w = 2 * math.pi * r / n
        cr.lens_ring(r, z, nr, nz, n, w, w, thick * w, phase=0.5 * (k % 2), kind=kind)
        if fr is not None and s + d * gap * 0.5 < total:
            hr, hz, _, _ = at(s + d * gap * 0.5)     # wire hoop between this necklace and the next
            fr.ring(hr, hz, hoop, hoop_seg if hr > 0.4 else max(16, hoop_seg // 2), 3)
        s += d * gap
        k += 1
    return k


def _node_group(name, protos, realize):
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    nin, nout = N.new("NodeGroupInput"), N.new("NodeGroupOutput")

    def named(attr, dtype):
        n = N.new("GeometryNodeInputNamedAttribute")
        n.data_type = dtype
        n.inputs["Name"].default_value = attr
        return next(o for o in n.outputs if o.enabled and o.name == "Attribute")

    rot = N.new("FunctionNodeEulerToRotation")
    L.new(named("rot", "FLOAT_VECTOR"), rot.inputs[0])
    scl = named("scl", "FLOAT_VECTOR")
    kind = named("kind", "INT")
    join = N.new("GeometryNodeJoinGeometry")
    for k, ob in enumerate(protos):
        oi = N.new("GeometryNodeObjectInfo")
        oi.inputs["Object"].default_value = ob
        oi.inputs["As Instance"].default_value = True
        cmp = N.new("FunctionNodeCompare")
        cmp.data_type = "INT"
        cmp.operation = "EQUAL"
        ci = [i for i in cmp.inputs if i.enabled]
        L.new(kind, ci[0])
        ci[1].default_value = k
        iop = N.new("GeometryNodeInstanceOnPoints")
        L.new(nin.outputs[0], iop.inputs["Points"])
        L.new(cmp.outputs[0], iop.inputs["Selection"])
        L.new(oi.outputs["Geometry"], iop.inputs["Instance"])
        L.new(rot.outputs[0], iop.inputs["Rotation"])
        L.new(scl, iop.inputs["Scale"])
        L.new(iop.outputs[0], join.inputs[0])
    out = join.outputs[0]
    if realize:
        rz = N.new("GeometryNodeRealizeInstances")
        L.new(out, rz.inputs[0])
        out = rz.outputs[0]
    L.new(out, nout.inputs[0])
    return ng


def build_crystals(name, cr, protos, coll, export_coll):
    """Makes <name>_crystals (instanced) in coll and <name>_crystals_export
    (realised, with the Col vertex colour) in export_coll."""
    me = bpy.data.meshes.new(name + "_points")
    me.from_pydata(cr.pos, [], [])

    def attr(n, t, key, data):
        a = me.attributes.new(n, t, "POINT")
        a.data.foreach_set(key, data)

    attr("rot", "FLOAT_VECTOR", "vector", [c for v in cr.rot for c in v])
    attr("scl", "FLOAT_VECTOR", "vector", [c for v in cr.scl for c in v])
    attr("kind", "INT", "value", cr.kind)
    attr("sparkle", "FLOAT", "value", cr.spk)

    ob = bpy.data.objects.new(name + "_crystals", me)
    coll.objects.link(ob)
    ob.modifiers.new("Crystals", "NODES").node_group = _node_group(name + "_instancer", protos, False)
    ob.visible_shadow = False      # the lamp inside must shine through

    # realised variant
    tmp = bpy.data.objects.new(name + "_tmp", me)
    coll.objects.link(tmp)
    ng_r = _node_group(name + "_realize_tmp", protos, True)
    tmp.modifiers.new("Crystals", "NODES").node_group = ng_r
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    rme = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    rme.name = name + "_crystals_export"
    bpy.data.objects.remove(tmp)
    bpy.data.node_groups.remove(ng_r)

    n = len(rme.vertices)
    spk = [0.0] * n
    rme.attributes["sparkle"].data.foreach_get("value", spk)
    for junk in ("rot", "scl", "kind"):
        if junk in rme.attributes:
            rme.attributes.remove(rme.attributes[junk])
    a = rme.attributes.new("_sparkle", "FLOAT", "POINT")
    a.data.foreach_set("value", spk)
    col = rme.color_attributes.new("Col", "FLOAT_COLOR", "POINT")
    flat = []
    for s in spk:
        flat += [s, (s * 17.317) % 1.0, 1.0, 1.0]
    col.data.foreach_set("color", flat)
    rme.color_attributes.active_color = col
    rme.color_attributes.render_color_index = list(rme.color_attributes).index(col)
    if not rme.materials:
        rme.materials.append(crystal_material())
    rob = bpy.data.objects.new(name + "_crystals_export", rme)
    rob.visible_shadow = False
    export_coll.objects.link(rob)
    return ob, rob


# ---------------------------------------------------------------- metal frame
class Frame:
    def __init__(self):
        self.bm = bmesh.new()

    def lathe(self, profile, seg=32, closed=False):
        """profile: [(r, z), ...] revolved around Z."""
        bm = self.bm
        rings = []
        for r, z in profile:
            if r < 1e-6:
                v = bm.verts.new((0, 0, z))
                rings.append([v] * seg)
            else:
                rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / seg),
                                            r * math.sin(2 * math.pi * i / seg), z)) for i in range(seg)])
        pairs = list(zip(rings, rings[1:]))
        if closed:
            pairs.append((rings[-1], rings[0]))
        for a, b in pairs:
            for i in range(seg):
                j = (i + 1) % seg
                vs = []
                for v in (a[i], a[j], b[j], b[i]):
                    if v not in vs:
                        vs.append(v)
                if len(vs) >= 3:
                    try:
                        bm.faces.new(vs)
                    except ValueError:
                        pass

    def ring(self, R, z, tube=0.008, seg=48, tseg=5):
        self.lathe([(R + tube * math.cos(2 * math.pi * k / tseg), z + tube * math.sin(2 * math.pi * k / tseg))
                    for k in range(tseg)], seg, closed=True)

    def band(self, R, z_top, h, seg=32):
        self.lathe([(R, z_top), (R, z_top - h)], seg)

    def bead_band(self, R, z_top, h, bulge, seg=40):
        """Rounded band, the bead-mesh wrapped ring."""
        self.lathe([(R - 0.2 * bulge, z_top), (R + 0.75 * bulge, z_top - 0.2 * h), (R + bulge, z_top - 0.5 * h),
                    (R + 0.75 * bulge, z_top - 0.8 * h), (R - 0.2 * bulge, z_top - h)], seg)

    def finish(self, name, coll, mat, smooth=True, scale=1.0):
        for v in self.bm.verts:
            v.co *= scale
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces[:])
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        for p in me.polygons:
            p.use_smooth = smooth
        me.materials.append(mat)
        ob = bpy.data.objects.new(name, me)
        coll.objects.link(ob)
        return ob


def bulbs(name, coll, spots, size=0.03):
    """Small emissive candle bulbs at [(x, y, z), ...]."""
    bm = bmesh.new()
    for p in spots:
        r = bmesh.ops.create_icosphere(bm, subdivisions=1, radius=size)
        for v in r["verts"]:
            v.co.z *= 1.7
            v.co += Vector(p)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bulb_material())
    ob = bpy.data.objects.new(name, me)
    ob.visible_shadow = False
    coll.objects.link(ob)
    return ob


def ring_spots(r, z, n, phase=0.0):
    return [(r * math.cos(2 * math.pi * (i + phase) / n), r * math.sin(2 * math.pi * (i + phase) / n), z)
            for i in range(n)]


# ---------------------------------------------------------------- utilities
def tri_count(coll):
    t = 0
    for ob in coll.objects:
        if ob.type == "MESH":
            t += sum(len(p.vertices) - 2 for p in ob.data.polygons)
    return t


def export_collection(name):
    """<name>_export lives in the file but is excluded from the view layer."""
    c = bpy.data.collections.new(name)
    bpy.context.scene.collection.children.link(c)
    bpy.context.view_layer.layer_collection.children[c.name].exclude = True
    return c


def warm_light(name, power, radius=0.25):
    """Near-neutral warm white, the way the photos read (about 4000 K as the
    camera sees it). A plain colour, not a blackbody: Blender's blackbody at
    3-4000 K turns the white walls orange."""
    li = bpy.data.lights.new(name, "POINT")
    li.energy = power
    li.shadow_soft_size = radius
    if hasattr(li, "use_temperature"):
        li.use_temperature = False
    li.color = LIGHT_RGB
    li["kelvin_look"] = 4000
    return bpy.data.objects.new(name, li)


def preview_settings(bg=(0.05, 0.05, 0.06), strength=0.02, exposure=-2.6):
    dark_world(strength, bg)
    sc = bpy.context.scene
    sc.cycles.transparent_max_bounces = 24      # crystals use alpha
    sc.cycles.max_bounces = 6
    sc.view_settings.exposure = exposure


def side_by_side(out_name, panels, height=720):
    """panels: paths (photo crops or renders). Writes previews/<out_name>.png."""
    import subprocess
    conv = "/opt/ImageMagick/bin/convert"
    if not os.path.exists(conv):
        print("no ImageMagick, skipped", out_name)
        return
    args = [conv]
    for p in panels:
        args += ["(", p, "-auto-orient", "-resize", "x%d" % height, ")"]
    args += ["+append", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                     "previews", out_name + ".png")]
    subprocess.run(args, stderr=subprocess.DEVNULL)


def dark_world(strength=0.02, bg=(0.05, 0.05, 0.06)):
    w = bpy.data.worlds.new("PreviewWorld")
    w.use_nodes = True
    node = next(n for n in w.node_tree.nodes if n.type == "BACKGROUND")
    node.inputs[0].default_value = (*bg, 1)
    node.inputs[1].default_value = strength
    bpy.context.scene.world = w
