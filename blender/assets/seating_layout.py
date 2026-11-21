"""Seating layout -> collection `Seating`, saved as seating.blend.

Appends Pew / DeaconBench / Lectern / RopePost from their .blend files and
places linked duplicates (shared mesh data). All positions come from
common.py and seat_parts.py; nothing is hardcoded from an older room size.

Layout (what the photos show, see seat_parts.py "floor plan"):
  * FOUR pew blocks: main pew each side of the centre aisle, a side aisle,
    then a short pew up against the wall heater. common.PEW_ROWS rows each,
    common.PEW_PITCH apart, back-most seat back at common.PEW_FIRST_Y.
    Sitters face +Y (the altar).
  * Chorus (z = common.CHORUS_H): three deacon benches each side running
    front-to-back, facing the centre (each other), ends toward the people.
  * Two lecterns flanking the royal door: the left one close to the
    iconostasis (reader faces the altar), the right one further forward
    (reader faces the people).
  * Two brass rope posts behind the last row, one each side of the centre
    aisle. The rope across the aisle is only added when ROPE_ACROSS is True
    (the photos show the aisle open).
Run AFTER the four asset scripts: Blender -b --python blender/assets/seating_layout.py
"""
import math
import os
import sys

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import common       # noqa: E402
import seat_parts as sp  # noqa: E402

ROPE_ACROSS = False
BENCHES_PER_SIDE = 3
BENCH_PITCH = 0.85
BENCH_WALL_GAP = 0.30        # behind the outer bench (heater)
BENCH_FRONT_GAP = 0.30       # bench end to the front edge of the chorus platform
LECTERN_X = common.DOOR_W / 2 + 0.75
LECTERN_L_GAP = 0.55         # left lectern centre to the iconostasis face
LECTERN_R_GAP = 1.70         # right lectern stands further forward
ROPE_POST_INSET = 0.06       # must match rope_post.POST_INSET
ROPE_POST_BEHIND = 0.45      # behind the last row's seat back


def append(blend, coll_name):
    path = os.path.join(common.ASSETS, blend + ".blend")
    if not os.path.exists(path):
        raise SystemExit("missing %s - run blender/assets/%s.py first" % (path, blend))
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.collections = [coll_name]
    return {o.name: o for o in dst.collections[0].objects}   # not linked into the scene


def main():
    common.reset_scene()
    coll = common.collection("Seating")
    pews = append("pew", "Pew")
    bench = append("deacon_bench", "DeaconBench")["DeaconBench"]
    lect = append("lectern", "Lectern")["Lectern"]
    rope = append("rope_post", "RopePost")
    bench_len = bench.dimensions.x

    def place(src, name, loc, rot_z=0.0):
        ob = bpy.data.objects.new(name, src.data)      # linked duplicate
        ob.location = loc
        ob.rotation_euler = (0, 0, rot_z)
        coll.objects.link(ob)
        return ob

    # ---- pews: asset seat faces -Y, so turn it round; back sits at +BACK_Y0 locally
    for side, sx in (("L", -1), ("R", 1)):
        for r in range(common.PEW_ROWS):
            y = common.PEW_FIRST_Y + r * common.PEW_PITCH + sp.BACK_Y0
            place(pews["Pew"], "Pew_%s_%02d" % (side, r + 1), (sx * sp.MAIN_PEW_X, y, 0), math.pi)
            place(pews["PewSide"], "PewSide_%s_%02d" % (side, r + 1), (sx * sp.SIDE_PEW_X, y, 0), math.pi)

    # ---- chorus
    z = common.CHORUS_H
    by = common.CHORUS_Y + BENCH_FRONT_GAP + bench_len / 2
    for side, sx in (("L", -1), ("R", 1)):
        for i in range(BENCHES_PER_SIDE):
            back_x = common.NAVE_W / 2 - BENCH_WALL_GAP - i * BENCH_PITCH
            # seat faces the centre: local -Y -> world -sx*X
            place(bench, "DeaconBench_%s_%d" % (side, i + 1), (sx * (back_x - sp.BACK_Y0), by, z),
                  sx * math.pi / 2)
    place(lect, "Lectern_L", (-LECTERN_X, common.NAVE_L - LECTERN_L_GAP, z), math.pi)
    place(lect, "Lectern_R", (LECTERN_X, common.NAVE_L - LECTERN_R_GAP, z), 0.0)

    # ---- rope posts behind the last row
    px = common.AISLE_W / 2 + ROPE_POST_INSET
    py = common.PEW_FIRST_Y - ROPE_POST_BEHIND
    place(rope["RopePost"], "RopePost_L", (-px, py, 0))
    place(rope["RopePost"], "RopePost_R", (px, py, 0))
    if ROPE_ACROSS:
        place(rope["RopePost_Rope"], "RopePost_Rope", (-px, py, 0))

    # the appended files each bring their own copy of shared materials: merge them
    for me in bpy.data.meshes:
        for i, m in enumerate(me.materials):
            base = bpy.data.materials.get(m.name.rsplit(".", 1)[0]) if m.name[-4:-3] == "." else None
            if base:
                me.materials[i] = base

    tris = sp.tri_count(coll)
    uniq = {}
    for o in coll.objects:
        o.data.calc_loop_triangles()
        uniq[o.data.name] = len(o.data.loop_triangles)
    print("SEATING objects:", len(coll.objects), "instanced tris:", tris, "unique tris:", sum(uniq.values()), uniq)
    print("SEATING main pew %.2f m at |x| %.2f..%.2f, side pew %.2f m at |x| %.2f..%.2f, rows %d, y %.2f..%.2f" % (
        sp.MAIN_PEW_LEN, sp.MAIN_PEW_X - sp.MAIN_PEW_LEN / 2, sp.MAIN_PEW_X + sp.MAIN_PEW_LEN / 2,
        sp.SIDE_PEW_LEN, sp.SIDE_PEW_X - sp.SIDE_PEW_LEN / 2, sp.SIDE_PEW_X + sp.SIDE_PEW_LEN / 2,
        common.PEW_ROWS, common.PEW_FIRST_Y, common.PEW_FIRST_Y + (common.PEW_ROWS - 1) * common.PEW_PITCH))
    bpy.ops.outliner.orphans_purge(do_recursive=True)
    common.save("seating")

    # ---- previews: stand-in nave (not saved)
    w, y0, y1 = common.NAVE_W / 2, common.CHORUS_Y, common.NAVE_L
    sp.room(-w, w, 0.0, common.NAVE_L, common.WALL_H,
            windows=[(side, wy, common.WINDOW_W, common.WINDOW_SILL, common.WINDOW_TOP)
                     for side in ("x0", "x1") for wy in common.WINDOW_Y])
    me = bpy.data.meshes.new("PreviewChorus")
    me.from_pydata([(-w, y0, 0), (w, y0, 0), (w, y1, 0), (-w, y1, 0), (-w, y0, z), (w, y0, z), (w, y1, z), (-w, y1, z)],
                   [], [(4, 5, 6, 7), (0, 1, 5, 4)])
    plat = bpy.data.objects.new("PreviewChorus", me)
    plat.location.z = -0.002
    me.materials.append(sp.carpet_material())
    bpy.context.scene.collection.objects.link(plat)
    n = 4
    sp.lights([((0.0, common.NAVE_L * (i + 0.5) / n, common.WALL_H - 0.4), 900, 2.0) for i in range(n)])
    kw = dict(size=(640, 480), samples=32)
    last = common.PEW_FIRST_Y + (common.PEW_ROWS - 1) * common.PEW_PITCH
    common.render_preview("seating", (0.0, 0.6, 3.6), (0.0, common.NAVE_L * 0.62, 0.4), lens=20, **kw)
    common.render_preview("seating_chorus", (-1.2, last - 2.0, 2.3), (1.6, common.NAVE_L - 1.5, 0.7), lens=22, **kw)
    common.render_preview("seating_aisle", (2.0, common.PEW_FIRST_Y - 1.9, 1.6), (-1.5, common.PEW_FIRST_Y + 3, 0.5),
                          lens=22, **kw)
    bpy.data.objects["PreviewCeil"].hide_render = True
    for o in bpy.data.objects:
        if o.name.startswith("PreviewLight"):
            o.location.z = 30.0
            o.data.energy *= 40
    common.render_preview("seating_top", (0.0, common.NAVE_L / 2, 34.0), (0.0, common.NAVE_L / 2 + 0.001, 0.0), lens=70, **kw)


if __name__ == "__main__":
    main()
