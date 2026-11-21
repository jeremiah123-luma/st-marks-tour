"""Print collections, object counts and bounds of each asset .blend."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
from mathutils import Vector

for name in ["shell", "seating", "iconostasis", "chandeliers", "shrine", "icon_stand", "throne"]:
    p = os.path.join(common.ASSETS, name + ".blend")
    if not os.path.exists(p):
        print("MISSING", name); continue
    bpy.ops.wm.open_mainfile(filepath=p)
    print("==", name)
    for c in bpy.data.collections:
        objs = [o for o in c.all_objects]
        mn = Vector((1e9,) * 3); mx = Vector((-1e9,) * 3)
        for o in objs:
            if o.type != "MESH": continue
            for corner in o.bound_box:
                w = o.matrix_world @ Vector(corner)
                mn = Vector(map(min, mn, w)); mx = Vector(map(max, mx, w))
        print("  coll", c.name, len(objs), "children", [k.name for k in c.children][:8],
              "min", [round(v, 2) for v in mn], "max", [round(v, 2) for v in mx])
    em = [o.name for o in bpy.data.objects if o.type == "EMPTY" and o.name.startswith("Slot")]
    print("  slots", [(n, [round(v, 2) for v in bpy.data.objects[n].location],
                       [round(v, 2) for v in bpy.data.objects[n].rotation_euler]) for n in em])
    print("  lights", len([o for o in bpy.data.objects if o.type == "LIGHT"]))
