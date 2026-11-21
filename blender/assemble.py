"""Assemble every asset into blender/church.blend and render check views.

Run: Blender -b --python blender/assemble.py -- [--no-render]
"""
import os, sys, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy, common
from mathutils import Matrix, Vector

common.reset_scene()
scene = bpy.context.scene


def append_collections(blend, names):
    path = os.path.join(common.ASSETS, blend + ".blend")
    if not os.path.exists(path):
        print("assemble: missing", blend)
        return []
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.collections = [n for n in names if n in src.collections]
    out = []
    for c in dst.collections:
        if c is not None:
            scene.collection.children.link(c)
            out.append(c)
    bpy.context.view_layer.update()
    return out


def roots(coll):
    return [o for o in coll.all_objects if o.parent is None]


# ---- room, seating, chandeliers (already in room coordinates) ----------
append_collections("shell", ["Shell"])
append_collections("seating", ["Seating"])
append_collections("chandeliers", ["Chandeliers"])

# ---- iconostasis: asset origin -> on the chorus platform at the front ---
for c in append_collections("iconostasis", ["Iconostasis"]):
    m = Matrix.Translation((0, common.NAVE_L, common.CHORUS_H))
    for o in roots(c):
        o.matrix_world = m @ o.matrix_world


# ---- instanced pieces on the shell's slot empties ----------------------
def place(blend, coll_name, slot_prefix, icon_for, icon_prefix="Icon_"):
    src = append_collections(blend, [coll_name])
    if not src:
        return
    src = src[0]
    protos = list(src.all_objects)
    bpy.context.view_layer.update()
    slots = [o for o in bpy.data.objects if o.type == "EMPTY" and o.name.startswith(slot_prefix)]
    dest = common.collection(coll_name + "s")
    for slot in slots:
        key = slot.name[len(slot_prefix):]
        for p in protos:
            o = p.copy()
            dest.objects.link(o)
            o.matrix_world = slot.matrix_world @ p.matrix_world
            if p.name.startswith("Icon_slot"):
                o.data = p.data.copy()
                tex = icon_for(key)
                o.name = icon_prefix + tex
                o.data.materials.clear()
                o.data.materials.append(
                    common.image_material("Icon_" + tex, "icons/%s.jpg" % tex, rough=0.35))
            else:
                o.name = "%s_%s_%s" % (coll_name, key, p.name)
    scene.collection.children.unlink(src)


place("shrine", "Shrine", "Slot_Shrine_", lambda k: k.split("_", 1)[1])
# the stands' icons are their own items in the tour (Icon_stand_*), apart from the iconostasis icons of the same saints
place("icon_stand", "IconStand", "Slot_IconStand_", lambda k: "theotokos" if k == "L" else "christ", "Icon_stand_")

for c in append_collections("throne", ["Throne"]):
    # against the left wall near the iconostasis, turned to face right (+X)
    m = Matrix.Translation((-common.NAVE_W / 2 + 0.5, common.NAVE_L - 1.15, common.CHORUS_H)) \
        @ Matrix.Rotation(math.radians(90), 4, "Z")
    for o in roots(c):
        o.matrix_world = m @ o.matrix_world

# ---- names the tour expects, if an asset file still carries an older name --
for old, new in (("StMark_Relief", "Icon_stmark_relief"), ("Throne_icon", "Icon_throne_christ")):
    if old in bpy.data.objects and new not in bpy.data.objects:
        bpy.data.objects[old].name = new

# ---- the realised chandelier variants for the web export (export_web.py) --
# kept in the file but out of the view layer, so they never render or cast light
path = os.path.join(common.ASSETS, "chandeliers.blend")
if os.path.exists(path):
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.collections = [n for n in src.collections if n.endswith("_export")]
    holder = bpy.data.collections.new("Chandeliers_export")
    scene.collection.children.link(holder)
    for c in dst.collections:
        if c is not None:
            holder.children.link(c)
    bpy.context.view_layer.layer_collection.children[holder.name].exclude = True

# ---- light: evening, chandeliers on -------------------------------------
for o in bpy.data.objects:
    if o.type == "LIGHT":
        o.data.color = (1.0, 0.86, 0.72)
        o.data.energy *= 0.55
        o.data.shadow_soft_size = 0.35
world = bpy.data.worlds.new("World")
world.use_nodes = True
bg = next(n for n in world.node_tree.nodes if n.type == "BACKGROUND")
bg.inputs[0].default_value = (0.02, 0.025, 0.04, 1)
bg.inputs[1].default_value = 1.0
scene.world = world
try:
    scene.view_settings.view_transform = "AgX"
except TypeError:
    pass
scene.view_settings.exposure = -1.2
try:
    scene.cycles.transparent_max_bounces = 24
except Exception:
    pass

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(common.ROOT, "blender", "church.blend"))

if "--no-render" not in sys.argv:
    L, W = common.NAVE_L, common.NAVE_W
    views = {
        "church_toward_altar": ((0.0, 1.2, 1.65), (0.0, L, 2.6), 17),
        "church_iconostasis": ((0.0, L - 7.5, 1.65 + common.CHORUS_H * 0.0), (0.0, L, 2.3), 20),
        "church_left_wall": ((W / 2 - 1.2, 9.0, 1.6), (-W / 2, 13.5, 3.0), 17),
        "church_toward_back": ((0.0, L - 4.0, 1.9), (0.0, 0.0, 2.4), 17),
    }
    only = [a for a in sys.argv if a.startswith("church_")]
    for name, (loc, at, lens) in views.items():
        if only and name not in only:
            continue
        common.render_preview(name, loc, at, lens=lens, size=(1280, 853), samples=64)
