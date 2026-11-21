"""ChandelierDome: the very large shallow crystal bowl over the chorus.

From IMG_7928 (seen from almost directly below): a wide bead-wrapped rim, then
a shallow bowl (depth about a third of the diameter) of about 23 perfectly
regular concentric necklaces of identical round faceted crystals, touching
along each ring, a thin wire hoop between rings, down to a small finial.
Above the rim a low cone of fine bead strands rises to a bead-wrapped crown
(IMG_7905 side view; in IMG_7928 the crown shows above the near rim, which
puts it well above the rim plane).
Origin = the hang point (top of the crown); the body hangs down -Z.
Run: Blender -b --python blender/assets/chandelier_dome.py
"""
import os
import sys
import math
import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import chandelier_lib as L

NAME = "ChandelierDome"
R = 1.5               # design radius; everything below is drawn at this size
SCALE = (common.NAVE_W / 4) / (2 * R)   # then scaled so the dome is a quarter of the nave width
DEPTH = 0.98          # bowl depth below the rim (about a third of the diameter)
CONE_H = 0.85         # crown ring down to the rim
R_TOP = 0.36          # top ring of the cone
BALL_TOP, BALL_BOT = 0.078, 0.060      # crystal diameter at the rim / at the bottom
RING_GAP = 1.16       # ring-to-ring pitch in crystal diameters
CONE_STRANDS = 44
CONE_BEADS = 26


def build():
    coll = common.collection(NAME)
    xcoll = L.export_collection(NAME + "_export")
    cmat = L.crystal_material()
    protos = [L.proto_bead(NAME + "_bead", 3, cmat),
              L.proto_ico(NAME + "_ball", cmat),
              L.proto_drop(NAME + "_drop", cmat),
              L.proto_lens(NAME + "_bandlens", 4, cmat)]
    cr = L.Crystals(5)
    fr = L.Frame()
    bd = L.Frame()

    z_top = -0.30                 # top ring of the cone (bottom of the crown)
    z_ring = z_top - CONE_H       # top of the rim band
    rim_h = 0.13
    z_bowl = z_ring - rim_h + 0.02

    # crown: chrome knob + bead-wrapped egg
    fr.lathe([(0, 0), (0.05, -0.01), (0.06, -0.06), (0.03, -0.09)], 12)
    bd.lathe([(0.03, -0.08), (0.11, -0.11), (0.155, -0.19), (0.15, -0.27)], 20)
    fr.lathe([(0.15, -0.27), (R_TOP, z_top), (R_TOP, z_top - 0.05)], 28)
    # low cone of fine strands
    ln = math.hypot(R - R_TOP, CONE_H) / CONE_BEADS
    for i in range(CONE_STRANDS):
        cr.strand(2 * math.pi * i / CONE_STRANDS, R_TOP, z_top - 0.05, R - 0.03, z_ring + 0.01, CONE_BEADS, 0.6 * ln)
    # rim: wide bead-wrapped band with a row of small crystals under it
    bd.bead_band(R, z_ring, rim_h, 0.035, 72)
    n = int(2 * math.pi * R / 0.040)
    cr.lens_ring(R - 0.005, z_ring - rim_h - 0.02, 1, 0, n, 0.038, 0.038, 0.03, kind=3)

    # the bowl
    a = R * 0.975

    def prof(t):
        ang = math.radians(4 + 85 * t)
        return a * math.cos(ang), z_bowl - DEPTH * math.sin(ang)

    rings = L.bowl_rings(cr, fr, prof, BALL_TOP, BALL_BOT, RING_GAP, 1.0, hoop_seg=56, hoop=0.0035)
    zf = z_bowl - DEPTH
    fr.lathe([(0.07, zf + 0.03), (0.085, zf), (0.03, zf - 0.03)], 12)
    cr.add((0, 0, zf - 0.085), (1, 0, 0), (0, 0, 1), (0.11, 0.11, 0.12), 1)

    # stem + candle bulbs inside the bowl
    fr.lathe([(0.018, -0.09), (0.018, zf + 0.03)], 6)
    spots = L.ring_spots(1.0, z_bowl - 0.12, 12) + L.ring_spots(0.6, z_bowl - 0.40, 8, 0.5)
    spots += L.ring_spots(0.25, z_bowl - 0.65, 4)
    k = SCALE
    cr.rescale(k)
    frame = fr.finish(NAME + "_frame", coll, L.chrome_material(), scale=k)
    bands = bd.finish(NAME + "_bands", coll, L.band_material(), scale=k)
    blb = L.bulbs(NAME + "_bulbs", coll, [tuple(c * k for c in p) for p in spots], 0.032 * k)
    L.build_crystals(NAME, cr, protos, coll, xcoll)
    for ob in (frame, bands, blb):
        xcoll.objects.link(ob)
    coll["height"] = -(zf - 0.15) * k
    coll["light_z"] = (z_bowl - 0.3) * k
    coll["ring_z"] = z_ring * k
    print("TRIS %s: %d  (crystals %d, bowl rings %d, height %.2f m, dia %.2f m, bowl depth %.2f m)" % (
        NAME, L.tri_count(xcoll), len(cr.pos), rings, coll["height"], 2 * R * k, DEPTH * k))
    return coll


def main():
    common.reset_scene()
    coll = build()
    common.save("chandelier_dome")

    # ---- previews (not saved)
    k = SCALE
    li = L.warm_light("pv", 250)
    li.location = (0, 0, coll["light_z"])
    bpy.context.scene.collection.objects.link(li)
    # side view
    L.preview_settings()
    common.render_preview("chandelier_dome", (0, -7.5 * k, -1.0 * k), (0, 0, -1.2 * k), lens=50, size=(640, 480), samples=32)
    # from below, the IMG_7928 view: dark grey ceiling behind
    L.preview_settings(bg=(0.09, 0.09, 0.10), strength=2.0)
    rz = coll["ring_z"]
    common.render_preview("chandelier_dome_below", (0, -3.0, rz - 3.3), (0, 0.0, rz - 0.1), lens=46,
                          size=(640, 624), samples=32)
    import subprocess
    conv = "/opt/ImageMagick/bin/convert"
    tmp = os.path.join(common.PREVIEWS, "_ref_dome.png")
    subprocess.run([conv, os.path.join(common.ROOT, "reference", "IMG_7928.jpg"), "-auto-orient", "-crop",
                    "1600x1560+610+90", "+repage", "-resize", "640x624", tmp], stderr=subprocess.DEVNULL)
    L.side_by_side("compare_dome", [tmp, os.path.join(common.PREVIEWS, "chandelier_dome_below.png")], 624)
    if os.path.exists(tmp):
        os.remove(tmp)


main()
