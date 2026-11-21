"""Nave pew -> collection `Pew`, saved as pew.blend.

One mesh object. Origin = floor centre. The SEAT faces -Y (spec default:
asset faces -Y); seating_layout.py turns it round so sitters face the altar.
Run: Blender -b --python blender/assets/pew.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common       # noqa: E402
import seat_parts as sp  # noqa: E402


def build():
    """Collection `Pew` holds two mesh objects: `Pew` (main block, beside the
    centre aisle) and `PewSide` (short pew against the wall)."""
    coll = common.collection("Pew")
    M = sp.pew_materials()
    out = []
    for k, (name, length) in enumerate((("Pew", sp.MAIN_PEW_LEN), ("PewSide", sp.SIDE_PEW_LEN))):
        b = sp.B(seed=11 + k)
        sp.build_bench(b, M, length, common.PEW_BACK_H, common.PEW_SEAT_H,
                       n_panels=max(2, round(length / 0.60)),
                       n_supports=max(0, round(length / 1.5) - 1),
                       book_rail=True, inlay=0.33, pads=2 if length > 2.0 else 1)
        out.append(b.finish(name, coll))
    return coll, out


if __name__ == "__main__":
    import bpy
    common.reset_scene()
    coll, (main, side) = build()
    for ob in (main, side):
        ob.data.calc_loop_triangles()
        print("PEW tris:", ob.name, len(ob.data.loop_triangles))
    common.save("pew")
    side.hide_render = True          # previews show the main pew
    L = sp.MAIN_PEW_LEN
    # preview only: neighbouring rows, as in the nave
    for k in (-2, -1, 1, 2):
        twin = bpy.data.objects.new("PreviewRow", main.data)
        twin.location.y = -k * common.PEW_PITCH
        bpy.context.scene.collection.objects.link(twin)
    sp.preview("pew", (-L / 2 - 2.2, -2.6, 1.7), (-0.5, 0.0, 0.45), lens=30)
    sp.preview("pew_end", (-L / 2 - 1.5, -0.9 - 2 * common.PEW_PITCH, 0.95), (-L / 2, -2 * common.PEW_PITCH, 0.5),
               lens=50, setup=False)
    # same angle as the balcony photo MVIMG_20190817_111919 (for compare_pew.png)
    sp.preview("cmp_pew", (-L / 2 - 2.9, -0.55, 2.75), (-L / 2 + 0.25, 0.05, 0.50), lens=62, size=(480, 720),
               samples=40, setup=False)
