"""Throne: the bishop's throne. Light golden oak, burgundy velvet, brass nails,
rope-twist posts and columns, hexagonal pierced canopy with ribbed dome + cross,
arched icon of Christ enthroned in the back.

Origin = floor centre of the footprint, front faces -Y.
Objects: `Throne` (oak, velvet, brass, shadow) and `Icon_throne_christ` (the icon, named as the tour knows it).
Run: Blender -b --python blender/assets/throne.py
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

NAME = "Throne"
common.reset_scene()
coll = common.collection(NAME)

# ---- proportions (reference/icons/20070525_185906_010.jpg, IMG_4806-4811) ----
HW = 0.475            # half width (0.95 m overall)
H = 3.30              # floor to top of the cross
PL_D = 0.92           # plinth depth; back of the throne is y=0 while building
Z_PL = 0.09           # plinth top
Z_SEAT = 0.50         # top of the cushion
Z_ARM = 0.86          # underside of the arm rail
Z_ARMT = 0.92         # top of the arm rail
PX, PY = 0.41, -0.555  # front arm posts
CX, CY = 0.41, -0.11   # tall columns (stand on the arm rails)
Z_COLT = 1.76         # top of the tall twist shafts
Z_CAPT = 1.96         # top of the column capitals
Z_CAN = 2.20          # underside of the canopy
R_CAN = 0.50          # canopy hexagon corner radius (flat faces front/back)
YC = -R_CAN * math.sqrt(3) / 2   # canopy centre (back flat on y=0)
IC_W, IC_H, IC_Z0 = 0.42, 0.84, 1.25

OAK, VELVET, BRASS, SHADOW = 0, 1, 2, 3
B = cv.Builder()


def nails(xf, w, h, sp=0.036, r=0.0065):
    """Brass upholstery nails round a w x h rectangle (local origin lower-left)."""
    B.mat = BRASS
    pts = []
    nx, ny = max(2, round(w / sp)), max(2, round(h / sp))
    for i in range(nx + 1):
        pts += [(w * i / nx, 0), (w * i / nx, h)]
    for j in range(1, ny):
        pts += [(0, h * j / ny), (w, h * j / ny)]
    for u, v in pts:
        cv.lathe(B, [(r, 0), (r * 0.72, r * 0.6), (0, r * 0.85)], 6, lambda p, u=u, v=v: xf(Vector((p[0] + u, p[1] + v, p[2]))))
    B.mat = OAK


def framed(xf, w, h, fw=0.035, t=0.012):
    for lo, hi in (((0, 0, 0), (w, fw, t)), ((0, h - fw, 0), (w, h, t)),
                   ((0, fw, 0), (fw, h - fw, t)), ((w - fw, fw, 0), (w, h - fw, t))):
        cv.box(B, lo, hi, xf, skip="-z")


# ---- plinth -------------------------------------------------------------------
cv.box(B, (-HW - 0.02, -PL_D, 0), (HW + 0.02, 0, Z_PL - 0.02), skip="-z")
cv.box(B, (-HW - 0.008, -PL_D + 0.012, Z_PL - 0.02), (HW + 0.008, 0, Z_PL), skip="-z")

# ---- back board, full height ---------------------------------------------------
YB = -0.05
cv.box(B, (-HW, YB, Z_PL), (HW, 0, Z_CAN), skip="-z+z")
for s in (-1, 1):   # chip-carved zigzag strip down each side edge
    n = 34
    xf = cv.side(s * HW, YB + 0.004 if s > 0 else -0.004, Z_PL + 0.04, s)
    cv.diamonds(B, xf, 1, n, 0.042, (Z_CAN - Z_PL - 0.08) / n, 0.006)

# ---- side walls, arm rails, front posts ---------------------------------------
for s in (-1, 1):
    xi, xo = s * 0.415, s * HW
    xa, xb = sorted((xi, xo))
    cv.box(B, (xa, PY + 0.065, Z_PL), (xb, YB, Z_ARM), skip="-z+z+y")
    # outside: framed panel with chip carving
    pw, ph = 0.40, 0.62
    if s > 0:
        oxf = cv.side(xo, PY + 0.085, Z_PL + 0.07, 1)
    else:
        oxf = cv.side(xo, PY + 0.085 + pw, Z_PL + 0.07, -1)
    framed(oxf, pw, ph, 0.04, 0.014)
    cv.diamonds(B, lambda p: oxf(Vector((p[0] + 0.06, p[1] + 0.06, p[2]))), 4, 7, 0.07, (ph - 0.12) / 7, 0.007, boss=0.004)
    # inside: velvet panel with nails
    vw, vh = 0.40, 0.29
    if s > 0:
        ixf = cv.side(xi, PY + 0.085 + vw, Z_SEAT + 0.03, -1)
    else:
        ixf = cv.side(xi, PY + 0.085, Z_SEAT + 0.03, 1)
    B.mat = VELVET
    cv.box(B, (0, 0, 0), (vw, vh, 0.012), ixf, skip="-z")
    nails(lambda p: ixf(Vector((p[0] + 0.012, p[1] + 0.012, p[2] + 0.012))), vw - 0.024, vh - 0.024)
    # arm rail with carved edge
    ra, rb = sorted((s * 0.34, s * (HW + 0.012)))
    cv.box(B, (ra, PY + 0.07, Z_ARM), (rb, 0, Z_ARMT))
    ln = -(PY + 0.08) - 0.06
    if s > 0:
        exf = cv.side(rb, PY + 0.08, Z_ARM + 0.008, 1)
        nxf = cv.side(ra, PY + 0.08 + ln, Z_ARM + 0.008, -1)
    else:
        exf = cv.side(ra, PY + 0.08 + ln, Z_ARM + 0.008, -1)
        nxf = cv.side(rb, PY + 0.08, Z_ARM + 0.008, 1)
    for f in (exf, nxf):
        cv.diamonds(B, f, 11, 1, ln / 11, Z_ARMT - Z_ARM - 0.016, 0.005)

    # front post: block, rope twist, rosette block, cap, ball finial
    px = s * PX
    cv.box(B, (px - 0.065, PY - 0.065, Z_PL), (px + 0.065, PY + 0.065, 0.20), skip="-z")
    cv.lathe(B, [(0.062, 0), (0.064, 0.012), (0.052, 0.03)], 14, cv.plane((px, PY, 0.20), X, Y))
    cv.twist(B, 0.05, 0.45, cv.plane((px, PY, 0.23), X, Y), lobes=5, ppl=4, turns_per_m=2.1, depth=0.2, hand=s)
    cv.lathe(B, [(0.05, 0), (0.062, 0.008), (0.062, 0.02)], 14, cv.plane((px, PY, 0.68), X, Y))
    cv.box(B, (px - 0.065, PY - 0.065, 0.70), (px + 0.065, PY + 0.065, Z_ARM), skip="+z")
    zm = (0.70 + Z_ARM) / 2
    cv.rosette(B, cv.front(px, zm, PY - 0.065), 0.05, 0.012, petals=4)
    cv.rosette(B, cv.plane((px + s * 0.065, PY, zm), Y * s, Z), 0.05, 0.012, petals=4)
    cv.rosette(B, cv.plane((px - s * 0.065, PY, zm), -Y * s, Z), 0.05, 0.012, petals=4)
    cv.box(B, (px - 0.078, PY - 0.078, Z_ARM), (px + 0.078, PY + 0.078, Z_ARMT))
    cv.diamonds(B, cv.front(px - 0.078, Z_ARM + 0.008, PY - 0.078), 4, 1, 0.039, Z_ARMT - Z_ARM - 0.016, 0.005)
    cv.box(B, (px - 0.055, PY - 0.055, Z_ARMT), (px + 0.055, PY + 0.055, Z_ARMT + 0.02), skip="-z")
    cv.ball_finial(B, cv.plane((px, PY, Z_ARMT + 0.02), X, Y), 0.06, segs=16)

# ---- seat: board, cushion, front apron with medallion -----------------------
cv.box(B, (-0.415, -0.60, Z_SEAT - 0.08), (0.415, YB, Z_SEAT - 0.05))
B.mat = VELVET
r0 = [Vector((x, y, Z_SEAT - 0.05)) for x, y in ((-0.405, -0.605), (0.405, -0.605), (0.405, YB - 0.02), (-0.405, YB - 0.02))]
r1 = [Vector((x, y, Z_SEAT - 0.012)) for x, y in ((-0.412, -0.612), (0.412, -0.612), (0.412, YB - 0.018), (-0.412, YB - 0.018))]
r2 = [Vector((x, y, Z_SEAT)) for x, y in ((-0.395, -0.595), (0.395, -0.595), (0.395, YB - 0.03), (-0.395, YB - 0.03))]
vr = cv.loft(B, [r0, r1, r2])
B.f(vr[-1])
B.mat = OAK
YA = -0.47
cv.box(B, (-0.415, YA, Z_PL), (0.415, YA + 0.03, Z_SEAT - 0.08), skip="-z+z")
axf = cv.front(-0.39, Z_PL + 0.03, YA)
framed(axf, 0.78, Z_SEAT - 0.08 - Z_PL - 0.05, 0.035, 0.012)
cv.rosette(B, cv.front(0, (Z_PL + Z_SEAT - 0.08) / 2, YA), 0.07, 0.014, petals=8, segs=18)

# ---- back: velvet, carved band, icon frame ----------------------------------
bw, bz0, bz1 = 0.71, Z_SEAT + 0.03, 1.03
bxf = cv.front(-bw / 2, bz0, YB)
B.mat = VELVET
cv.box(B, (0, 0, 0), (bw, bz1 - bz0, 0.018), bxf, skip="-z")
nails(lambda p: bxf(Vector((p[0] + 0.014, p[1] + 0.014, p[2] + 0.018))), bw - 0.028, bz1 - bz0 - 0.028)
# carved lattice band
gw = 0.66
gxf = cv.front(-gw / 2, 1.06, YB)
framed(gxf, gw, 0.11, 0.012, 0.01)
cv.diamonds(B, lambda p: gxf(Vector((p[0] + 0.012, p[1] + 0.012, p[2]))), 9, 1, (gw - 0.024) / 9, 0.086, 0.009, boss=0.006)
# raised field + rectangular moulding
FZ0, FZ1, FX = 1.19, 2.15, 0.33
cv.box(B, (-FX, YB - 0.012, FZ0), (FX, YB, FZ1), skip="+y")
yf = YB - 0.012
m = 0.02
pts = [Vector((-FX + m, yf, FZ0 + m)), Vector((-FX + m, yf, FZ1 - m)), Vector((FX - m, yf, FZ1 - m)), Vector((FX - m, yf, FZ0 + m))]
nrm = [Vector((-1, 0, -1)), Vector((-1, 0, 1)), Vector((1, 0, 1)), Vector((1, 0, -1))]
cv.sweep(B, pts, nrm, -Y, [(0, 0), (0.018, 0), (0.018, 0.012), (0.008, 0.018), (-0.012, 0.01), (-0.012, 0)], closed=True)
# arched carved border round the icon
SEG = 24
ap, an = cv.arch_path(0, yf, IC_Z0, IC_W, IC_H, segs=SEG, closed=True)
bwid = 0.05
cv.sweep(B, ap, an, -Y, [(0, 0), (bwid, 0), (bwid, 0.012), (bwid - 0.008, 0.02), (0.008, 0.02), (0, 0.012)], closed=True)
zs = IC_Z0 + IC_H - IC_W / 2
ncell = 15
for s in (-1, 1):   # leaf-and-bead border modules up the sides
    x0 = -IC_W / 2 - bwid + 0.008 if s < 0 else IC_W / 2 + 0.008
    cv.diamonds(B, cv.front(x0, IC_Z0, yf - 0.02), 1, ncell, bwid - 0.016, (zs - IC_Z0) / ncell, 0.006)
na = 18
ra = IC_W / 2 + 0.008
cv.diamonds(B, cv.arc((0, yf - 0.02, zs), ra), na, 1, PI * ra / na, bwid - 0.016, 0.006)
cv.diamonds(B, cv.front(-IC_W / 2, IC_Z0 - bwid + 0.008, yf - 0.02), 10, 1, IC_W / 10, bwid - 0.016, 0.006)
for s in (-1, 1):   # spandrel rosettes
    cv.rosette(B, cv.front(s * 0.235, FZ1 - 0.115, yf), 0.05, 0.012, petals=8, segs=16)

# ---- tall rope-twist columns, capitals, brackets ----------------------------
for s in (-1, 1):
    cx = s * CX
    cv.box(B, (cx - 0.06, CY - 0.06, Z_ARMT), (cx + 0.06, CY + 0.06, Z_ARMT + 0.025), skip="-z")
    cv.lathe(B, [(0.056, 0), (0.058, 0.012), (0.046, 0.03)], 14, cv.plane((cx, CY, Z_ARMT + 0.025), X, Y))
    z0 = Z_ARMT + 0.055
    cv.twist(B, 0.045, Z_COLT - z0, cv.plane((cx, CY, z0), X, Y), lobes=5, ppl=4, turns_per_m=2.3, depth=0.2, hand=-s)
    cv.lathe(B, [(0.045, 0), (0.057, 0.008), (0.057, 0.022), (0.05, 0.03)], 14, cv.plane((cx, CY, Z_COLT), X, Y))
    zc0, zc1 = Z_COLT + 0.03, Z_CAPT - 0.045
    hb = 0.062
    cv.box(B, (cx - hb, CY - hb, zc0), (cx + hb, CY + hb, zc1))
    zm = (zc0 + zc1) / 2
    cv.rosette(B, cv.front(cx, zm, CY - hb), 0.048, 0.012, petals=4)
    cv.rosette(B, cv.plane((cx + s * hb, CY, zm), Y * s, Z), 0.048, 0.012, petals=4)
    cv.rosette(B, cv.plane((cx - s * hb, CY, zm), -Y * s, Z), 0.048, 0.012, petals=4)
    cv.box(B, (cx - hb - 0.012, CY - hb - 0.012, zc1), (cx + hb + 0.012, CY + hb + 0.012, zc1 + 0.02), skip="-z")
    cv.box(B, (cx - hb - 0.024, CY - hb - 0.024, zc1 + 0.02), (cx + hb + 0.024, min(CY + hb + 0.024, YB), Z_CAPT))
    cv.diamonds(B, cv.front(cx - hb - 0.024, zc1 + 0.024, CY - hb - 0.024), 5, 1, (2 * hb + 0.048) / 5, 0.017, 0.004)
    # upright stub + bracket that sweeps forward under the canopy
    cv.box(B, (cx - 0.04, CY - 0.03, Z_CAPT), (cx + 0.04, YB, Z_CAN), skip="-z+z+y")
    ry, rz = 0.30, Z_CAN - Z_CAPT - 0.035
    bp, bn = [], []
    for i in range(11):
        t = PI / 2 * i / 10
        bp.append(Vector((cx, CY - 0.03 - ry * (1 - math.cos(t)), Z_CAPT + rz * math.sin(t))))
        bn.append(Vector((0, math.cos(t), math.sin(t))).normalized())
    cv.sweep(B, bp, bn, X, [(-0.04, -0.035), (0.0, -0.035), (0.0, 0.035), (-0.04, 0.035)])
    for sd in (-1, 1):   # leaf carving on the bracket cheeks
        for i in range(1, 10, 2):
            t = PI / 2 * i / 10
            c = Vector((cx + sd * 0.035, CY - 0.03 - (ry + 0.02) * (1 - math.cos(t)) + 0.02, Z_CAPT + (rz - 0.02) * math.sin(t)))
            tan = Vector((0, -math.sin(t), math.cos(t)))
            nor = Vector((0, math.cos(t), math.sin(t)))
            u, v = (tan, nor) if sd > 0 else (nor, tan)
            if u.cross(v).x * sd < 0:
                u, v = v, u
            cv.diamonds(B, cv.plane(c - u * 0.016 - v * 0.016, u, v), 1, 1, 0.032, 0.032, 0.005)
    cv.lathe(B, [(0, -0.04), (0.028, -0.03), (0.04, 0), (0.028, 0.03), (0, 0.04)], 10,
             cv.plane((cx, CY - 0.03 - ry - 0.02, Z_CAN - 0.045), Y, Z))

# ---- hexagonal canopy --------------------------------------------------------
def hexv(R, z):
    return [Vector((R * math.cos(PI / 3 * i), YC + R * math.sin(PI / 3 * i), z)) for i in range(6)]


def hexlayer(R, z0, z1, back=True):
    cv.prism(B, cv.ngon(R, 6, 0.0, (0, YC)), z1 - z0, cv.plane((0, 0, z0), X, Y), back=back)


def hside(i, R, z, inset=0.0, dw=0.0):
    """Frame on side i of a hexagon of corner radius R: u along the side,
    v up, w outward. Side 4 faces the front (-Y), side 1 is the back."""
    P = hexv(R, z)
    a, b = P[i], P[(i + 1) % 6]
    d = (b - a).normalized()
    base = cv.plane(a + d * inset, d, Z)
    return lambda p: base(Vector((p[0], p[1], p[2] + dw)))


VIS = [0, 2, 3, 4, 5]          # every side but the back
z = Z_CAN
hexlayer(R_CAN, z, z + 0.03)
B.mat = SHADOW
cv.prism(B, cv.ngon(0.36, 6, 0.0, (0, YC)), 0.002, cv.plane((0, 0, z - 0.002), X, Y))
B.mat = OAK
for i in VIS:
    cv.tabs(B, hside(i, R_CAN, z, 0.0, -0.014), 7, R_CAN / 7, 0.03, 0.014, drop=0.028)
z += 0.03
R1 = 0.47
hexlayer(R1, z, z + 0.07, back=False)
for i in VIS:
    cv.diamonds(B, hside(i, R1, z + 0.008, 0.012), 8, 1, (R1 - 0.024) / 8, 0.054, 0.006)
z += 0.07
hexlayer(R_CAN, z, z + 0.025)
z += 0.025
# pierced tier
PH = 0.13
B.mat = SHADOW
hexlayer(R1 - 0.02, z, z + PH, back=False)
B.mat = OAK
for i in VIS:
    cv.pierced(B, hside(i, R1, z + 0.004, 0.03), 6, 2, (R1 - 0.06) / 6, (PH - 0.008) / 2, 0.012, N=16, hole=0.86, lobe=0.4)
for p in hexv(R1, z):
    cv.lathe(B, [(0.03, 0), (0.03, PH)], 8, cv.plane(p, X, Y))
z += PH
hexlayer(R_CAN + 0.005, z, z + 0.025)
for i in VIS:
    cv.tabs(B, hside(i, R_CAN + 0.005, z, 0.0, -0.012), 9, (R_CAN + 0.005) / 9, 0.022, 0.012, drop=0.02, seg=3)
z += 0.025
R2 = 0.48
hexlayer(R2, z, z + 0.08, back=False)
for i in VIS:
    cv.diamonds(B, hside(i, R2, z + 0.008, 0.012), 7, 1, (R2 - 0.024) / 7, 0.064, 0.007)
    cv.rosette(B, hside(i, R2, z + 0.04, R2 / 2, 0.004), 0.03, 0.014, petals=6, ring=False)
z += 0.08
hexlayer(R_CAN + 0.01, z, z + 0.025)
z += 0.025
for i in VIS:
    cv.merlons(B, hside(i, R_CAN, z, 0.0, -0.016), 8, R_CAN / 8, 0.046, 0.05, 0.014)
for i, p in enumerate(hexv(R_CAN - 0.02, z)):
    if i in (1, 2):
        continue
    cv.ball_finial(B, cv.plane(p, X, Y), 0.03, segs=10)
ZR = z
R3 = 0.235
cv.loft(B, [hexv(R_CAN - 0.03, ZR), hexv(R3 + 0.03, ZR + 0.045)])
# drum
z = ZR + 0.045
DH = 0.17
B.mat = SHADOW
hexlayer(R3 - 0.02, z, z + DH, back=False)
B.mat = OAK
for i in range(6):
    cv.pierced(B, hside(i, R3, z + 0.004, 0.02), 3, 2, (R3 - 0.04) / 3, (DH - 0.008) / 2, 0.012, N=16, hole=0.86, lobe=0.4)
for p in hexv(R3, z):
    cv.lathe(B, [(0.02, 0), (0.02, DH)], 8, cv.plane(p, X, Y))
z += DH
hexlayer(R3 + 0.03, z, z + 0.025)
z += 0.025
for i in range(6):
    cv.merlons(B, hside(i, R3 + 0.025, z, 0.0, -0.012), 5, (R3 + 0.025) / 5, 0.036, 0.035, 0.01)

# ---- ribbed pierced dome, knob, cross -----------------------------------------
RD = 0.215
ZCROSS = H - 0.19
HD = ZCROSS - 0.045 - z          # dome height
EMAX = math.radians(74)


def dome(p):
    a = p[0] / RD
    e = p[1] / RD
    r = RD + p[2]
    return Vector((r * math.cos(e) * math.cos(a), YC + r * math.cos(e) * math.sin(a), z + HD / RD * r * math.sin(e)))


B.mat = SHADOW
cv.lathe(B, [((RD - 0.004) * math.cos(EMAX * i / 6), HD * (RD - 0.004) / RD * math.sin(EMAX * i / 6)) for i in range(7)],
         12, cv.plane((0, YC, z), X, Y))
B.mat = OAK
ND = 12
cv.pierced(B, dome, ND, 3, 2 * PI * RD / ND, RD * EMAX / 3, 0.012, N=16, hole=0.84, lobe=0.4)
for k in range(ND):
    uc = 2 * PI * RD * k / ND
    for j in range(4):
        cv.box(B, (uc - 0.011, RD * EMAX * j / 4, 0.004), (uc + 0.011, RD * EMAX * (j + 1) / 4, 0.026), dome, skip="-z")
e0 = EMAX - 0.02
cap = [((RD + 0.014) * math.cos(e0 + (PI / 2 - e0) * i / 3) if i < 3 else 0.0,
        HD / RD * (RD + 0.014) * math.sin(e0 + (PI / 2 - e0) * i / 3)) for i in range(4)]
cv.lathe(B, cap, 12, cv.plane((0, YC, z), X, Y))
zk = z + HD / RD * (RD + 0.014)
cv.lathe(B, [(0.022, -0.006), (0.03, 0.006), (0.018, 0.018), (0.03, 0.03), (0.022, 0.042), (0.012, 0.05)], 10,
         cv.plane((0, YC, zk), X, Y))
cv.cross(B, cv.plane((0, YC, zk + 0.048), X, Z), H - zk - 0.048 - 0.02, 0.125, 0.02, 0.022)

mats = [
    cv.wood("Throne_oak", (0.36, 0.155, 0.04), (0.68, 0.37, 0.125), rough=0.36, coat=0.3, grain=(5.0, 5.0, 0.6)),
    cv.velvet("Throne_velvet", (0.30, 0.01, 0.03)),
    common.flat_material("Throne_brass", (0.83, 0.62, 0.28), 0.3, 1.0),
    common.flat_material("Throne_shadow", (0.10, 0.04, 0.012), 0.8),
]
cv.finish(B, NAME, coll, mats)

icon_mat = common.image_material("Throne_icon", "icons/throne_christ.jpg", fallback=(0.72, 0.52, 0.18), rough=0.35)
cv.icon_plane("Icon_throne_christ", coll, cv.arch_poly(IC_W, IC_H, SEG), cv.front(-IC_W / 2, IC_Z0, yf - 0.002), icon_mat)

cv.shift(coll, PL_D / 2)            # origin -> floor centre of the footprint
print("TRIS", NAME, cv.tri_count(coll), "footprint", 2 * R_CAN, "x", PL_D, "h", H)
common.save("throne")

# ---- preview -----------------------------------------------------------------
FINAL = bool(os.environ.get("CT_FINAL"))
size = (720, 960) if FINAL else (480, 640)
smp = 48 if FINAL else 32
cv.studio(PL_D / 2 + 0.002, key=(-2.6, -4.4, 3.4), fill=(3.0, -3.4, 1.4), key_w=300, fill_w=110)
if os.environ.get("CT_BACKFACE"):
    cv.backface_check(coll)
    common.render_preview("throne_backface", (2.4, -5.2, 2.3), (0, 0, 1.65), lens=42, size=size, samples=16)
else:
    common.render_preview("throne", (0.0, -7.2, 1.6), (0, 0, 1.66), lens=55, size=size, samples=smp)
    common.render_preview("throne_side", (2.6, -5.0, 2.4), (0, 0, 1.65), lens=42, size=size, samples=smp)
    common.render_preview("throne_seat", (1.1, -2.6, 1.9), (0, 0.1, 0.75), lens=35, size=size, samples=smp)
    common.render_preview("throne_canopy", (1.3, -2.6, 1.7), (0, 0, 2.6), lens=45, size=size, samples=smp)
