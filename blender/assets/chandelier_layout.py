"""Chandeliers: places the dome and the tiered chandeliers in the nave.

Count from IMG_7905 / IMG_7928 and the 2019 side-wall photos
(MVIMG_20190817_111919 / _111953): 1 dome + 3 large tiered + 8 small tiered.
- the dome hangs over the chorus, halfway between the chorus edge and the
  iconostasis, its bottom DOME_CLEAR above the chorus floor;
- three rows of left / centre / right tiered chandeliers hang from the ceiling
  beams at common.BRACKET_Y[1], [2], [3] (centre = large, sides = small);
- one more pair of small side ones hangs from the front beam
  (common.BRACKET_Y[0]), either side of the dome (IMG_7905 shows four per
  side; IMG_7928 shows the front right one beside the dome).

Each chandelier = one collection instance (empty) + a rod up to the ceiling +
one near-neutral warm-white point light. Saves chandeliers.blend.
Run after chandelier_dome.py and chandelier_tier.py:
  Blender -b --python blender/assets/chandelier_layout.py
"""
import os
import sys
import bpy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common
import chandelier_lib as L

ROW_Y = common.BRACKET_Y[1:4]               # centre + side rows, front -> back
FRONT_SIDE_Y = common.BRACKET_Y[0]          # the side pair beside the dome hangs from the front beam
DOME_Y = (common.CHORUS_Y + common.NAVE_L) / 2
DOME_CLEAR = 4.3                            # dome bottom above the chorus floor
SIDE_X = 0.37 * common.NAVE_W               # side rows: where the flat ceiling meets the cove
# rod lengths measured in MVIMG_20190817_111919 against the window glass: a
# side chandelier's crown is about 2.6 m below the ceiling.
ROD = {"ChandelierTier": 1.25, "ChandelierTierSmall": 1.40}   # flat ceiling at 6.6 m
MIN_ROD = 0.35
POWER = {"ChandelierDome": 2000.0, "ChandelierTier": 600.0, "ChandelierTierSmall": 450.0}   # W, retune in assembly


def append(blend, names):
    path = os.path.join(common.ASSETS, blend)
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.collections = [n for n in names if n in src.collections]
    return {c.name: c for c in dst.collections}


def rod_mesh(name, length):
    fr = L.Frame()
    fr.lathe([(0.009, 0), (0.009, length - 0.05)], 8)                      # rod
    fr.lathe([(0.02, length - 0.12), (0.075, length - 0.03), (0.085, length), (0, length)], 16)   # ceiling cup
    fr.lathe([(0.0, 0.0), (0.022, 0.0), (0.022, 0.05), (0.009, 0.06)], 8)  # coupling on the crown
    return fr


def main():
    common.reset_scene()
    coll = common.collection("Chandeliers")
    src = common.collection("Chandeliers_sources")       # originals + _export variants
    cols = append("chandelier_dome.blend", ["ChandelierDome", "ChandelierDome_export"])
    cols.update(append("chandelier_tier.blend", ["ChandelierTier", "ChandelierTier_export",
                                                  "ChandelierTierSmall", "ChandelierTierSmall_export"]))
    for c in cols.values():
        src.children.link(c)
    bpy.context.view_layer.layer_collection.children[src.name].exclude = True

    top_z = {k: common.CEIL_H - r for k, r in ROD.items()}
    top_z["ChandelierDome"] = min(common.CHORUS_H + DOME_CLEAR + cols["ChandelierDome"]["height"],
                                  common.CEIL_H - MIN_ROD)
    rods = {}
    for kind, z in top_z.items():
        tmp = bpy.data.collections.new("tmp")
        ob = rod_mesh("ChandelierRod_" + kind, common.CEIL_H - z).finish("ChandelierRod_" + kind, tmp,
                                                                         L.chrome_material())
        rods[kind] = ob.data
        bpy.data.objects.remove(ob)
        bpy.data.collections.remove(tmp)

    places = [("ChandelierDome", "C1", 0.0, DOME_Y),
              ("ChandelierTierSmall", "L1", -SIDE_X, FRONT_SIDE_Y),
              ("ChandelierTierSmall", "R1", SIDE_X, FRONT_SIDE_Y)]
    for i, y in enumerate(ROW_Y):
        row = i + 2
        places.append(("ChandelierTier", "C%d" % row, 0.0, y))
        places.append(("ChandelierTierSmall", "L%d" % row, -SIDE_X, y))
        places.append(("ChandelierTierSmall", "R%d" % row, SIDE_X, y))

    for kind, tag, x, y in places:
        z = top_z[kind]
        e = bpy.data.objects.new("%s_%s" % (kind, tag), None)
        e.instance_type = "COLLECTION"
        e.instance_collection = cols[kind]
        e.empty_display_size = 0.3
        e.location = (x, y, z)
        e.rotation_euler.z = 0.37 * len(coll.objects)      # so no two show the same face
        coll.objects.link(e)
        r = bpy.data.objects.new("ChandelierRod_%s" % tag, rods[kind])
        r.location = (x, y, z)
        coll.objects.link(r)
        li = L.warm_light("ChandelierLight_%s" % tag, POWER[kind], 0.30)
        li.location = (x, y, z + cols[kind]["light_z"])
        coll.objects.link(li)

    common.save("chandeliers")
    for k in ("ChandelierDome", "ChandelierTier", "ChandelierTierSmall"):
        print("TRIS %s_export: %d" % (k, L.tri_count(cols[k + "_export"])))
    print("PLACED", [(p[0], p[1], round(p[2], 2), p[3], round(top_z[p[0]], 2)) for p in places])

    # ---- previews (not saved): a bare dark room for scale
    import bmesh
    L.preview_settings(strength=0.0)
    W, Ln, H = common.NAVE_W, common.NAVE_L, common.CEIL_H
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1)
    for v in bm.verts:
        v.co.x *= W
        v.co.y = (v.co.y + 0.5) * Ln
        v.co.z = (v.co.z + 0.5) * H
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new("room")
    bm.to_mesh(me)
    room = bpy.data.objects.new("room", me)
    me.materials.append(common.flat_material("room", (0.30, 0.29, 0.28), 0.7))
    bpy.context.scene.collection.objects.link(room)
    common.render_preview("chandeliers_from_back", (1.2, 0.6, 4.2), (0, Ln, 4.6), lens=20, size=(640, 480), samples=32)
    common.render_preview("chandeliers_from_chorus", (0.3, Ln - 0.8, common.CHORUS_H + 1.6), (0, Ln * 0.45, 5.0),
                          lens=14, size=(480, 640), samples=32)

main()
