"""Shrine: wall-mounted carved mahogany icon shrine (instanced 8x).

Origin = centre of the bottom of the bracket shelf, at the wall face.
Front faces -Y; the wall is the plane y = 0; z = 0 is the underside.
Objects: `Shrine` (wood, shadow, brass, flowers) and `Icon_slot` (the icon
panel, set back inside the frame; assembly swaps its material).
Run: Blender -b --python blender/assets/shrine.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy
from mathutils import Vector
import common
import _carved as cv
from _carved import X, Y, Z, PI

NAME = "Shrine"
common.reset_scene()
coll = common.collection(NAME)

# ---- proportions (all derived from the common.py envelope) ----------------
W = common.SHRINE_W                 # shelf width
H = common.SHRINE_H                 # shelf underside to top of the cross
k = W                               # the design below is drawn on a 1 x 1 unit
kz = H / 1.87                       # sheet (shelf width 1, top of cross 1.87)
BW = 0.43 * k                       # half width of the body / hood
D = 0.285 * k                       # hood depth from the wall
BOX_D = 0.14 * k                    # depth of the back box (pilasters)
COLX, COLY = 0.37 * k, -0.215 * k   # column centres
Z_SHELF = 0.17 * kz                 # top of the shelf
Z_COL0, Z_COL1 = 0.30 * kz, 0.985 * kz
Z_CAP = 1.11 * kz                   # top of the capital block
Z_SPR = 1.17 * kz                   # arch springing / top of abacus
R_IN = 0.31 * k                     # hood opening radius
R_BAND = 0.42 * k                   # outer radius of the pierced arch band
Z_SIDE = 1.49 * kz                  # top of the hood at its sides
Z_CROWN = 1.645 * kz                 # top of the segmental roof at the centre
IC_W, IC_Z0, IC_Z1 = 0.60 * k, 0.225 * kz, 1.035 * kz   # ~0.75 aspect like the painted panels

WOOD, SHADOW, BRASS, FLOWER = 0, 1, 2, 3
B = cv.Builder()

# ---- bracket + stepped shelf -------------------------------------------------
B.mat = SHADOW
cv.box(B, (-0.42 * k, -0.20 * k, 0), (0.42 * k, 0, 0.07 * kz), skip="+y+z")
B.mat = WOOD
for hw, dp, z0, z1 in ((0.50, 0.31, 0.07, 0.105), (0.485, 0.295, 0.105, 0.138), (0.47, 0.28, 0.138, 0.17)):
    cv.box(B, (-hw * k, -dp * k, z0 * kz), (hw * k, 0, z1 * kz), skip="+y")

# ---- back box: board, reeded pilasters, icon frame -------------------------
cv.box(B, (-0.336 * k, -0.085 * k, Z_SHELF), (0.336 * k, 0, Z_SPR), skip="+y-z-x+x")
for s in (-1, 1):
    x0, x1 = sorted((s * 0.336 * k, s * BW))
    cv.box(B, (x0, -BOX_D, Z_SHELF), (x1, 0, Z_CAP), skip="+y-z")
    # reeds on the front and on the outer side
    for i in range(3):
        cx = s * (0.353 + 0.027 * i) * k
        cv.box(B, (cx - 0.009 * k, -BOX_D - 0.007, Z_SHELF + 0.03), (cx + 0.009 * k, -BOX_D, Z_CAP - 0.03), skip="+y")
    for i in range(3):
        cy = -(0.03 + 0.04 * i) * k
        xa, xb = sorted((s * BW, s * (BW + 0.007)))
        cv.box(B, (xa, cy - 0.011 * k, Z_SHELF + 0.03), (xb, cy + 0.011 * k, Z_CAP - 0.03),
               skip="-x" if s > 0 else "+x")

fy = -0.10 * k
hx = IC_W / 2
pts = [Vector((-hx, fy, IC_Z0)), Vector((-hx, fy, IC_Z1)), Vector((hx, fy, IC_Z1)), Vector((hx, fy, IC_Z0))]
nrm = [Vector((-1, 0, -1)), Vector((-1, 0, 1)), Vector((1, 0, 1)), Vector((1, 0, -1))]
cv.sweep(B, pts, nrm, -Y, [(0, -0.02), (0.035 * k, -0.02), (0.035 * k, 0.022), (0.02 * k, 0.03), (0, 0.012)],
         closed=True)

# lintel over the icon with a chip-carved band
cv.box(B, (-0.336 * k, -BOX_D - 0.02, Z_CAP - 0.045 * kz), (0.336 * k, -0.08 * k, Z_SPR), skip="+y")
cv.diamonds(B, cv.front(-0.30 * k, Z_CAP - 0.035 * kz, -BOX_D - 0.02), 12, 1, 0.05 * k, 0.05 * kz, 0.006)

# ---- columns ---------------------------------------------------------------
for s in (-1, 1):
    cx = s * COLX
    for hw, z0, z1 in ((0.07, 0.17, 0.205), (0.06, 0.205, 0.235), (0.052, 0.235, 0.265)):
        cv.box(B, (cx - hw * k, COLY - hw * k, z0 * kz), (cx + hw * k, COLY + hw * k, z1 * kz), skip="-z")
    base = cv.plane((cx, COLY, 0.265 * kz), X, Y)
    r = 0.04 * k
    cv.lathe(B, [(r * 1.25, 0), (r * 1.3, 0.012), (r * 1.05, 0.024), (r * 0.95, Z_COL0 - 0.265 * kz)], 10, base)
    cv.twist(B, r, Z_COL1 - Z_COL0, cv.plane((cx, COLY, Z_COL0), X, Y), lobes=3, ppl=4,
             turns_per_m=4.4 / k, depth=0.2, hand=s, ring_twist=0.75)
    cv.lathe(B, [(r * 0.95, 0), (r * 1.2, 0.008), (r * 1.2, 0.02), (r * 0.9, 0.028)], 10,
             cv.plane((cx, COLY, Z_COL1 - 0.004), X, Y))
    # capital block with medallions, then a stepped abacus
    hb = 0.056 * k
    zb0, zb1 = Z_COL1 + 0.02, Z_CAP
    cv.box(B, (cx - hb, COLY - hb, zb0), (cx + hb, COLY + hb, zb1))
    zm = (zb0 + zb1) / 2
    cv.cross_medallion(B, cv.plane((cx, COLY - hb, zm), X, Z), hb * 0.8, 0.012)
    cv.rosette(B, cv.plane((cx + s * hb, COLY, zm), Y * s, Z), hb * 0.74, 0.008, petals=4, segs=10)
    cv.box(B, (cx - hb - 0.008, COLY - hb - 0.008, zb1), (cx + hb + 0.008, COLY + hb + 0.008, zb1 + 0.025 * kz), skip="+z")
    cv.box(B, (cx - hb - 0.018, COLY - hb - 0.018, zb1 + 0.025 * kz), (cx + hb + 0.018, COLY + hb + 0.018, Z_SPR))

# ---- hood ------------------------------------------------------------------
cz = Z_SPR
SEG = 16
# segmental roof: circle through (+-(BW+0.03), Z_SIDE) and (0, Z_CROWN)
c_half, sag = BW + 0.03 * k, Z_CROWN - Z_SIDE
R_TOP = (c_half ** 2 + sag ** 2) / (2 * sag)
ZC_TOP = Z_CROWN - R_TOP


def top_z(x):
    return ZC_TOP + math.sqrt(max(R_TOP ** 2 - x ** 2, 0))


# side walls with a square pierced panel
for s in (-1, 1):
    x0, x1 = sorted((s * (BW - 0.04 * k), s * BW))
    cv.box(B, (x0, -D, cz), (x1, 0, top_z(BW) + 0.004), skip="+y+z-y")  # front = spandrel plate
    pw = 0.19 * k
    xf = cv.side(s * (BW + 0.001), -D / 2 - s * pw / 2, cz + 0.07 * kz, s)
    B.mat = SHADOW
    cv.prism(B, [(0, 0), (pw, 0), (pw, pw), (0, pw)], 0.001, xf, back=False)
    B.mat = WOOD
    cv.pierced(B, xf, 3, 3, pw / 3, pw / 3, 0.008, N=8, hole=0.9, lobe=0.45, walls=False)
    fw = 0.014
    for lo, hi in (((-fw, -fw, 0), (pw + fw, 0, 0.016)), ((-fw, pw, 0), (pw + fw, pw + fw, 0.016)),
                   ((-fw, 0, 0), (0, pw, 0.016)), ((pw, 0, 0), (pw + fw, pw, 0.016))):
        cv.box(B, lo, hi, xf, skip="-z")

# barrel soffit (faces the axis) from the lunette plane to the front
ring_f, ring_b = [], []
for i in range(SEG + 1):
    a = PI - PI * i / SEG
    ring_f.append(Vector((R_IN * math.cos(a), -D + 0.02, cz + R_IN * math.sin(a))))
    ring_b.append(Vector((R_IN * math.cos(a), -BOX_D + 0.01, cz + R_IN * math.sin(a))))
cv.loft(B, [ring_b, ring_f], close=False)

# back of the recess (dark) + pierced lunette with vase
B.mat = SHADOW
yb = -BOX_D + 0.012
vs = [B.v(p) for p in [Vector((R_IN * math.cos(PI * i / SEG), yb, cz + R_IN * math.sin(PI * i / SEG))) for i in range(SEG + 1)]]
B.f(vs)
B.mat = WOOD
R0 = 0.085 * k
lun = cv.arc((0, yb + 0.005, cz + 0.005), R0)   # 8 mm plate, 3 mm proud of the dark back
cv.pierced(B, lun, 14, 3, PI * R0 / 14, 0.17 * k / 3, 0.008, N=8, hole=0.9, lobe=0.45, walls=False)
ap, an = cv.arch_path(0, yb - 0.012, cz, 2 * 0.262 * k, 0.262 * k, segs=SEG)
cv.sweep(B, ap[1:-1], an[1:-1], -Y, [(0, 0), (0.028 * k, 0), (0.028 * k, 0.012), (0.012 * k, 0.02), (0, 0.012)])
cv.lathe(B, [(0.03 * k, 0), (0.022 * k, 0.012), (0.04 * k, 0.04), (0.07 * k, 0.075), (0.075 * k, 0.085), (0, 0.085)],
         8, cv.plane((0, yb - 0.006, cz), X, Y), a0=PI, a1=2 * PI)

# front face: pierced band over a dark backing, solid carved spandrels above
T = 0.014
B.mat = SHADOW
bi = [Vector((R_IN * math.cos(PI - PI * i / SEG), -D + T + 0.002, cz + R_IN * math.sin(PI - PI * i / SEG))) for i in range(SEG + 1)]
bo = [Vector((R_BAND * math.cos(PI - PI * i / SEG), -D + T + 0.002, cz + R_BAND * math.sin(PI - PI * i / SEG))) for i in range(SEG + 1)]
cv.loft(B, [bi, bo], close=False)
B.mat = WOOD
NB = 22
band = cv.arc((0, -D + T, cz), R_IN + 0.004)
cv.pierced(B, band, NB, 2, PI * (R_IN + 0.004) / NB, (R_BAND - R_IN - 0.008) / 2, T, N=8, hole=0.9, lobe=0.45, walls=False)
# cusped (scalloped) inner edge
NS = 13
cv.tabs(B, cv.arc((0, -D + 0.022, cz), R_IN + 0.002), NS, PI * (R_IN + 0.002) / NS, 0.036 * k, 0.022, drop=0.03 * k, seg=3)
# rim beads on both sides of the band
for rr in (R_BAND,):
    p2, n2 = cv.arch_path(0, -D, cz, 2 * rr, rr, segs=SEG)
    cv.sweep(B, p2[1:-1], n2[1:-1], -Y, [(-0.007, 0), (0.007, 0), (0.007, 0.008), (-0.007, 0.008)])
# solid spandrels: radial strip from the band to the outline
angs = sorted(set([PI * i / SEG for i in range(SEG + 1)] +
                  [math.atan2(top_z(BW) - cz, BW), PI - math.atan2(top_z(BW) - cz, BW)]), reverse=True)
inner, outer = [], []
for a in angs:
    c, s_ = math.cos(a), math.sin(a)
    t = BW / abs(c) if abs(c) > 1e-6 else 1e9
    # ray vs roof circle
    dz = cz - ZC_TOP
    bq = s_ * dz
    t2 = -bq + math.sqrt(bq * bq - (dz * dz - R_TOP ** 2))
    t = min(t, t2)
    inner.append(Vector((R_BAND * c, -D, cz + R_BAND * s_)))
    outer.append(Vector((t * c, -D, cz + t * s_)))
cv.loft(B, [inner, outer], close=False)
for s in (-1, 1):
    cv.rosette(B, cv.front(s * (BW - 0.068 * k), cz + 0.305 * kz, -D), 0.046 * k, 0.012, petals=6, segs=10)

# roof slab following the segmental curve, with overhang
half = math.asin(c_half / R_TOP)
NR = 12
rp, rn = [], []
for i in range(NR + 1):
    a = PI / 2 + half - 2 * half * i / NR
    rn.append(Vector((math.cos(a), 0, math.sin(a))))
    rp.append(Vector((R_TOP * math.cos(a), 0, ZC_TOP + R_TOP * math.sin(a))))
cv.sweep(B, rp, rn, -Y, [(0, 0), (0.016, 0), (0.016, D + 0.008), (0.03, D + 0.012), (0.03, D + 0.028),
                          (0.014, D + 0.028), (0, D + 0.012)])
# pierced cresting along the roof front
RC = R_TOP + 0.03
NCR = 20
hc = half * 0.93
arcl = 2 * hc * RC
crest = cv.arc((0, -D + 0.004, ZC_TOP), RC, a0=PI / 2 + hc)
cv.pierced(B, crest, NCR, 1, arcl / NCR, 0.055 * kz, 0.012, N=8, hole=0.88, lobe=0.45, walls=False)
B.mat = SHADOW
cb = cv.arc((0, -D + 0.017, ZC_TOP), RC, a0=PI / 2 + hc)
cv.prism(B, [(0, 0), (arcl / 2, 0), (arcl / 2, 0.055 * kz), (0, 0.055 * kz)], 0.001, cb, back=False)
cv.prism(B, [(arcl / 2, 0), (arcl, 0), (arcl, 0.055 * kz), (arcl / 2, 0.055 * kz)], 0.001, cb, back=False)
B.mat = WOOD

# urn finials at the corners, cross on the crown
for s in (-1, 1):
    fx = s * (BW - 0.01 * k)
    zf = top_z(BW) + 0.02
    cv.cbox(B, (fx, -D + 0.035 * k, zf + 0.012), (0.075 * k, 0.075 * k, 0.03))
    cv.urn(B, cv.plane((fx, -D + 0.035 * k, zf + 0.027), X, Y), 0.036 * k, 0.115 * kz)
zt = Z_CROWN + 0.03
cv.cbox(B, (0, -D + 0.02, zt + 0.012), (0.07 * k, 0.05 * k, 0.05))
cv.cross(B, cv.plane((0, -D + 0.02, zt + 0.03), X, Z), H - zt - 0.03 - 0.019 * k, 0.115 * k, 0.018, 0.02 * k)

# ---- shelf dressing: engraved brass plate + white flowers -----------------
B.mat = BRASS
cv.box(B, (-0.10 * k, -0.262 * k, Z_SHELF), (0.10 * k, -0.25 * k, Z_SHELF + 0.045), skip="-z")
B.mat = FLOWER
for fx, fr in ((-0.24, 0.032), (-0.185, 0.026), (0.17, 0.03), (0.225, 0.034), (0.275, 0.025)):
    cv.lathe(B, [(0, 0), (fr * 0.8 * k, 0.008), (fr * k, 0.022), (fr * 0.6 * k, 0.04), (0, 0.045)], 5,
             cv.plane((fx * k, -0.235 * k, Z_SHELF), X, Y))

mats = [
    cv.wood("Shrine_mahogany", (0.085, 0.02, 0.008), (0.25, 0.068, 0.024), rough=0.24, coat=0.6,
            grain=(5.0, 5.0, 0.7)),
    common.flat_material("Shrine_shadow", (0.012, 0.004, 0.003), 0.7),
    common.flat_material("Shrine_brass", (0.72, 0.52, 0.22), 0.35, 1.0),
    common.flat_material("Shrine_flowers", (0.86, 0.82, 0.7), 0.8),
]
body = cv.finish(B, NAME, coll, mats)

icon_mat = common.image_material("Icon_annunciation", "icons/annunciation.jpg", fallback=(0.72, 0.52, 0.18), rough=0.35)
cv.icon_plane("Icon_slot", coll, [(0, 0), (IC_W, 0), (IC_W, IC_Z1 - IC_Z0), (0, IC_Z1 - IC_Z0)],
              cv.front(-IC_W / 2, IC_Z0, -0.088 * k), icon_mat)

print("TRIS", NAME, cv.tri_count(coll))
common.save("shrine")

# ---- preview -----------------------------------------------------------------
cv.studio(0.002, floor=False, key=(-1.6, -3.0, 2.2), fill=(2.2, -2.2, 0.2), key_w=120, fill_w=45, size=2.0)
if os.environ.get("CT_BACKFACE"):
    cv.backface_check(coll)
    common.render_preview("shrine_backface", (1.7, -2.9, -0.6), (0, -0.12, 0.93), lens=50, size=(720, 960), samples=16)
else:
    FINAL = bool(os.environ.get("CT_FINAL"))
    size = (720, 960) if FINAL else (480, 640)
    smp = 48 if FINAL else 32
    common.render_preview("shrine", (0.0, -3.6, 0.9), (0, -0.1, 0.93), lens=58, size=size, samples=smp)
    common.render_preview("shrine_side", (1.7, -2.9, -0.6), (0, -0.12, 0.93), lens=50, size=size, samples=smp)
