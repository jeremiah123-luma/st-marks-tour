"""IconStand: free-standing canopied icon stand (one each side of the back
doors). Dark walnut cabinet with star-inlay panels, sand tray on the deck,
four turned posts carrying a barrel-vault canopy with mother-of-pearl banding
and an inlaid cross.

Origin = floor centre of the footprint, front faces -Y.
Objects: `IconStand` and `Icon_slot` (icon panel; assembly swaps its material).
Run: Blender -b --python blender/assets/icon_stand.py
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

NAME = "IconStand"
common.reset_scene()
coll = common.collection(NAME)

# ---- proportions (measured off reference/IMG_7902 + batch3/IMG_7975) --------
HW = 0.60            # half width of the plinth
D = 0.60             # depth of the plinth (back at y=0 while building)
Z_PL = 0.12          # plinth top
Z_CAB = 0.93         # cabinet body top (deck top is Z_DECK); about wainscot height
Z_DECK = 0.98
Z_BLK = 1.10         # top of the post pedestal blocks
Z_CAPB = 2.13        # underside of the post top blocks
Z_ENT = 2.25         # underside of the cornice
Z_SPR = 2.31         # springing of the barrel vault
R_V = 0.40           # inner radius of the vault
T_V = 0.045          # vault shell thickness
H_TOP = 3.02         # top of the cross
PX, PYF, PYB = 0.52, -0.52, -0.085   # post centres
IC_W, IC_H, IC_Z0 = 0.50, 0.86, 1.05

WOOD, PEARL, STEEL, SAND, SHADOW = 0, 1, 2, 3, 4
B = cv.Builder()


def star8(xf, a, h, inlay=True):
    """8-pointed star boss (two squares) centred on the local origin, with
    mother-of-pearl lozenges."""
    B.mat = WOOD
    cv.prism(B, [(-a, -a), (a, -a), (a, a), (-a, a)], h, xf, back=False)
    d = a * 1.36
    cv.prism(B, [(0, -d), (d, 0), (0, d), (-d, 0)], h * 1.35, xf, back=False)
    if inlay:
        B.mat = PEARL
        z0 = h * 1.35
        up = lambda p: xf(Vector((p[0], p[1], p[2] + z0)))
        q = a * 0.34
        cv.prism(B, [(0, -q), (q, 0), (0, q), (-q, 0)], 0.0015, up, back=False)
        for sx, sy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            cx, cy = sx * a * 0.78, sy * a * 0.78
            r = a * 0.2
            cv.prism(B, [(cx, cy - r), (cx + r, cy), (cx, cy + r), (cx - r, cy)], 0.0015, up, back=False)
        B.mat = WOOD


def bevel_bar(xf, x0, y0, x1, y1, h, ins=0.012):
    """Raised bevelled bar (frustum) on a panel."""
    b = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    t = [(x0 + ins, y0 + ins), (x1 - ins, y0 + ins), (x1 - ins, y1 - ins), (x0 + ins, y1 - ins)]
    vb = [B.v(xf(Vector((p[0], p[1], 0)))) for p in b]
    vt = [B.v(xf(Vector((p[0], p[1], h)))) for p in t]
    for i in range(4):
        j = (i + 1) % 4
        B.f([vb[i], vb[j], vt[j], vt[i]])
    B.f(vt)


def door_panel(xf, w, h):
    """Cabinet door: framed field, bevelled bar top and bottom, star centre."""
    fw = 0.045
    for lo, hi in (((0, 0, 0), (w, fw, 0.014)), ((0, h - fw, 0), (w, h, 0.014)),
                   ((0, fw, 0), (fw, h - fw, 0.014)), ((w - fw, fw, 0), (w, h - fw, 0.014))):
        cv.box(B, lo, hi, xf, skip="-z")
    bw = w - 2 * fw - 0.06
    x0 = (w - bw) / 2
    bevel_bar(xf, x0, fw + 0.035, x0 + bw, fw + 0.115, 0.016)
    bevel_bar(xf, x0, h - fw - 0.115, x0 + bw, h - fw - 0.035, 0.016)
    c = lambda p: xf(Vector((p[0] + w / 2, p[1] + h / 2, p[2])))
    a = min(bw, h - 2 * fw - 0.36) / 2 / 1.36
    star8(c, a, 0.012)
    # four inlaid diagonal slips round the star
    B.mat = PEARL
    for sx in (-1, 1):
        for sy in (-1, 1):
            ox, oy = sx * a * 0.62, sy * a * 0.62
            l, t2 = a * 0.34, a * 0.07
            dx, dy = sx * 0.7071, sy * 0.7071
            px, py = -dy, dx
            poly = [(ox - dx * l - px * t2, oy - dy * l - py * t2), (ox + dx * l - px * t2, oy + dy * l - py * t2),
                    (ox + dx * l + px * t2, oy + dy * l + py * t2), (ox - dx * l + px * t2, oy - dy * l + py * t2)]
            if sum(poly[i][0] * poly[(i + 1) % 4][1] - poly[(i + 1) % 4][0] * poly[i][1] for i in range(4)) < 0:
                poly = poly[::-1]
            up = lambda p: c((p[0], p[1], p[2] + 0.0165))
            cv.prism(B, poly, 0.0015, up, back=False)
    B.mat = WOOD


# ---- plinth + cabinet --------------------------------------------------------
cv.box(B, (-HW, -D, 0), (HW, 0, Z_PL - 0.03), skip="-z")
cv.box(B, (-HW + 0.012, -D + 0.012, Z_PL - 0.03), (HW - 0.012, 0, Z_PL), skip="-z")
CW, CD = HW - 0.03, D - 0.03
cv.box(B, (-CW, -CD, Z_PL), (CW, 0, Z_CAB), skip="-z+z")
ph = Z_CAB - Z_PL - 0.05
pw = CW - 0.045
for s in (-1, 1):
    door_panel(cv.front(0.012 if s > 0 else -0.012 - pw, Z_PL + 0.025, -CD), pw, ph)
    sw = (CD - 0.05) / 2
    for i in range(2):
        y0 = -CD + 0.02 + i * (sw + 0.01)
        if s > 0:
            door_panel(cv.side(CW, y0, Z_PL + 0.025, 1), sw, ph)
        else:
            door_panel(cv.side(-CW, y0 + sw, Z_PL + 0.025, -1), sw, ph)
# deck with a moulded edge
cv.box(B, (-HW + 0.005, -D + 0.005, Z_CAB), (HW - 0.005, 0, Z_CAB + 0.02), skip="+z")
cv.box(B, (-HW - 0.01, -D - 0.01, Z_CAB + 0.02), (HW + 0.01, 0, Z_DECK))

# ---- sand tray on the deck -----------------------------------------------
B.mat = STEEL
tx, ty0, ty1 = 0.26, -0.40, -0.16
for lo, hi in (((-tx, ty0, Z_DECK), (tx, ty0 + 0.012, Z_DECK + 0.03)), ((-tx, ty1 - 0.012, Z_DECK), (tx, ty1, Z_DECK + 0.03)),
               ((-tx, ty0 + 0.012, Z_DECK), (-tx + 0.012, ty1 - 0.012, Z_DECK + 0.03)),
               ((tx - 0.012, ty0 + 0.012, Z_DECK), (tx, ty1 - 0.012, Z_DECK + 0.03))):
    cv.box(B, lo, hi, skip="-z")
B.mat = SAND
cv.prism(B, [(-tx + 0.012, ty0 + 0.012), (tx - 0.012, ty0 + 0.012), (tx - 0.012, ty1 - 0.012), (-tx + 0.012, ty1 - 0.012)],
         0.018, cv.plane((0, 0, Z_DECK), X, Y), back=False)
B.mat = WOOD

# ---- back panel: board, star strips, header -------------------------------
BX = 0.47
YB = -0.05
cv.box(B, (-BX, YB, Z_DECK), (BX, 0, Z_SPR), skip="+y-z")
# semicircular tympanum inside the vault
SEG = 20
B.f([B.v(Vector((R_V * math.cos(PI * i / SEG), YB, Z_SPR + R_V * math.sin(PI * i / SEG)))) for i in range(SEG + 1)])
# icon surround: thin raised frame
hx = IC_W / 2
fz0, fz1 = IC_Z0 - 0.03, IC_Z0 + IC_H + 0.03
for lo, hi in (((-hx - 0.03, YB - 0.012, fz0), (hx + 0.03, YB, IC_Z0)), ((-hx - 0.03, YB - 0.012, IC_Z0), (-hx, YB, fz1)),
               ((hx, YB - 0.012, IC_Z0), (hx + 0.03, YB, fz1))):
    cv.box(B, lo, hi, skip="+y")
# flanking strips of five stars
n_st = 5
pitch = (IC_H + 0.02) / n_st
for s in (-1, 1):
    cx = s * (hx + 0.03 + (BX - hx - 0.03) / 2)
    cv.box(B, (cx - 0.078, YB - 0.008, IC_Z0 - 0.02), (cx + 0.078, YB, IC_Z0 + IC_H + 0.02), skip="+y")
    for i in range(n_st):
        star8(cv.front(cx, IC_Z0 - 0.01 + (i + 0.5) * pitch, YB - 0.008), 0.05, 0.01)
    star8(cv.front(s * 0.19, IC_Z0 + IC_H + 0.085, YB), 0.036, 0.008)
star8(cv.front(0, Z_SPR + 0.12, YB), 0.075, 0.012)

# ---- posts -----------------------------------------------------------------
L = Z_CAPB - Z_BLK
prof = [(0.046, 0), (0.05, 0.015), (0.04, 0.03), (0.03, 0.05), (0.043, 0.07), (0.043, 0.085), (0.03, 0.10),
        (0.035, 0.15), (0.034, L - 0.17), (0.029, L - 0.12), (0.041, L - 0.10), (0.041, L - 0.085),
        (0.028, L - 0.07), (0.037, L - 0.04), (0.047, L - 0.02), (0.047, L)]
for sx in (-1, 1):
    for py in (PYF, PYB):
        cx = sx * PX
        hb = 0.058
        cv.box(B, (cx - hb, py - hb, Z_DECK), (cx + hb, py + hb, Z_BLK), skip="-z")
        cv.box(B, (cx - hb, py - hb, Z_CAPB), (cx + hb, py + hb, Z_ENT), skip="+z")
        cv.lathe(B, prof, 12, cv.plane((cx, py, Z_BLK), X, Y))
        B.mat = PEARL
        for zb in (0.19, L - 0.24):
            cv.lathe(B, [(0.0362, zb), (0.0362, zb + 0.022)], 12, cv.plane((cx, py, Z_BLK), X, Y))
        if py == PYF:
            for zc in ((Z_DECK + Z_BLK) / 2, (Z_CAPB + Z_ENT) / 2):
                q = 0.03
                cv.prism(B, [(0, -q), (q, 0), (0, q), (-q, 0)], 0.0015, cv.front(cx, zc, py - hb), back=False)
                cv.prism(B, [(0, -q), (q, 0), (0, q), (-q, 0)], 0.0015,
                         cv.plane((cx + sx * hb, py, zc), Y * sx, Z), back=False)
        B.mat = WOOD

# ---- canopy: side beams, cornice wings, barrel vault ----------------------
YF = -D - 0.02                      # canopy front plane
XO = HW + 0.04                      # cornice half width
for s in (-1, 1):
    xa, xb = sorted((s * (R_V + T_V * 0.4), s * (PX + 0.058)))
    cv.box(B, (xa, PYF - 0.058, Z_ENT), (xb, 0, Z_SPR - 0.02), skip="+z")           # beam / soffit block
    xa, xb = sorted((s * (R_V + T_V * 0.4), s * (XO - 0.02)))
    cv.box(B, (xa, YF + 0.012, Z_SPR - 0.02), (xb, 0, Z_SPR + 0.012), skip="-z")
    xa, xb = sorted((s * (R_V + T_V * 0.4), s * XO))
    cv.box(B, (xa, YF, Z_SPR + 0.012), (xb, 0, Z_SPR + 0.05), skip="")
vp, vn = [], []
for i in range(SEG + 1):
    a = PI - PI * i / SEG
    vn.append(Vector((math.cos(a), 0, math.sin(a))))
    vp.append(Vector((R_V * math.cos(a), 0, Z_SPR + R_V * math.sin(a))))
cv.sweep(B, vp, vn, -Y, [(0, 0), (T_V, 0), (T_V, -YF), (0, -YF)])
# raised face band + mother-of-pearl tiles: wings then round the arch
band_w = 0.036
for s in (-1, 1):
    x0 = s * (R_V + T_V + 0.01)
    x1 = s * (XO - 0.008)
    xa, xb = sorted((x0, x1))
    n = 5
    B.mat = PEARL
    for i in range(n):
        u0 = xa + (xb - xa) * (i + 0.12) / n
        u1 = xa + (xb - xa) * (i + 0.88) / n
        cv.box(B, (u0, YF - 0.0015, Z_SPR + 0.02), (u1, YF, Z_SPR + 0.043), skip="+y")
    B.mat = WOOD
RB = R_V + (T_V - band_w) / 2
arcx = cv.arc((0, YF, Z_SPR), RB)
n = 22
al = PI * RB
B.mat = PEARL
for i in range(n):
    cv.box(B, (al * (i + 0.14) / n, 0.007, 0), (al * (i + 0.86) / n, band_w - 0.007, 0.0015), arcx, skip="-z")
B.mat = WOOD

# ---- cross on the crown, inlaid ---------------------------------------------
zc0 = Z_SPR + R_V + T_V
ch = H_TOP - zc0
yc = YF + 0.03
cxf = cv.plane((0, yc, zc0), X, Z)
bar = 0.04
cv.cross(B, cxf, ch, ch * 0.62, 0.028, bar, bud=False)
B.mat = PEARL
fr = cv.plane((0, yc - 0.014, zc0), X, Z)
nt = 9
for i in range(nt):
    cv.box(B, (-bar * 0.28, ch * (i + 0.15) / nt, 0), (bar * 0.28, ch * (i + 0.85) / nt, 0.0015), fr, skip="-z")
arm = ch * 0.62
for s in (-1, 1):
    for i in range(3):
        u0 = s * (bar / 2 + (arm / 2 - bar / 2) * (i + 0.15) / 3)
        u1 = s * (bar / 2 + (arm / 2 - bar / 2) * (i + 0.85) / 3)
        ua, ub = sorted((u0, u1))
        cv.box(B, (ua, ch * 0.68 - bar * 0.28, 0), (ub, ch * 0.68 + bar * 0.28, 0.0015), fr, skip="-z")
B.mat = WOOD

mats = [
    cv.wood("Stand_walnut", (0.03, 0.011, 0.006), (0.13, 0.05, 0.022), rough=0.26, coat=0.5, grain=(5.0, 5.0, 0.7)),
    common.flat_material("Stand_pearl", (0.86, 0.85, 0.78), 0.22),
    common.flat_material("Stand_steel", (0.55, 0.56, 0.57), 0.35, 1.0),
    common.flat_material("Stand_sand", (0.62, 0.55, 0.42), 0.95),
    common.flat_material("Stand_shadow", (0.012, 0.005, 0.003), 0.7),
]
cv.finish(B, NAME, coll, mats)

icon_mat = common.image_material("Icon_stand_preview", "icons/theotokos.jpg", fallback=(0.72, 0.52, 0.18), rough=0.35)
cv.icon_plane("Icon_slot", coll, cv.arch_poly(IC_W, IC_H, 16), cv.front(-IC_W / 2, IC_Z0, YB - 0.006), icon_mat)

DEPTH = D + 0.02                    # plinth + canopy overhang
cv.shift(coll, DEPTH / 2)           # origin -> floor centre of the footprint
print("TRIS", NAME, cv.tri_count(coll), "footprint", 2 * (HW + 0.04), "x", DEPTH, "h", H_TOP)
common.save("icon_stand")

# ---- preview -----------------------------------------------------------------
cv.studio(DEPTH / 2 + 0.002, key=(-2.4, -4.2, 3.2), fill=(3.0, -3.2, 1.4), key_w=420, fill_w=150)
if os.environ.get("CT_BACKFACE"):
    cv.backface_check(coll)
    common.render_preview("icon_stand_backface", (2.6, -4.6, 1.9), (0, 0, 1.5), lens=45, size=(720, 960), samples=16)
else:
    common.render_preview("icon_stand", (0.0, -6.0, 1.5), (0, 0, 1.52), lens=50, size=(720, 960), samples=48)
    common.render_preview("icon_stand_side", (2.6, -4.6, 1.9), (0, 0, 1.5), lens=45, size=(720, 960), samples=48)
