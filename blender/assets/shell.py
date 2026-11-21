"""Room shell: floor, walls with windows, wainscot, ceiling, back wall, front
panelling. Builds collection `Shell`, saves blender/assets/shell.blend and
renders previews to blender/previews/shell_*.png.

Run: Blender -b --python blender/assets/shell.py   (add `-- --no-render` to skip previews)
"""
import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common as C  # noqa: E402

C.reset_scene()
COL = C.collection("Shell")

W2 = C.NAVE_W / 2
L = C.NAVE_L
FRONT_Y = L + C.ICONO_D / 2        # face of the wall above the iconostasis
WALL_T = 0.45

# ---- local numbers (not in common.py; estimated from the photos) ----------
COVE_RUN = 2.2                     # horizontal run of each flat sloped side plane of the ceiling
COVE_SEG = 1                       # planar: one flat plane per side
BRACKET_FOOT = C.WALL_H - 0.95     # top of the bracket corbel, where the brace leaves the wall
BRACKET_REACH = 1.15               # how far the curved brace swings out from the wall
BRACKET_T = 0.12
REVEAL_D = 0.30                    # glass set-back from the wall face
REVEAL_R = 0.44                    # width of the stepped plaster surround
ARCH_SEG = 20
MULLION_3 = (0.35, 0.655)          # sash rails as a fraction of the glass height
MULLION_2 = (0.33,)
WINDOW_EMIT = 0.05                 # faint for the evening scene; raise (about 1.5) for a daytime variant
GLASS_TINT = 0.16                  # darkens the glass as a lit surface (night: lit only from inside)

ALC_R = 2.05                       # back alcove half width
ALC_SPRING, ALC_CROWN = 3.75, 4.6  # segmental arch in the back wall
ALC_D = 2.4                        # depth behind the back wall face
ALC_WALL = 0.45                    # thickness of the arch wall
ALC_H = 0.45                       # platform, three risers
ALC_EAVE, ALC_RIDGE, ALC_RIDGE_X = ALC_H + 4.2, ALC_H + 5.0, 0.6
DDOOR_W, DDOOR_H = 1.75, 2.1       # double doors
SDOOR_W, SDOOR_H = 0.86, 2.05      # single doors
CASING = 0.14
DOOR_L_X = -(W2 - 0.78)            # left back door sits in the corner
DOOR_R_X = 2.55
RELIEF_W, RELIEF_H = 0.9, 1.9

LAND_D = 1.2                       # stair landing, right-back corner
LAND_X = W2 - LAND_D
LAND_HALF = 0.85                   # landing reaches this far each side of the short window
LAND_Y = C.WINDOW_Y[-1] + LAND_HALF
CORNER_STAIR = C.WINDOW_Y[-1] - LAND_HALF < 1.6   # window in the corner -> stair runs along the back wall
LAND_Z = 1.0
STAIR_W = LAND_D
STAIR_N, STAIR_RISE, STAIR_GO = 5, 0.2, 0.26
SHRINE_BACK_L_X = -3.195            # slot positions are fixed (assembly uses them)
SHRINE_BACK_R_X = LAND_X - 0.45

PANEL_HW = 0.27 * C.NAVE_W         # wood panelling above the iconostasis
FOIL_BASE = C.ICONO_H + C.CHORUS_H  # assumes the iconostasis stands on the chorus
FOIL_HW = 0.18 * C.NAVE_W          # half width of the scalloped opening
FOIL_RC = FOIL_HW * 0.5            # centre lobe radius
FOIL_LEDGE = FOIL_HW * 0.06
FOIL_RECESS = 0.14                 # thickness of the panelled wall at the opening
SANCT_D = 3.0                      # sanctuary box behind the opening; deeper and the ceiling cuts the view
SANCT_Z0 = C.ICONO_H - 0.6         # nothing lower can be seen from the nave
SANCT_H = C.CEIL_H
# far-wall windows (IMG_2128): Christ in the centre, a small niche window each side, sills level
ALTAR_CHRIST_W = 0.9               # glass width; height follows the texture ratio (1:1.93)
ALTAR_SILL = FOIL_BASE + 1.0       # chosen so it shows behind and above the crucifix from the aisle
ALTAR_SMALL_TOP = 0.37             # small windows reach this fraction of the Christ window's height
ALTAR_SMALL_PITCH = 1.2            # centre spacing, in Christ-window widths
# tall archangel windows on the sanctuary side walls: (name, width, fallback height, sill)
ALTAR_SIDE = {-1: ("gabriel", 0.55, 2.45, FOIL_BASE + 0.9), 1: ("mikhail", 0.8, 1.8, FOIL_BASE + 1.2)}
MEDALLION_Y = L / 2


# ---- materials -------------------------------------------------------------
def striped(name, rgb, rough, width, axis="u", groove=0.04, dark=0.45, var=0.22, metallic=0.0, bump=0.0,
            coat=0.0):
    """Principled material with board lines every `width` metres along a UV axis."""
    m = C.flat_material(name, rgb, rough, metallic)
    nt = m.node_tree
    b = C.bsdf(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs[0])

    def math_node(op, a, bval=None):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        if isinstance(a, float):
            n.inputs[0].default_value = a
        else:
            nt.links.new(a, n.inputs[0])
        if bval is not None:
            if isinstance(bval, float):
                n.inputs[1].default_value = bval
            else:
                nt.links.new(bval, n.inputs[1])
        return n.outputs[0]

    coord = sep.outputs["X" if axis == "u" else "Y"]
    scaled = math_node("MULTIPLY", coord, 1.0 / width)
    fr = math_node("FRACT", scaled)
    is_groove = math_node("LESS_THAN", fr, groove)
    idx = math_node("FLOOR", scaled)
    wn = nt.nodes.new("ShaderNodeTexWhiteNoise")
    wn.noise_dimensions = "1D"
    nt.links.new(idx, wn.inputs["W"])
    tone = math_node("SUBTRACT", 1.0, math_node("MULTIPLY", wn.outputs["Value"], var))
    gr = math_node("SUBTRACT", 1.0, math_node("MULTIPLY", is_groove, 1.0 - dark))
    fac = math_node("MULTIPLY", tone, gr)
    vm = nt.nodes.new("ShaderNodeVectorMath")
    vm.operation = "SCALE"
    vm.inputs[0].default_value = rgb
    nt.links.new(fac, vm.inputs["Scale"])
    nt.links.new(vm.outputs["Vector"], b.inputs["Base Color"])
    if bump:
        bn = nt.nodes.new("ShaderNodeBump")
        bn.inputs["Strength"].default_value = bump
        bn.inputs["Distance"].default_value = 0.004
        # shallow V between boards: height falls toward each board edge
        edge = math_node("MINIMUM", fr, math_node("SUBTRACT", 1.0, fr))
        nt.links.new(math_node("MINIMUM", math_node("MULTIPLY", edge, 6.0), 1.0), bn.inputs["Height"])
        nt.links.new(bn.outputs["Normal"], b.inputs["Normal"])
    if coat:
        b.inputs["Coat Weight"].default_value = coat
        b.inputs["Coat Roughness"].default_value = 0.10
    m["shell_math"] = 1
    return m


def perforated(name, rgb, rough, pitch_u, pitch_v):
    """White sheet metal with rows of dark slots (heater cover grille)."""
    m = C.flat_material(name, rgb, rough)
    nt = m.node_tree
    b = C.bsdf(m)
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    nt.links.new(tc.outputs["UV"], sep.inputs[0])

    def mn(op, a, bv):
        n = nt.nodes.new("ShaderNodeMath")
        n.operation = op
        nt.links.new(a, n.inputs[0])
        if isinstance(bv, float):
            n.inputs[1].default_value = bv
        else:
            nt.links.new(bv, n.inputs[1])
        return n.outputs[0]

    su = mn("LESS_THAN", mn("FRACT", mn("MULTIPLY", sep.outputs["X"], 1.0 / pitch_u), 0.0), 0.55)
    sv = mn("LESS_THAN", mn("FRACT", mn("MULTIPLY", sep.outputs["Y"], 1.0 / pitch_v), 0.0), 0.72)
    slot = mn("MULTIPLY", su, sv)
    fac = mn("SUBTRACT", mn("MULTIPLY", slot, -0.93), -1.0)
    vm = nt.nodes.new("ShaderNodeVectorMath")
    vm.operation = "SCALE"
    vm.inputs[0].default_value = rgb
    nt.links.new(fac, vm.inputs["Scale"])
    nt.links.new(vm.outputs["Vector"], b.inputs["Base Color"])
    return m


def tint(mat, rgb):
    """Multiply an image material's base colour (no-op on the flat fallback)."""
    b = C.bsdf(mat)
    if not b.inputs["Base Color"].links:
        return mat
    src = b.inputs["Base Color"].links[0].from_socket
    vm = mat.node_tree.nodes.new("ShaderNodeVectorMath")
    vm.operation = "MULTIPLY"
    vm.inputs[1].default_value = rgb
    mat.node_tree.links.new(src, vm.inputs[0])
    mat.node_tree.links.new(vm.outputs["Vector"], b.inputs["Base Color"])
    return mat


def emissive(name, rgb, strength):
    m = C.flat_material(name, rgb, 0.4)
    b = C.bsdf(m)
    b.inputs["Emission Color"].default_value = (*rgb, 1.0)
    b.inputs["Emission Strength"].default_value = strength
    return m


M_CARPET = tint(C.image_material("Shell_Carpet", "patterns/carpet_red.jpg", fallback=(0.22, 0.012, 0.022), rough=0.95),
                (0.30, 0.45, 0.70))            # deep burgundy
M_RUNNER = tint(C.image_material("Shell_Runner", "patterns/runner.jpg", fallback=(0.42, 0.16, 0.12), rough=0.9),
                (0.8, 0.8, 0.8))
M_PLASTER = C.flat_material("Shell_Plaster", (0.86, 0.875, 0.89), 0.8)          # clean cool white
M_RECESS = C.flat_material("Shell_Recess", (0.80, 0.78, 0.74), 0.9)
# near-black varnished tongue-and-groove boards running along the nave
M_CEIL = striped("Shell_CeilingPlanks", (0.020, 0.010, 0.007), 0.30, 0.085, "v", 0.05, 0.4, 0.3, bump=1.0, coat=0.8)
M_DARKWOOD = C.flat_material("Shell_DarkWood", (0.016, 0.009, 0.007), 0.22)
M_PINE = striped("Shell_KnottyPine", (0.60, 0.27, 0.07), 0.22, 0.11, "u", 0.05, 0.45, 0.28, bump=0.4, coat=0.5)
M_DOOR = striped("Shell_DoorWood", (0.27, 0.11, 0.045), 0.3, 0.45, "u", 0.0, 1.0, 0.12)
M_TRIMWOOD = striped("Shell_CasingWood", (0.33, 0.17, 0.07), 0.35, 0.028, "u", 0.3, 0.7, 0.0)
M_PANEL = striped("Shell_FrontPanelling", (0.30, 0.15, 0.07), 0.4, 0.30, "u", 0.03, 0.55, 0.3)
M_OAK = C.flat_material("Shell_ArchTrimGold", (0.62, 0.46, 0.20), 0.35, 0.6)
M_OAKWOOD = striped("Shell_StairOak", (0.45, 0.27, 0.12), 0.35, 0.09, "v", 0.04, 0.7, 0.15)
M_CAP = C.flat_material("Shell_WainscotCap", (0.20, 0.08, 0.03), 0.25)
M_GREY = C.flat_material("Shell_FixtureGrey", (0.45, 0.45, 0.46), 0.4, 0.6)
M_HEATER = C.flat_material("Shell_HeaterWhite", (0.82, 0.82, 0.80), 0.5)
M_GRILLE = perforated("Shell_HeaterGrille", (0.82, 0.82, 0.80), 0.5, 0.028, 0.085)
M_VENT = striped("Shell_VentGrille", (0.62, 0.62, 0.62), 0.5, 0.04, "v", 0.45, 0.25, 0.0)
M_WHITE = C.flat_material("Shell_WhitePaint", (0.88, 0.88, 0.86), 0.45)
M_IRON = C.flat_material("Shell_Iron", (0.015, 0.015, 0.015), 0.5, 1.0)
M_GOLD = C.flat_material("Shell_Gold", (1.0, 0.72, 0.30), 0.3, 1.0)
M_GLASSDARK = C.flat_material("Shell_DoorGlass", (0.05, 0.06, 0.07), 0.08)
M_EXIT = emissive("Shell_ExitRed", (0.9, 0.03, 0.02), 4.0)
M_RELIEF = C.image_material("StMark_Relief", "icons/stmark_relief.jpg", fallback=(0.42, 0.20, 0.09), rough=0.38)
_b = C.bsdf(M_RELIEF)
_b.inputs["Metallic"].default_value = 0.6
_hp = os.path.join(C.TEX, "icons", "stmark_relief_height.jpg")
if os.path.exists(_hp):                      # optional height map -> bump
    _nt = M_RELIEF.node_tree
    _ht = _nt.nodes.new("ShaderNodeTexImage")
    _ht.image = bpy.data.images.load(_hp, check_existing=True)
    _ht.image.colorspace_settings.name = "Non-Color"
    _bump = _nt.nodes.new("ShaderNodeBump")
    _bump.inputs["Strength"].default_value = 0.8
    _bump.inputs["Distance"].default_value = 0.03
    _nt.links.new(_ht.outputs["Color"], _bump.inputs["Height"])
    _nt.links.new(_bump.outputs["Normal"], _b.inputs["Normal"])


# ---- mesh builder ------------------------------------------------------------
class Builder:
    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.mats = []

    def mi(self, mat):
        if mat not in self.mats:
            self.mats.append(mat)
        return self.mats.index(mat)

    def _orient(self, f, n=None, toward=None):
        f.normal_update()
        if toward is not None:
            n = Vector(toward) - f.calc_center_median()
        if n is not None and f.normal.dot(Vector(n)) < 0:
            f.normal_flip()

    def face(self, pts, mat, n=None, toward=None):
        f = self.bm.faces.new([self.bm.verts.new(p) for p in pts])
        f.material_index = self.mi(mat)
        self._orient(f, n, toward)
        return f

    def box(self, lo, hi, mat, skip="", mats=None):
        """Axis box. skip: any of 'x-','x+','y-','y+','z-','z+' (space separated)."""
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        sides = {
            "x-": ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
            "x+": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
            "y-": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
            "y+": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
            "z-": ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
            "z+": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
        }
        sk = skip.split()
        for key, (pts, n) in sides.items():
            if key not in sk:
                self.face(pts, (mats or {}).get(key, mat), n=n)

    def beam(self, p0, p1, w, h, mat):
        """Rectangular bar between two points; w is horizontal, h is along Z."""
        p0, p1 = Vector(p0), Vector(p1)
        d = (p1 - p0).normalized()
        side = Vector((-d.y, d.x, 0))
        side = side.normalized() * (w / 2) if side.length > 1e-6 else Vector((w / 2, 0, 0))
        up = Vector((0, 0, h / 2))
        a = [p0 - side - up, p0 + side - up, p0 + side + up, p0 - side + up]
        b = [p + (p1 - p0) for p in a]
        mid = (p0 + p1) / 2
        for i in range(4):
            j = (i + 1) % 4
            q = [a[i], a[j], b[j], b[i]]
            c = sum(q, Vector()) / 4
            self.face(q, mat, n=c - mid)
        self.face(a, mat, n=-d)
        self.face(b, mat, n=d)

    def fill(self, loops, to3d, mat, n=None, toward=None):
        """Triangulate a flat polygon with holes (no booleans, no T-junctions)."""
        edges = []
        for loop in loops:
            vs = [self.bm.verts.new(to3d(*p)) for p in loop]
            for i in range(len(vs)):
                edges.append(self.bm.edges.new((vs[i], vs[(i + 1) % len(vs)])))
        res = bmesh.ops.triangle_fill(self.bm, use_beauty=True, use_dissolve=False, edges=edges)
        idx = self.mi(mat)
        for g in res["geom"]:
            if isinstance(g, bmesh.types.BMFace):
                g.material_index = idx
                self._orient(g, n, toward)

    def strip(self, ring_a, ring_b, mat, closed=True, n=None, toward=None):
        cnt = len(ring_a)
        for i in range(cnt if closed else cnt - 1):
            j = (i + 1) % cnt
            self.face([ring_a[i], ring_a[j], ring_b[j], ring_b[i]], mat, n=n, toward=toward)

    def finish(self, uv_mode="box", origin=None):
        bm = self.bm
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-4)
        ngons = [f for f in bm.faces if len(f.verts) > 4]
        if ngons:
            bmesh.ops.triangulate(bm, faces=ngons)
        if origin is not None:
            bmesh.ops.translate(bm, verts=bm.verts, vec=-Vector(origin))
        uv = bm.loops.layers.uv.new("UVMap")
        o = Vector(origin) if origin is not None else Vector()
        for f in bm.faces:
            n = f.normal
            ax = max(range(3), key=lambda k: abs(n[k]))
            for lp in f.loops:
                p = lp.vert.co + o
                if ax == 0:
                    lp[uv].uv = (p.y, p.z)
                elif ax == 1:
                    lp[uv].uv = (p.x, p.z)
                else:
                    lp[uv].uv = (p.y, p.x)
        me = bpy.data.meshes.new(self.name)
        bm.to_mesh(me)
        bm.free()
        for m in self.mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        if origin is not None:
            ob.location = origin
        COL.objects.link(ob)
        return ob


def plane_object(name, pts, mat, uv_fn, facing=None):
    """Single flat polygon as its own object (origin at its centre) with explicit UVs."""
    pts = [Vector(p) for p in pts]
    c = sum(pts, Vector()) / len(pts)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    c = (lo + hi) / 2
    bm = bmesh.new()
    f = bm.faces.new([bm.verts.new(p - c) for p in pts])
    if facing is not None:
        f.normal_update()
        if f.normal.dot(Vector(facing)) < 0:
            f.normal_flip()
    uv = bm.loops.layers.uv.new("UVMap")
    for lp in f.loops:
        lp[uv].uv = uv_fn(lp.vert.co + c)
    if len(pts) > 4:
        bmesh.ops.triangulate(bm, faces=[f])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    ob.location = c
    COL.objects.link(ob)
    return ob


def empty(name, loc, rot_z=0.0):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = "ARROWS"
    e.empty_display_size = 0.4
    e.location = loc
    e.rotation_euler = (0, 0, rot_z)
    COL.objects.link(e)
    return e


def ceil_z(x):
    """Ceiling height: flat centre, one straight sloped plane each side."""
    a = W2 - abs(x)
    if a >= COVE_RUN:
        return C.CEIL_H
    return C.WALL_H + (C.CEIL_H - C.WALL_H) * max(a, 0.0) / COVE_RUN


ROOM_C = (0, L / 2, 3.5)


def offset_loop(loop, r):
    out = []
    cnt = len(loop)
    area = sum(loop[i][0] * loop[(i + 1) % cnt][1] - loop[(i + 1) % cnt][0] * loop[i][1] for i in range(cnt))
    sgn = 1.0 if area < 0 else -1.0           # outward
    for i in range(cnt):
        p0, p1, p2 = Vector(loop[i - 1]), Vector(loop[i]), Vector(loop[(i + 1) % cnt])
        e0, e1 = (p1 - p0).normalized(), (p2 - p1).normalized()
        n0, n1 = Vector((-e0.y, e0.x)) * sgn, Vector((-e1.y, e1.x)) * sgn
        nn = n0 + n1
        nn = nn.normalized() if nn.length > 1e-6 else n0
        k = min(1.0 / max(nn.dot(n0), 0.35), 2.0)
        out.append(tuple(p1 + nn * r * k))
    return out

# =============================================================================
# FLOOR
# =============================================================================
fl = Builder("Shell_Floor")
step_go = 0.35
y_step = C.CHORUS_Y - step_go
fl.face([(-W2, 0, 0), (W2, 0, 0), (W2, y_step, 0), (-W2, y_step, 0)], M_CARPET, n=(0, 0, 1))
h1 = C.CHORUS_H / 2
fl.face([(-W2, y_step, 0), (W2, y_step, 0), (W2, y_step, h1), (-W2, y_step, h1)], M_CARPET, n=(0, -1, 0))
fl.face([(-W2, y_step, h1), (W2, y_step, h1), (W2, C.CHORUS_Y, h1), (-W2, C.CHORUS_Y, h1)], M_CARPET, n=(0, 0, 1))
fl.face([(-W2, C.CHORUS_Y, h1), (W2, C.CHORUS_Y, h1), (W2, C.CHORUS_Y, C.CHORUS_H), (-W2, C.CHORUS_Y, C.CHORUS_H)],
        M_CARPET, n=(0, -1, 0))
fl.face([(-W2, C.CHORUS_Y, C.CHORUS_H), (W2, C.CHORUS_Y, C.CHORUS_H), (W2, FRONT_Y, C.CHORUS_H),
         (-W2, FRONT_Y, C.CHORUS_H)], M_CARPET, n=(0, 0, 1))
# alcove platform (inside the alcove) and two lower steps out into the nave
fl.box((-ALC_R, -ALC_D, 0), (ALC_R, 0, ALC_H), M_CARPET, skip="z- y- x- x+")
r3 = ALC_H / 3
fl.box((-1.15, 0, 0), (1.15, 0.32, 2 * r3), M_CARPET, skip="z- y-")
fl.box((-1.15, 0.32, 0), (1.15, 0.64, r3), M_CARPET, skip="z- y-")
fl.finish()

# runner: its own object, UV u across the width, v repeating along the aisle
ry0, ry1 = 0.72, y_step - 0.08
hw = C.RUNNER_W / 2
plane_object("Shell_Runner",
             [(-hw, ry0, 0.006), (hw, ry0, 0.006), (hw, ry1, 0.006), (-hw, ry1, 0.006)], M_RUNNER,
             lambda p: ((p.x + hw) / C.RUNNER_W, (p.y - ry0) / (C.RUNNER_W * 574.0 / 768.0)))

# =============================================================================
# SIDE WALLS + WINDOWS
# =============================================================================
walls = Builder("Shell_Walls")
mull = Builder("Shell_Mullions")
PROFILE = [(0.0, REVEAL_D), (0.0, REVEAL_D - 0.05), (0.14, 0.10), (0.14, 0.04), (0.24, 0.04), (0.24, -0.02),
           (0.27, -0.05), (REVEAL_R - 0.05, -0.05), (REVEAL_R - 0.02, -0.02), (REVEAL_R, 0.0)]


def window_outline(yc, sill, top, k):
    """[(point(y,z), offset dir)] around the glass, counter-clockwise from bottom-left.
    k = how far the surround drops below the sill, per unit of surround width."""
    r = C.WINDOW_W / 2
    zs = top - r
    out = [((yc - r, sill), (-1.0, -k)), ((yc - r, zs), (-1.0, 0.0))]
    for i in range(1, ARCH_SEG):
        a = math.pi - i * math.pi / ARCH_SEG
        out.append(((yc + r * math.cos(a), zs + r * math.sin(a)), (math.cos(a), math.sin(a))))
    out += [((yc + r, zs), (1.0, 0.0)), ((yc + r, sill), (1.0, -k))]
    return out


def ring2d(outline, r):
    return [(p[0] + r * n[0], p[1] + r * n[1]) for p, n in outline]


def side_wall(sign, names):
    def P(y, z, d=0.0):
        return (sign * (W2 + d), y, z)

    hide = "x+" if sign > 0 else "x-"
    loops = [[(0, 0), (FRONT_Y, 0), (FRONT_Y, C.WALL_H), (0, C.WALL_H)]]
    for i, (yc, name) in enumerate(zip(C.WINDOW_Y, names)):
        short = sign > 0 and i == len(C.WINDOW_Y) - 1
        sill = C.SHORT_WINDOW_SILL if short else C.WINDOW_SILL
        # the surround runs down to the wainscot cap; on the short window it runs
        # down to the landing and frames the white door under the glass
        base = LAND_Z if short else sill
        k = 0.0 if short else (sill - C.WAINSCOT_H - 0.005) / REVEAL_R
        ol = window_outline(yc, base, C.WINDOW_TOP, k)
        loops.append(ring2d(ol, REVEAL_R))
        aim = (sign * (W2 - 3.0), yc, (base + C.WINDOW_TOP) / 2)
        rings = [[P(y, z, d) for y, z in ring2d(ol, r)] for r, d in PROFILE]
        for a, b in zip(rings[:-1], rings[1:]):
            walls.strip(a, b, M_PLASTER, toward=aim)
        # stained glass
        r = C.WINDOW_W / 2
        h = C.WINDOW_TOP - sill
        mat = tint(C.image_material("Win_" + name, "windows/%s.jpg" % name, fallback=(0.04, 0.08, 0.18),
                                    rough=0.08, emit=WINDOW_EMIT), (GLASS_TINT,) * 3)
        gl = window_outline(yc, sill, C.WINDOW_TOP, 0.0)
        gpts = [P(y, z, REVEAL_D) for y, z in ring2d(gl, 0.0)]
        if sign < 0:
            gpts.reverse()          # normal toward the room
        plane_object("Win_" + name, gpts, mat,
                     lambda p, yc=yc, sill=sill, h=h, r=r: (0.5 - sign * (p.y - yc) / (2 * r), (p.z - sill) / h))
        # white sash frame around the glass and the rails between the stacked sashes
        fr_d = REVEAL_D - 0.035
        mull.strip([P(y, z, fr_d) for y, z in ring2d(gl, 0.0)], [P(y, z, fr_d) for y, z in ring2d(gl, -0.045)],
                   M_WHITE, n=(-sign, 0, 0))
        for fr in (MULLION_2 if short else MULLION_3):
            z = sill + fr * h
            xa, xb = sorted((sign * (W2 + REVEAL_D), sign * (W2 + REVEAL_D - 0.06)))
            mull.box((xa, yc - r, z - 0.035), (xb, yc + r, z + 0.035), M_WHITE, skip=hide)
        xa, xb = sorted((sign * (W2 + REVEAL_D), sign * (W2 + REVEAL_D - 0.05)))
        mull.box((xa, yc - r, sill), (xb, yc + r, sill + 0.05), M_WHITE, skip=hide)
        if short:                   # white exit door with closer and push bar, under the glass
            xd = sign * (W2 + REVEAL_D - 0.02)
            mull.face([(xd, yc - r, LAND_Z), (xd, yc + r, LAND_Z), (xd, yc + r, sill), (xd, yc - r, sill)],
                      M_WHITE, n=(-sign, 0, 0))
            xa, xb = sorted((xd, xd - sign * 0.03))
            mull.box((xa, yc - r, sill - 0.09), (xb, yc + r, sill), M_WHITE, skip=hide)
            for ya, yb in ((yc - r, yc - r + 0.06), (yc + r - 0.06, yc + r)):
                mull.box((xa, ya, LAND_Z), (xb, yb, sill - 0.09), M_WHITE, skip=hide + " z-")
            xa, xb = sorted((xd, xd - sign * 0.06))
            mull.box((xa, yc - r + 0.12, sill - 0.22), (xb, yc - r + 0.42, sill - 0.14), M_GREY, skip=hide)
            mull.box((xa, yc - r + 0.08, LAND_Z + 0.95), (xb, yc + r - 0.08, LAND_Z + 1.0), M_GREY, skip=hide)
    walls.fill(loops, lambda y, z: P(y, z), M_PLASTER, n=(-sign, 0, 0))


side_wall(-1, C.LEFT_WINDOWS)
side_wall(1, C.RIGHT_WINDOWS)

# =============================================================================
# BACK WALL + ALCOVE
# =============================================================================
_rise = ALC_CROWN - ALC_SPRING
ARC_RAD = (ALC_R ** 2 + _rise ** 2) / (2 * _rise)
_half = math.asin(ALC_R / ARC_RAD)
arch = [(-ALC_R, 0.0), (-ALC_R, ALC_SPRING)]
for i in range(1, 24):
    a = -_half + i * 2 * _half / 24
    arch.append((ARC_RAD * math.sin(a), ALC_CROWN - ARC_RAD + ARC_RAD * math.cos(a)))
arch += [(ALC_R, ALC_SPRING), (ALC_R, 0.0)]


def notch(xc, w, h):
    return [(xc - w / 2, 0.0), (xc - w / 2, h), (xc + w / 2, h), (xc + w / 2, 0.0)]


back_loop = ([(-W2, 0.0)] + notch(DOOR_L_X, SDOOR_W, SDOOR_H) + arch + notch(DOOR_R_X, SDOOR_W, SDOOR_H)
             + [(W2, 0.0), (W2, C.WALL_H), (W2 - COVE_RUN, C.CEIL_H), (-(W2 - COVE_RUN), C.CEIL_H),
                (-W2, C.WALL_H)])      # trapezoid top under the sloped ceiling planes
walls.fill([back_loop], lambda x, z: (x, 0.0, z), M_PLASTER, n=(0, 1, 0))
# thin moulded bead around the arch
bead = offset_loop(arch, 0.10)[1:-1]
for (xa, za), (xb, zb) in zip(bead[:-1], bead[1:]):
    if abs(xb - xa) < 1e-4:
        walls.box((xa - 0.025, 0.0, min(za, zb)), (xa + 0.025, 0.025, max(za, zb)), M_PLASTER, skip="y-")
    else:
        walls.beam((xa, 0.0, za), (xb, 0.0, zb), 0.05, 0.055, M_PLASTER)
# arch soffit through the wall thickness
walls.strip([(x, 0.0, z) for x, z in arch], [(x, -ALC_WALL, z) for x, z in arch], M_PLASTER, closed=False,
            toward=(0, -ALC_WALL / 2, 1.5))
# inside face of the arch wall (between the arch and the alcove ceiling)
roofp = [(ALC_R, ALC_EAVE), (ALC_RIDGE_X, ALC_RIDGE), (-ALC_RIDGE_X, ALC_RIDGE), (-ALC_R, ALC_EAVE)]
walls.fill([arch[1:-1] + roofp], lambda x, z: (x, -ALC_WALL, z), M_PLASTER, n=(0, -1, 0))
for s in (-1, 1):
    walls.face([(s * ALC_R, -ALC_WALL, 0), (s * ALC_R, -ALC_D, 0), (s * ALC_R, -ALC_D, ALC_EAVE),
                (s * ALC_R, -ALC_WALL, ALC_EAVE)], M_PLASTER, n=(-s, 0, 0))
alc_back = ([(-ALC_R, 0.0)] + notch(0.0, DDOOR_W, ALC_H + DDOOR_H) + [(ALC_R, 0.0)] + roofp)
walls.fill([alc_back], lambda x, z: (x, -ALC_D, z), M_PLASTER, n=(0, 1, 0))

# =============================================================================
# FRONT WALL (above the iconostasis) + RECESS
# =============================================================================
fz0 = C.ICONO_H - 0.2
for s in (-1, 1):
    walls.face([(s * PANEL_HW, FRONT_Y, fz0), (s * W2, FRONT_Y, fz0), (s * W2, FRONT_Y, C.WALL_H),
                (s * max(W2 - COVE_RUN, PANEL_HW), FRONT_Y, ceil_z(max(W2 - COVE_RUN, PANEL_HW))),
                (s * PANEL_HW, FRONT_Y, C.CEIL_H)], M_PLASTER, n=(0, -1, 0))
    gx, gz = s * (PANEL_HW + (W2 - PANEL_HW) * 0.48), C.ICONO_H + 1.75
    walls.box((gx - 0.6, FRONT_Y - 0.03, gz - 0.55), (gx + 0.6, FRONT_Y, gz + 0.55), M_VENT, skip="y+")


def multifoil():
    """Scalloped opening outline (x, z above its base), left to right: a quarter-round
    shoulder each side, a small ledge, and a tall round centre lobe."""
    n, m = 8, 20
    sx, sz = FOIL_HW - FOIL_RC - FOIL_LEDGE, FOIL_HW - FOIL_RC   # shoulder radii (x, z)
    left = []
    for i in range(n + 1):                    # from the base up to the ledge
        a = (math.pi / 2) * i / n
        left.append((-FOIL_HW + sx * (1 - math.cos(a)), sz * math.sin(a)))
    mid = []
    for i in range(m + 1):                    # centre lobe, semicircle standing on the ledge
        a = math.pi - math.pi * i / m
        mid.append((FOIL_RC * math.cos(a), sz + FOIL_RC * math.sin(a)))
    return left + mid + [(-x, z) for x, z in reversed(left)]


foil = [(x, FOIL_BASE + z) for x, z in multifoil()]

panel = Builder("Shell_FrontPanel")
panel.fill([[(-PANEL_HW, fz0), (PANEL_HW, fz0), (PANEL_HW, C.CEIL_H), (-PANEL_HW, C.CEIL_H)], foil],
           lambda x, z: (x, FRONT_Y, z), M_PANEL, n=(0, -1, 0))
# thin gold moulding edging the opening
foil_out = offset_loop(foil, 0.07)
yf = FRONT_Y - 0.03
panel.strip([(x, yf, z) for x, z in foil], [(x, yf, z) for x, z in foil_out], M_OAK, n=(0, -1, 0))
panel.strip([(x, yf, z) for x, z in foil_out], [(x, FRONT_Y, z) for x, z in foil_out], M_OAK,
            toward=(0, FRONT_Y - 3, FOIL_BASE - 4))
foil_c = (0, FRONT_Y, FOIL_BASE + 0.6)
panel.strip([(x, yf, z) for x, z in foil], [(x, FRONT_Y + 0.05, z) for x, z in foil], M_OAK, toward=foil_c)
# the opening is a hole into the sanctuary: only the thickness of the panelled wall shows
panel.strip([(x, FRONT_Y + 0.05, z) for x, z in foil], [(x, FRONT_Y + FOIL_RECESS, z) for x, z in foil], M_PANEL,
            toward=foil_c)
# wood shelf at the base of the opening
panel.box((-FOIL_HW - 0.15, FRONT_Y - 0.22, FOIL_BASE - 0.06), (FOIL_HW + 0.15, FRONT_Y, FOIL_BASE), M_PANEL,
          skip="y+")
panel.finish()

# ---- sanctuary seen through the opening: plain box, three windows on its far wall ----
sy0, sy1 = FRONT_Y + FOIL_RECESS, FRONT_Y + SANCT_D


def tex_ratio(name, default):
    """height / width of textures/windows/<name>.jpg, or the default if it is not there yet."""
    path = os.path.join(C.TEX, "windows", name + ".jpg")
    if os.path.exists(path):
        im = bpy.data.images.load(path, check_existing=True)
        if im.size[0] and im.size[1]:
            return im.size[1] / im.size[0]
    return default


def sanct_window(name, cu, sill, ww, wh, to3d, facing, depth, flip_u=False):
    """Arched window in a plain plaster niche. cu = centre along the wall; to3d(u, z, d) with d into the
    wall. Returns the hole outline for the wall fill."""
    r = ww / 2
    zs = sill + wh - r
    ol = [((cu - r, sill), (-1.0, -1.0)), ((cu - r, zs), (-1.0, 0.0))]
    for i in range(1, 16):
        a = math.pi - i * math.pi / 16
        ol.append(((cu + r * math.cos(a), zs + r * math.sin(a)), (math.cos(a), math.sin(a))))
    ol += [((cu + r, zs), (1.0, 0.0)), ((cu + r, sill), (1.0, -1.0))]
    prof = [(0.0, depth), (0.0, depth - 0.04), (0.10, 0.0), (0.12, -0.03), (0.20, -0.03), (0.22, 0.0)]
    rings = [[to3d(u, z, d) for u, z in ring2d(ol, rr)] for rr, d in prof]
    mid = Vector(to3d(cu, sill + wh / 2, 0.0)) + Vector(facing) * 3.0
    for ra, rb in zip(rings[:-1], rings[1:]):
        walls.strip(ra, rb, M_PLASTER, toward=mid)
    mat = tint(C.image_material("Win_" + name, "windows/%s.jpg" % name, fallback=(0.20, 0.14, 0.05), rough=0.08,
                                emit=WINDOW_EMIT), (GLASS_TINT,) * 3)
    sgn = -1.0 if flip_u else 1.0
    c3 = Vector(to3d(cu, sill, depth))
    e3 = (Vector(to3d(cu + 1.0, sill, depth)) - c3)          # unit step along the wall

    def uv(p):
        return (0.5 + sgn * (p - c3).dot(e3) / ww, (p.z - sill) / wh)

    plane_object("Win_" + name, [to3d(u, z, depth) for u, z in ring2d(ol, 0.0)], mat, uv, facing=facing)
    return ring2d(ol, prof[-1][0])


far_loops = [[(-W2, SANCT_Z0), (W2, SANCT_Z0), (W2, SANCT_H), (-W2, SANCT_H)]]


def far3d(u, z, d):
    return (u, sy1 + d, z)


cw = ALTAR_CHRIST_W
ch = cw * tex_ratio("altar_christ", 1.93)
ALTAR_SILL = min(ALTAR_SILL, SANCT_H - 0.2 - ch)      # keep the arch under the sanctuary ceiling
far_loops.append(sanct_window("altar_christ", 0.0, ALTAR_SILL, cw, ch, far3d, (0, -1, 0), 0.20))
for nm, sx_, dflt in (("altar_small_left", -1, 1.61), ("altar_small_right", 1, 1.92)):
    sh = ALTAR_SMALL_TOP * ch
    sw = sh / tex_ratio(nm, dflt)
    far_loops.append(sanct_window(nm, sx_ * ALTAR_SMALL_PITCH * cw, ALTAR_SILL, sw, sh, far3d, (0, -1, 0), 0.38))
walls.fill(far_loops, far3d and (lambda x, z: (x, sy1, z)), M_RECESS, n=(0, -1, 0))
for sx in (-1, 1):
    nm, sw, sh_default, ssill = ALTAR_SIDE[sx]
    sh = sw * tex_ratio("altar_" + nm, sh_default / sw)
    ssill = max(min(ssill, SANCT_H - 0.15 - sh), SANCT_Z0 + 0.3)     # drop the sill rather than squash the glass
    hole = sanct_window("altar_" + nm, (sy0 + sy1) / 2, ssill, sw, sh,
                        lambda u, z, d, sx=sx: (sx * (W2 + d), u, z), (-sx, 0, 0), 0.25, flip_u=(sx > 0))
    walls.fill([[(sy0, SANCT_Z0), (sy1, SANCT_Z0), (sy1, SANCT_H), (sy0, SANCT_H)], hole],
               lambda u, z, sx=sx: (sx * W2, u, z), M_RECESS, n=(-sx, 0, 0))
walls.face([(-W2, sy0, SANCT_H), (W2, sy0, SANCT_H), (W2, sy1, SANCT_H), (-W2, sy1, SANCT_H)], M_DARKWOOD,
           n=(0, 0, -1))
walls.finish()
mull.finish()

# =============================================================================
# WAINSCOT + HEATER COVERS
# =============================================================================
wn = Builder("Shell_Wainscot")
WH = C.WAINSCOT_H


def wainscot_x(sign, y0, y1, mat):
    xa, xb = sorted((sign * W2, sign * (W2 - 0.025)))
    outer = "x-" if sign < 0 else "x+"
    wn.box((xa, y0, 0), (xb, y1, WH - 0.06), mat, skip="z- z+ " + outer)
    xa, xb = sorted((sign * W2, sign * (W2 - 0.045)))
    wn.box((xa, y0, WH - 0.10), (xb, y1, WH - 0.04), M_CAP, skip=outer)
    xa, xb = sorted((sign * W2, sign * (W2 - 0.07)))
    wn.box((xa, y0, WH - 0.04), (xb, y1, WH), M_CAP, skip=outer)


def wainscot_y(x0, x1, y, facing, mat, z0=0.0):
    ya, yb = sorted((y, y + facing * 0.025))
    outer = "y-" if facing > 0 else "y+"
    wn.box((x0, ya, z0), (x1, yb, z0 + WH - 0.06), mat, skip="z- z+ " + outer)
    ya, yb = sorted((y, y + facing * 0.05))
    wn.box((x0, ya, z0 + WH - 0.06), (x1, yb, z0 + WH), M_CAP, skip=outer)


def heater(sign, y0, y1):
    """White baseboard heater covers in sections: perforated band, chamfered top."""
    hh, hd = 0.70, 0.16
    xw, xf, xc = sign * (W2 - 0.025), sign * (W2 - 0.025 - hd), sign * (W2 - 0.025 - hd + 0.045)
    n = (-sign, 0, 0)
    cnt = max(int(round((y1 - y0) / 1.5)), 1)
    seg = (y1 - y0) / cnt
    for k in range(cnt):
        a, b = y0 + k * seg + 0.006, y0 + (k + 1) * seg - 0.006
        for za, zb, m in ((0, 0.40, M_HEATER), (0.40, 0.62, M_GRILLE), (0.62, hh - 0.045, M_HEATER)):
            wn.face([(xf, a, za), (xf, b, za), (xf, b, zb), (xf, a, zb)], m, n=n)
        wn.face([(xf, a, hh - 0.045), (xf, b, hh - 0.045), (xc, b, hh), (xc, a, hh)], M_HEATER,
                n=(-sign * 0.7, 0, 0.7))
        wn.face([(xc, a, hh), (xc, b, hh), (xw, b, hh), (xw, a, hh)], M_HEATER, n=(0, 0, 1))
        for y, ny in ((a, -1), (b, 1)):
            wn.face([(xf, y, 0), (xw, y, 0), (xw, y, hh), (xc, y, hh), (xf, y, hh - 0.045)], M_HEATER,
                    n=(0, ny, 0))


wainscot_x(-1, 0.0, FRONT_Y, M_PINE)
wainscot_x(1, LAND_Y if CORNER_STAIR else 0.0, FRONT_Y, M_PINE)
heater(-1, 1.4, C.CHORUS_Y - 0.5)
heater(1, LAND_Y + 0.4, C.CHORUS_Y - 0.5)
# small wooden offering box on the left wall near the front
oy = C.BRACKET_Y[0] - 1.0
wn.box((-W2, oy - 0.10, WH + 0.02), (-W2 + 0.12, oy + 0.10, WH + 0.30), M_DOOR, skip="x-")
# security cameras (white, on short arms)
for sgn, cy in ((-1, C.BRACKET_Y[1] + 0.7), (1, C.BRACKET_Y[1] + 0.7)):
    xa, xb = sorted((sgn * W2, sgn * (W2 - 0.22)))
    wn.box((xa, cy - 0.015, 4.05), (xb, cy + 0.015, 4.08), M_WHITE)
    xa, xb = sorted((sgn * (W2 - 0.12), sgn * (W2 - 0.38)))
    wn.box((xa, cy - 0.05, 3.93), (xb, cy + 0.05, 4.05), M_WHITE)
half_c = SDOOR_W / 2 + CASING
for x0, x1 in ((-W2, DOOR_L_X - half_c), (DOOR_L_X + half_c, -ALC_R), (ALC_R, DOOR_R_X - half_c),
               (DOOR_R_X + half_c, LAND_X if CORNER_STAIR else W2)):
    wainscot_y(x0, x1, 0.0, 1, M_PINE)
for s in (-1, 1):                                   # inside the alcove
    xa, xb = sorted((s * ALC_R, s * (DDOOR_W / 2 + CASING)))
    wainscot_y(xa, xb, -ALC_D, 1, M_PINE, ALC_H)
    xa, xb = sorted((s * ALC_R, s * (ALC_R - 0.025)))
    wn.box((xa, -ALC_D, ALC_H), (xb, 0.0, ALC_H + WH - 0.06), M_PINE, skip="z- z+ " + ("x+" if s > 0 else "x-"))
    xa, xb = sorted((s * ALC_R, s * (ALC_R - 0.05)))
    wn.box((xa, -ALC_D, ALC_H + WH - 0.06), (xb, 0.0, ALC_H + WH), M_CAP, skip="x+" if s > 0 else "x-")
wn.finish()

# =============================================================================
# CEILING, CORNICE, BRACKETS, MEDALLION
# =============================================================================
ce = Builder("Shell_Ceiling")
xs = [-W2 + COVE_RUN * i / COVE_SEG for i in range(COVE_SEG + 1)]
xs = xs + [-x for x in reversed(xs)]
for xa, xb in zip(xs[:-1], xs[1:]):
    ce.face([(xa, 0, ceil_z(xa)), (xb, 0, ceil_z(xb)), (xb, FRONT_Y, ceil_z(xb)), (xa, FRONT_Y, ceil_z(xa))],
            M_CEIL, n=(0, 0, -1))
xf = W2 - COVE_RUN
for s in (-1, 1):
    xa, xb = sorted((s * W2, s * (W2 - 0.06)))      # cornice at the wall top
    ce.box((xa, 0, C.WALL_H - 0.24), (xb, FRONT_Y, C.WALL_H + 0.02), M_DARKWOOD,
           skip="z+ " + ("x-" if s < 0 else "x+"))
    xa, xb = sorted((s * (W2 - 0.10), s * (W2 - 0.06)))
    ce.box((xa, 0, C.WALL_H - 0.10), (xb, FRONT_Y, C.WALL_H + 0.02), M_DARKWOOD, skip="z+")
    ce.box((s * xf - 0.07, 0, C.CEIL_H - 0.09), (s * xf + 0.07, FRONT_Y, C.CEIL_H), M_DARKWOOD, skip="z+")
ce.box((-xf, 0, C.CEIL_H - 0.2), (xf, 0.04, C.CEIL_H), M_DARKWOOD, skip="z+ y-")   # band on the back wall

bracket_ys = sorted(C.BRACKET_Y)
if min(bracket_ys) > min(C.WINDOW_Y):            # photos: one more bracket in each corner
    bracket_ys.insert(0, BRACKET_T / 2 + 0.005)
if max(bracket_ys) < max(C.WINDOW_Y):
    bracket_ys.append(FRONT_Y - BRACKET_T / 2 - 0.005)
gold = Builder("Shell_BracketCrosses")
RIB = 0.16
knee_top = ceil_z(W2 - BRACKET_REACH) - RIB
for yb in bracket_ys:
    if 0.5 < yb < FRONT_Y - 0.5:
        ce.box((-xf, yb - 0.06, C.CEIL_H - 0.08), (xf, yb + 0.06, C.CEIL_H), M_DARKWOOD, skip="z+")
    for s in (-1, 1):
        insets = [BRACKET_REACH * (1 - math.cos((math.pi / 2) * i / 10)) for i in range(11)]
        insets += [BRACKET_REACH + (COVE_RUN + 0.07 - BRACKET_REACH) * i / 3 for i in range(1, 4)]
        N = len(insets) - 1
        bot, top = [], []
        for inset in insets:
            x = s * (W2 - inset)
            zt = ceil_z(x)
            if inset <= BRACKET_REACH:
                th = math.acos(max(1 - inset / BRACKET_REACH, 0.0))
                zb = min(BRACKET_FOOT + (knee_top - BRACKET_FOOT) * math.sin(th), zt - RIB)
            else:
                zb = zt - RIB
            bot.append((x, zb))
            top.append((x, zt))
        ya, yc = yb - BRACKET_T / 2, yb + BRACKET_T / 2
        for i in range(N):
            for y, ny in ((ya, -1), (yc, 1)):
                ce.face([(bot[i][0], y, bot[i][1]), (bot[i + 1][0], y, bot[i + 1][1]),
                         (top[i + 1][0], y, top[i + 1][1]), (top[i][0], y, top[i][1])], M_DARKWOOD, n=(0, ny, 0))
            ce.face([(bot[i][0], ya, bot[i][1]), (bot[i + 1][0], ya, bot[i + 1][1]),
                     (bot[i + 1][0], yc, bot[i + 1][1]), (bot[i][0], yc, bot[i][1])], M_DARKWOOD,
                    toward=(s * (W2 - 4), yb, BRACKET_FOOT - 3))
        ce.face([(bot[N][0], ya, bot[N][1]), (bot[N][0], yc, bot[N][1]), (top[N][0], yc, top[N][1]),
                 (top[N][0], ya, top[N][1])], M_DARKWOOD, n=(-s, 0, 0))
        # carved corbel under the brace, and its gold cross
        outer = "x-" if s < 0 else "x+"
        for dx, hw_, z0, z1 in ((0.20, 0.11, BRACKET_FOOT - 0.22, BRACKET_FOOT + 0.02),
                                (0.15, 0.085, BRACKET_FOOT - 0.36, BRACKET_FOOT - 0.22),
                                (0.09, 0.05, BRACKET_FOOT - 0.46, BRACKET_FOOT - 0.36)):
            xa, xb = sorted((s * W2, s * (W2 - dx)))
            ce.box((xa, yb - hw_, z0), (xb, yb + hw_, z1), M_DARKWOOD, skip=outer)
        cx = s * (W2 - 0.20)
        xa, xb = sorted((cx, cx - s * 0.02))
        cz = BRACKET_FOOT + 0.02
        gold.box((xa, yb - 0.018, cz - 0.14), (xb, yb + 0.018, cz + 0.18), M_GOLD)
        gold.box((xa, yb - 0.09, cz + 0.06), (xb, yb + 0.09, cz + 0.10), M_GOLD)
gold.finish()

# medallion (lathe)
prof = [(0.0, 0.03), (0.26, 0.03), (0.30, 0.07), (0.44, 0.07), (0.50, 0.03), (0.62, 0.03), (0.68, 0.09),
        (0.78, 0.09), (0.83, 0.0)]
SEG = 32
for (r0, d0), (r1, d1) in zip(prof[:-1], prof[1:]):
    for k in range(SEG):
        a0, a1 = 2 * math.pi * k / SEG, 2 * math.pi * (k + 1) / SEG
        q = [(r0 * math.cos(a0), MEDALLION_Y + r0 * math.sin(a0), C.CEIL_H - d0),
             (r1 * math.cos(a0), MEDALLION_Y + r1 * math.sin(a0), C.CEIL_H - d1),
             (r1 * math.cos(a1), MEDALLION_Y + r1 * math.sin(a1), C.CEIL_H - d1),
             (r0 * math.cos(a1), MEDALLION_Y + r0 * math.sin(a1), C.CEIL_H - d0)]
        if r0 == 0.0:
            q = q[:3]
        ce.face(q, M_DARKWOOD, toward=(0, MEDALLION_Y, C.CEIL_H - 5))
# alcove ceiling (hipped planks)
rp = [(-ALC_R, ALC_EAVE), (-ALC_RIDGE_X, ALC_RIDGE), (ALC_RIDGE_X, ALC_RIDGE), (ALC_R, ALC_EAVE)]
for (xa, za), (xb, zb) in zip(rp[:-1], rp[1:]):
    ce.face([(xa, -ALC_WALL, za), (xb, -ALC_WALL, zb), (xb, -ALC_D, zb), (xa, -ALC_D, za)], M_CEIL,
            toward=(0, -1, 2))
ce.finish()

# =============================================================================
# DOORS, RELIEF, EXIT SIGNS
# =============================================================================
dr = Builder("Shell_Doors")


def half_disc(cx, z0, r, y, n=10):
    return [(cx + r * math.cos(math.pi * i / n), y, z0 + r * 0.62 * math.sin(math.pi * i / n)) for i in range(n + 1)]


def exit_sign(x, y, z, axis="y", facing=1):
    if axis == "y":
        ya, yb = sorted((y, y + facing * 0.045))
        dr.box((x - 0.17, ya, z), (x + 0.17, yb, z + 0.2), M_WHITE, skip="y-" if facing > 0 else "y+")
        yy = y + facing * 0.047
        dr.face([(x - 0.13, yy, z + 0.04), (x + 0.13, yy, z + 0.04), (x + 0.13, yy, z + 0.16),
                 (x - 0.13, yy, z + 0.16)], M_EXIT, n=(0, facing, 0))
    else:
        xa, xb = sorted((x, x + facing * 0.045))
        dr.box((xa, y - 0.17, z), (xb, y + 0.17, z + 0.2), M_WHITE, skip="x-" if facing > 0 else "x+")
        xx = x + facing * 0.047
        dr.face([(xx, y - 0.13, z + 0.04), (xx, y + 0.13, z + 0.04), (xx, y + 0.13, z + 0.16),
                 (xx, y - 0.13, z + 0.16)], M_EXIT, n=(facing, 0, 0))


def door_unit(xc, ywall, zfloor, w, h, leaves, depth=0.08, rosettes=False):
    """Casing + leaf slabs set `depth` behind the wall face (wall faces +Y)."""
    yd = ywall - depth
    c = CASING
    dr.box((xc - w / 2 - c, yd, zfloor), (xc - w / 2, ywall + 0.035, zfloor + h), M_TRIMWOOD, skip="z- y-")
    dr.box((xc + w / 2, yd, zfloor), (xc + w / 2 + c, ywall + 0.035, zfloor + h), M_TRIMWOOD, skip="z- y-")
    dr.box((xc - w / 2, yd, zfloor + h), (xc + w / 2, ywall + 0.035, zfloor + h + c), M_DOOR, skip="y-")
    for sx in (-1, 1):                         # corner blocks
        xa, xb = sorted((xc + sx * w / 2, xc + sx * (w / 2 + c + 0.01)))
        dr.box((xa, yd, zfloor + h), (xb, ywall + 0.05, zfloor + h + c + 0.01), M_DOOR, skip="y-")
        if rosettes:
            bx, bz = (xa + xb) / 2, zfloor + h + c / 2
            dr.face([(bx + 0.05 * math.cos(2 * math.pi * i / 12), ywall + 0.058, bz + 0.05 * math.sin(2 * math.pi * i / 12))
                     for i in range(12)], M_TRIMWOOD, n=(0, 1, 0))
    lw = w / leaves
    for k in range(leaves):
        x0 = xc - w / 2 + k * lw
        dr.face([(x0 + 0.003, yd, zfloor), (x0 + lw - 0.003, yd, zfloor), (x0 + lw - 0.003, yd, zfloor + h),
                 (x0 + 0.003, yd, zfloor + h)], M_DOOR, n=(0, 1, 0))
        st_ = 0.11 * lw / 0.9
        pw = (lw - 3 * st_) / 2
        yp = yd + 0.014
        for px in (x0 + st_, x0 + 2 * st_ + pw):
            for za, zb in ((0.10 * h, 0.52 * h), (0.52 * h + 0.08, 0.72 * h)):
                dr.box((px, yd, zfloor + za), (px + pw, yp, zfloor + zb), M_DOOR, skip="y-")
        fr_ = lw / 2 - st_
        fz = zfloor + 0.76 * h
        dr.face(half_disc(x0 + lw / 2, fz, fr_, yd + 0.004), M_GLASSDARK, n=(0, 1, 0))
        for ang in (45, 90, 135):                  # fan glazing bars
            ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang)) * 0.62
            dr.beam((x0 + lw / 2, yd + 0.008, fz), (x0 + lw / 2 + fr_ * ca, yd + 0.008, fz + fr_ * sa), 0.012, 0.014,
                    M_DOOR)
        hx = x0 + (lw - 0.06 if k == 0 else 0.06) if leaves == 2 else x0 + lw - 0.08
        dr.box((hx - 0.035, yd, zfloor + 0.90), (hx + 0.035, yd + 0.03, zfloor + 1.22), M_GOLD, skip="y-")


door_unit(0.0, -ALC_D, ALC_H, DDOOR_W, DDOOR_H, 2, rosettes=True)
# left back door: a deep doorway with two carpeted steps up to the door (IMG_7973)
door_unit(DOOR_L_X, 0.0, 0.30, SDOOR_W, SDOOR_H - 0.30, 1, depth=0.55)
for sx in (-1, 1):
    xj = DOOR_L_X + sx * SDOOR_W / 2
    dr.face([(xj, 0.0, 0.0), (xj, -0.55, 0.0), (xj, -0.55, SDOOR_H), (xj, 0.0, SDOOR_H)], M_DOOR, n=(-sx, 0, 0))
    xa, xb = sorted((xj, xj + sx * CASING))
    dr.box((xa, -0.02, 0.0), (xb, 0.035, 0.30), M_TRIMWOOD, skip="z- z+ y-")
dr.face([(DOOR_L_X - SDOOR_W / 2, 0.0, SDOOR_H), (DOOR_L_X + SDOOR_W / 2, 0.0, SDOOR_H),
         (DOOR_L_X + SDOOR_W / 2, -0.55, SDOOR_H), (DOOR_L_X - SDOOR_W / 2, -0.55, SDOOR_H)], M_DOOR, n=(0, 0, -1))
dr.box((DOOR_L_X - SDOOR_W / 2, -0.27, 0.0), (DOOR_L_X + SDOOR_W / 2, 0.0, 0.15), M_CARPET, skip="z- y- x- x+")
dr.box((DOOR_L_X - SDOOR_W / 2, -0.55, 0.0), (DOOR_L_X + SDOOR_W / 2, -0.27, 0.30), M_CARPET, skip="z- y- x- x+")
door_unit(DOOR_R_X, 0.0, 0.0, SDOOR_W, SDOOR_H, 1)


def emergency_sign(x, y, z, axis="y", facing=1):
    """EXIT sign with an emergency lamp each side."""
    exit_sign(x, y, z, axis, facing)
    for o in (-0.24, 0.24):
        if axis == "y":
            ya, yb = sorted((y, y + facing * 0.07))
            dr.box((x + o - 0.05, ya, z + 0.05), (x + o + 0.05, yb, z + 0.15), M_WHITE,
                   skip="y-" if facing > 0 else "y+")
        else:
            xa, xb = sorted((x, x + facing * 0.07))
            dr.box((xa, y + o - 0.05, z + 0.05), (xb, y + o + 0.05, z + 0.15), M_WHITE,
                   skip="x-" if facing > 0 else "x+")


sign_z = ALC_H + DDOOR_H + CASING + 0.16
emergency_sign(0.0, -ALC_D, sign_z)
emergency_sign(DOOR_L_X + 0.1, 0.0, SDOOR_H + CASING + 0.10)
emergency_sign(DOOR_R_X, 0.0, SDOOR_H + CASING + 0.10)
emergency_sign(W2, C.WINDOW_Y[-1] - C.WINDOW_W / 2 - REVEAL_R - 0.32, LAND_Z + 2.0, axis="x", facing=-1)
ryw = -ALC_D
dr.box((-0.36, ryw, sign_z + 0.24), (-0.26, ryw + 0.05, sign_z + 0.34), M_WHITE, skip="y-")     # dome camera
# copper relief: dark frame, and a small spotlight on the wall above it
rel_w, rel_h = RELIEF_W, RELIEF_H
rel_z = min(sign_z + 0.62, ALC_RIDGE - rel_h - 0.28)
dr.box((-rel_w / 2 - 0.025, ryw, rel_z - 0.025), (rel_w / 2 + 0.025, ryw + 0.03, rel_z + rel_h + 0.025), M_IRON,
       skip="y-")
dr.box((-0.03, ryw, rel_z + rel_h + 0.10), (0.03, ryw + 0.10, rel_z + rel_h + 0.20), M_GREY, skip="y-")
dr.finish()
plane_object("Icon_stmark_relief",   # named as the tour knows it (web/src/tour.json)
             [(-rel_w / 2, ryw + 0.034, rel_z), (rel_w / 2, ryw + 0.034, rel_z),
              (rel_w / 2, ryw + 0.034, rel_z + rel_h), (-rel_w / 2, ryw + 0.034, rel_z + rel_h)], M_RELIEF,
             lambda p: ((p.x + rel_w / 2) / rel_w, (p.z - rel_z) / rel_h))

# =============================================================================
# STAIR LANDING + RAILING (right-back corner)
# =============================================================================
st = Builder("Shell_Stair")
RAIL_H = 0.95
nw = 0.055
if CORNER_STAIR:
    land_y0 = 0.0

    def SP(u, v):               # u = distance down the stair from the landing edge, v = distance from the wall behind
        return (LAND_X - u, v)
else:
    land_y0 = C.WINDOW_Y[-1] - LAND_HALF

    def SP(u, v):               # stair runs back along the side wall
        return (W2 - v, land_y0 - u)


def sbox(u0, u1, v0, v1, z0, z1, mat, top=None):
    (xa, ya), (xb, yb) = SP(u0, v0), SP(u1, v1)
    st.box((min(xa, xb), min(ya, yb), z0), (max(xa, xb), max(ya, yb), z1), mat, skip="z-",
           mats={"z+": top} if top else None)


st.box((LAND_X, land_y0, 0), (W2, LAND_Y, LAND_Z), M_PINE, skip="z- x+", mats={"z+": M_OAKWOOD})
for i in range(1, STAIR_N):
    sbox((i - 1) * STAIR_GO, i * STAIR_GO, 0.0, STAIR_W - 0.02, 0.0, LAND_Z - i * STAIR_RISE, M_PINE, M_OAKWOOD)
u_low = (STAIR_N - 1) * STAIR_GO
# closed pine stringer on the nave side
pa, pb = SP(0.0, STAIR_W), SP(u_low + 0.06, STAIR_W)
st.face([(pa[0], pa[1], 0), (pb[0], pb[1], 0), (pb[0], pb[1], STAIR_RISE + 0.08), (pa[0], pa[1], LAND_Z + 0.06)],
        M_PINE, toward=(0, L / 2, 0.5))


def newel(xy, z0, h):
    x, y = xy
    st.box((x - nw, y - nw, z0), (x + nw, y + nw, z0 + h), M_OAKWOOD, skip="z-")
    st.box((x - nw - 0.015, y - nw - 0.015, z0 + h), (x + nw + 0.015, y + nw + 0.015, z0 + h + 0.04), M_OAKWOOD)


def rail_run(p0, p1, z0a, z0b):
    """Oak handrail + iron bottom bar + turned iron balusters from p0 to p1 (x, y)."""
    a = Vector((p0[0], p0[1], z0a + RAIL_H))
    b = Vector((p1[0], p1[1], z0b + RAIL_H))
    st.beam(a, b, 0.06, 0.05, M_OAKWOOD)
    st.beam(a - Vector((0, 0, RAIL_H - 0.10)), b - Vector((0, 0, RAIL_H - 0.10)), 0.02, 0.02, M_IRON)
    length = (Vector(p1) - Vector(p0)).length
    cnt = max(int(length / 0.125), 1)
    for k in range(1, cnt):
        t = k / cnt
        x, y = p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t
        z = z0a + (z0b - z0a) * t
        st.box((x - 0.007, y - 0.007, z + 0.10), (x + 0.007, y + 0.007, z + RAIL_H - 0.02), M_IRON, skip="z- z+")
        for kz in ((0.36, 0.60) if k % 2 == 0 else (0.48,)):     # knuckles of the turned balusters
            st.box((x - 0.017, y - 0.017, z + kz), (x + 0.017, y + 0.017, z + kz + 0.07), M_IRON)


c_top, c_low, c_far = SP(0.0, STAIR_W), SP(u_low + 0.02, STAIR_W), (LAND_X, LAND_Y)
newel(c_top, LAND_Z, RAIL_H + 0.2)
newel(c_far, LAND_Z, RAIL_H + 0.2)
newel(c_low, 0.0, RAIL_H + 0.25)
rail_run(c_top, c_far, LAND_Z, LAND_Z)
rail_run(c_far, (W2, LAND_Y), LAND_Z, LAND_Z)
rail_run(c_low, c_top, 0.1, LAND_Z)
if not CORNER_STAIR:            # landing edge beside the head of the stair
    rail_run((LAND_X, land_y0), (LAND_X + LAND_D - STAIR_W, land_y0), LAND_Z, LAND_Z)
# handrail on the wall beside the stair
wa, wb = SP(u_low, 0.06), SP(0.0, 0.06)
st.beam((wa[0], wa[1], 0.1 + RAIL_H), (wb[0], wb[1], LAND_Z + RAIL_H), 0.05, 0.05, M_OAKWOOD)
st.finish()

# =============================================================================
# SLOTS
# =============================================================================
for y, name in C.LEFT_SHRINES:
    if y < min(C.WINDOW_Y):      # photos: the back-most shrine hangs on the BACK wall
        e = empty("Slot_Shrine_L_" + name, (SHRINE_BACK_L_X, 0.0, C.SHRINE_Z), math.pi)
    else:
        e = empty("Slot_Shrine_L_" + name, (-W2, y, C.SHRINE_Z), math.pi / 2)
    e["texture"] = name
for y, name in C.RIGHT_SHRINES:
    if y < min(C.WINDOW_Y):
        e = empty("Slot_Shrine_R_" + name, (SHRINE_BACK_R_X, 0.0, C.SHRINE_Z + 0.35), math.pi)
    else:
        e = empty("Slot_Shrine_R_" + name, (W2, y, C.SHRINE_Z), -math.pi / 2)
    e["texture"] = name
empty("Slot_IconStand_L", (-1.4, -1.08, ALC_H), math.pi)
empty("Slot_IconStand_R", (1.4, -1.08, ALC_H), math.pi)

# =============================================================================
tris = 0
for ob in COL.objects:
    if ob.type == "MESH":
        ob.data.calc_loop_triangles()
        t = len(ob.data.loop_triangles)
        tris += t
        print("  %-28s %6d tris" % (ob.name, t))
print("SHELL TRIANGLES: %d" % tris)
C.save("shell")

# ---- previews (lights are added after saving, so they are not in the asset) ----
if "--no-render" not in sys.argv:
    only = [a.split("=")[1] for a in sys.argv if a.startswith("--only=")]
    scene = bpy.context.scene
    world = bpy.data.worlds.new("PreviewWorld")
    world.use_nodes = True
    bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
    bg.inputs[0].default_value = (0.02, 0.02, 0.025, 1)
    scene.world = world
    try:
        scene.view_settings.view_transform = "Standard"
    except TypeError:
        pass
    for y in [L * f for f in (0.1, 0.3, 0.5, 0.7, 0.9)]:
        for x in (-W2 * 0.5, W2 * 0.5):
            ld = bpy.data.lights.new("PreviewLight", "AREA")
            ld.energy = 110
            ld.size = 1.2
            ld.color = (1.0, 0.93, 0.82)
            lo = bpy.data.objects.new("PreviewLight", ld)
            lo.location = (x, y, C.WALL_H - 1.4)
            scene.collection.objects.link(lo)
    sl = bpy.data.lights.new("PreviewSanctuary", "POINT")
    sl.energy = float(os.environ.get("SHELL_SANCT_LIGHT", "25"))
    slo = bpy.data.objects.new("PreviewSanctuary", sl)
    slo.location = (0, FRONT_Y + SANCT_D * 0.4, C.ICONO_H)
    scene.collection.objects.link(slo)
    views = {
        "shell_altar": ((0.0, -0.6, 2.1), (0.0, L, 3.8), 14),
        "shell_back": ((0.0, C.CHORUS_Y - 3.0, 1.7), (0.0, 0.0, 3.2), 15),
        "shell_left": ((2.6, L * 0.52, 1.7), (-W2, L * 0.5, 3.6), 12),
        "shell_right": ((-2.0, 9.5, 1.6), (W2, 8.0, 3.4), 14),
        "shell_stair": ((0.3, C.WINDOW_Y[-1] + 3.5, 1.6), (W2 - 0.6, C.WINDOW_Y[-1] - 1.0, 2.2), 17),
        "shell_front": ((0.0, C.CHORUS_Y - 1.0, 1.7), (0.0, L, C.ICONO_H + 1.8), 22),
        "shell_arch": ((0.0, L / 3, 1.6), (0.0, L, C.ICONO_H + 1.6), 45),
        "shell_arch_chorus": ((-3.6, L - 2.6, 1.9), (2.5, FRONT_Y + 2.0, 6.4), 22),
        "shell_alcove": ((0.0, 4.5, 1.6), (0.0, -ALC_D, 3.0), 20),
    }
    for name, (loc, look, lens) in views.items():
        if only and name not in only:
            continue
        big = "--final" in sys.argv
        C.render_preview(name, loc, look, lens=lens, size=(960, 720) if big else (640, 480),
                         samples=48 if big else 32)
