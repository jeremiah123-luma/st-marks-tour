"""Brass rope stanchion -> collection `RopePost`, saved as rope_post.blend.

Two objects: `RopePost` (the post, origin floor centre) and `RopePost_Rope`
(a burgundy rope swag running from this post toward +X for ROPE_SPAN, the
distance between the two posts either side of the centre aisle).
Run: Blender -b --python blender/assets/rope_post.py
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common       # noqa: E402
import seat_parts as sp  # noqa: E402

POST_H = 0.96
POST_INSET = 0.06                               # post centre sits this far outside the aisle edge
ROPE_SPAN = common.AISLE_W + 2 * POST_INSET     # centre to centre
HOOK_Z = 0.885


def build():
    coll = common.collection("RopePost")
    brass = common.flat_material("Brass", (0.80, 0.58, 0.24), rough=0.2, metallic=1.0)
    rope = sp.fabric("RopeVelvet", (0.17, 0.008, 0.020))

    b = sp.B()
    b.lathe([(0.0, 0.0), (0.165, 0.0), (0.165, 0.010), (0.155, 0.022), (0.110, 0.040), (0.060, 0.056),
             (0.034, 0.066), (0.034, 0.082), (0.0255, 0.090), (0.0255, 0.865), (0.036, 0.872),
             (0.036, 0.900), (0.0255, 0.907), (0.0255, 0.925), (0.046, 0.935), (0.046, POST_H - 0.006),
             (0.040, POST_H), (0.0, POST_H)], 18, 0.0, 0.0, brass)
    post = b.finish("RopePost", coll)

    r = sp.B()
    x0, x1, sag, n = 0.036, ROPE_SPAN - 0.036, 0.24, 16
    path = []
    for i in range(n + 1):
        t = i / n
        path.append((x0 + (x1 - x0) * t, 0.0, HOOK_Z - sag * (1 - (2 * t - 1) ** 2)))
    r.tube(path[1:-1], 0.017, 7, rope)
    for a, c in ((path[0], path[1]), (path[-1], path[-2])):       # brass end fittings
        r.tube([a, ((a[0] + c[0]) / 2, 0, (a[2] + c[2]) / 2), c], 0.021, 7, brass)
    rope_ob = r.finish("RopePost_Rope", coll)
    return coll, post, rope_ob


if __name__ == "__main__":
    import bpy
    common.reset_scene()
    coll, post, rope_ob = build()
    print("ROPEPOST tris:", sp.tri_count(coll))
    common.save("rope_post")
    # preview only: a second post at the far end of the rope
    twin = bpy.data.objects.new("PreviewTwin", post.data)
    twin.location.x = ROPE_SPAN
    bpy.context.scene.collection.objects.link(twin)
    sp.preview("rope_post", (-0.9, -3.0, 1.35), (ROPE_SPAN / 2, 0.0, 0.5), lens=40)
