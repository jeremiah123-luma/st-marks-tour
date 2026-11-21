"""Chorus deacon bench -> collection `DeaconBench`, saved as deacon_bench.blend.

Same family as the nave pew but shorter, open underneath (plank legs and a
centre stretcher, no book rail) with a larger marquetry square on the ends.
One mesh object. Origin = floor centre, seat faces -Y.
Run: Blender -b --python blender/assets/deacon_bench.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common       # noqa: E402
import seat_parts as sp  # noqa: E402

LENGTH = 2.6      # estimate from IMG_7910 / IMG_7911 (four back panels)


def build():
    coll = common.collection("DeaconBench")
    b = sp.B(seed=31)
    M = dict(sp.pew_materials())
    M["cushion"] = sp.fabric("DeaconCushion", (0.200, 0.006, 0.018))   # a little redder than the nave
    sp.build_bench(b, M, LENGTH, common.PEW_BACK_H, common.PEW_SEAT_H,
                   n_panels=4, n_supports=2, book_rail=False, inlay=0.36, pads=1)
    return coll, b.finish("DeaconBench", coll)


if __name__ == "__main__":
    import bpy
    common.reset_scene()
    coll, ob = build()
    print("DEACONBENCH tris:", sp.tri_count(coll))
    common.save("deacon_bench")
    for k in (1, 2):                       # preview only: the benches behind
        twin = bpy.data.objects.new("PreviewRow", ob.data)
        twin.location.y = k * 0.85
        bpy.context.scene.collection.objects.link(twin)
    sp.preview("deacon_bench", (-2.9, -2.3, 1.6), (-0.5, 0.0, 0.42), lens=34)
    # same angle as IMG_7910 (for compare_bench.png)
    L = LENGTH
    sp.preview("cmp_bench", (L / 2 + 0.42, -0.80, 1.08), (L / 2 - 0.60, 0.28, 0.40), lens=16, size=(480, 720),
               samples=40,
               setup=False)
