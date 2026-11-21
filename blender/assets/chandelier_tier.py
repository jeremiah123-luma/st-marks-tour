"""ChandelierTier + ChandelierTierSmall: tiered empire-style crystal chandeliers.

Read off MVIMG_20190817_111919 / _111953 and IMG_7905, top to bottom:
bead-wrapped crown with a few drops, a narrow column of fine bead strands, a
bead-wrapped ring, a wider skirt of fine strands, the wide bead-wrapped main
ring with a short bead curtain and pendant drops, then a bowl of about nine
concentric necklaces of large round crystals down to one ball at the bottom.

Origin = the hang point (top of the crown, where the rod meets it); the body
hangs down -Z. chandelier_layout.py adds the rod up to the ceiling.
Run: Blender -b --python blender/assets/chandelier_tier.py
"""
import os
import sys
import math
import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import chandelier_lib as L

# R = main ring radius. n* = strands, b* = beads per strand.
LARGE = dict(name="ChandelierTier", seed=11, R=0.54, bead_n=4, ball_n=0,
             n1=30, b1=17, n2=72, b2=15, n3=72, b3=3, drops=24, ball=0.115, seg=40, bulbs=6)
SMALL = dict(name="ChandelierTierSmall", seed=23, R=0.47, bead_n=3, ball_n=6,
             n1=22, b1=13, n2=50, b2=12, n3=50, b3=2, drops=18, ball=0.125, seg=32, bulbs=5)


def build(P):
    name, R = P["name"], P["R"]
    coll = common.collection(name)
    xcoll = L.export_collection(name + "_export")
    cmat = L.crystal_material()
    protos = [L.proto_bead(name + "_bead", P["bead_n"], cmat),
              (L.proto_lens(name + "_ball", P["ball_n"], cmat) if P["ball_n"] else L.proto_ico(name + "_ball", cmat)),
              L.proto_drop(name + "_drop", cmat),
              L.proto_lens(name + "_bandlens", 4, cmat)]
    cr = L.Crystals(P["seed"])
    fr = L.Frame()          # chrome
    bd = L.Frame()          # bead-wrapped rings
    seg = P["seg"]

    # radii and heights in units of R, top to bottom
    r_cr = 0.25 * R                                   # crown
    r1a, r1b = 0.185 * R, 0.25 * R                    # narrow column, top / bottom
    r2 = 0.52 * R                                     # second ring
    r2b = 0.63 * R                                    # bottom of the skirt
    z_cr = -0.10 * R
    z1a, z1b = -0.32 * R, -1.12 * R
    z2 = -1.02 * R                                    # top of the second ring
    z2a, z2b = -1.15 * R, -1.98 * R
    z3 = -1.89 * R                                    # top of the main ring
    z3b = z3 - 0.17 * R
    zc = z3b - 0.14 * R                               # bottom of the bead curtain
    depth = 0.86 * R

    def strands(n, beads, ra, za, rb, zb, phase=0.0):
        ln = math.hypot(rb - ra, zb - za) / beads
        w = min(0.78 * ln, 0.80 * 2 * math.pi * ra / n)
        for i in range(n):
            cr.strand(2 * math.pi * (i + phase) / n, ra, za, rb, zb, beads, w)

    # crown: chrome knob, bead-wrapped cap, a few drops under its rim
    fr.lathe([(0, 0), (0.05 * R, -0.01 * R), (0.06 * R, -0.07 * R), (0.03 * R, z_cr)], 12)
    bd.lathe([(0.04 * R, z_cr + 0.01 * R), (0.75 * r_cr, z_cr - 0.02 * R), (r_cr, z_cr - 0.08 * R),
              (r_cr, z_cr - 0.17 * R), (0.8 * r_cr, z_cr - 0.20 * R)], 20)
    cr.drops(r_cr - 0.004, z_cr - 0.20 * R, 10, 0.05 * R, 0.13 * R)
    # narrow column
    strands(P["n1"], P["b1"], r1a, z1a, r1b, z1b)
    # second ring + skirt
    bd.bead_band(r2, z2, 0.13 * R, 0.03 * R, seg)
    fr.lathe([(r1b, z2 - 0.07 * R), (r2, z2 - 0.07 * R)], 24)        # plate carrying the ring
    strands(P["n2"], P["b2"], r2 - 0.01 * R, z2a, r2b, z2b, 0.5)
    # main ring, bead curtain, pendant drops
    bd.bead_band(R, z3, 0.17 * R, 0.035 * R, seg)
    strands(P["n3"], P["b3"], 0.985 * R, z3b, 0.985 * R, zc)
    cr.drops(1.0 * R, z3b - 0.01 * R, P["drops"], 0.05 * R, 0.13 * R, 0.5)

    # bowl of large round crystals
    def prof(t):
        return 0.95 * R * (1 - t ** 1.6) ** 0.75 + 0.012 * R, zc - 0.02 * R - depth * t

    d = P["ball"] * R
    rings = L.bowl_rings(cr, fr, prof, d, 0.9 * d, 1.08, 1.0 if not P["ball_n"] else 0.62, hoop_seg=seg, hoop=0.0025, s_end=0.97)
    zf = zc - 0.02 * R - depth
    cr.add((0, 0, zf - 0.02 * R), (1, 0, 0), (0, 0, 1), (1.25 * d, 1.25 * d, 1.25 * d), 1)

    # centre stem + candle bulbs
    fr.lathe([(0.011, z_cr), (0.011, zf + 0.05 * R)], 6)
    nb = P["bulbs"]
    spots = L.ring_spots(0.34 * R, z2b + 0.30 * R, nb) + L.ring_spots(0.12 * R, z1b + 0.30 * R, 3, 0.5)
    spots += L.ring_spots(0.45 * R, zc - 0.22 * depth, nb, 0.5)
    frame = fr.finish(name + "_frame", coll, L.chrome_material())
    bands = bd.finish(name + "_bands", coll, L.band_material())
    blb = L.bulbs(name + "_bulbs", coll, spots, 0.020)
    L.build_crystals(name, cr, protos, coll, xcoll)
    for ob in (frame, bands, blb):
        xcoll.objects.link(ob)
    coll["height"] = -(zf - 0.1 * R)
    coll["light_z"] = z3
    print("TRIS %s: %d  (crystals %d, bowl rings %d, height %.2f m, dia %.2f m)" % (
        name, L.tri_count(xcoll), len(cr.pos), rings, coll["height"], 2 * R))
    return coll


def main():
    common.reset_scene()
    big = build(LARGE)
    small = build(SMALL)
    common.save("chandelier_tier")

    # ---- previews (not saved)
    L.preview_settings()
    for ob in small.objects:
        ob.location.x += 1.5
    for c, x, pw in ((big, 0, 50), (small, 1.5, 40)):
        li = L.warm_light("pv", pw)
        li.location = (x, 0, c["light_z"])
        bpy.context.scene.collection.objects.link(li)
    common.render_preview("chandelier_tier", (0.75, -5.2, -1.6), (0.75, 0, -0.75), lens=50, size=(640, 480), samples=32)
    # same view as the 2019 photo: from below and to one side, dark wood ceiling behind
    L.preview_settings(bg=(0.10, 0.045, 0.035), strength=1.5)
    for ob in small.objects:
        ob.hide_render = True
    h = big["height"]
    common.render_preview("chandelier_tier_view", (1.3, -4.3, -h * 0.5 - 1.6), (0, 0, -h * 0.5), lens=70,
                          size=(498, 640), samples=32)
    ref = os.path.join(common.ROOT, "reference")
    tmp = os.path.join(common.PREVIEWS, "_ref_")
    import subprocess
    conv = "/opt/ImageMagick/bin/convert"
    crops = [("icons/MVIMG_20190817_111953.jpg", "560x720+960+0", "a"), ("IMG_7905.jpg", "420x520+380+820", "b")]
    panels = []
    for rel, geo, tag in crops:
        out = tmp + tag + ".png"
        subprocess.run([conv, os.path.join(ref, rel), "-auto-orient", "-crop", geo, "+repage", out],
                       stderr=subprocess.DEVNULL)
        panels.append(out)
    L.side_by_side("compare_tier", panels + [os.path.join(common.PREVIEWS, "chandelier_tier_view.png")])
    for p in panels:
        if os.path.exists(p):
            os.remove(p)


main()
