"""Export blender/church.blend for the web tour: web/public/church.glb + web/public/lm/*.

Run:  Blender -b --python blender/export_web.py -- [quick] [reuse] [assemble]
  quick     small lightmaps and few samples: proves the pipeline in a few minutes
  reuse     reuse baked lightmaps / albedo from blender/export_cache when sizes and samples match
  assemble  run assemble.py (no renders) first; also happens when church.blend is missing
church.blend itself is never saved by this script.

What it does
1. Environment probe: a small equirectangular HDR rendered from the middle of the nave (web/public/lm/env.hdr),
   used on the web for reflections (varnished ceiling, pews, metal, glass), box-projected onto the room.
2. Per group (shell / seating / iconostasis + throne / shrines + icon stands):
   - an "atlas" UV unwrap (once per mesh datablock, so the 48 pews share one unwrap) and an albedo atlas baked
     from the procedural materials (base colour through an emission bake, so metals keep their colour too);
   - instances made real and everything joined into one mesh; a unique lightmap UV set (the atlas islands
     repacked) and a diffuse direct + indirect bake under the chandelier lights, denoised with OpenImageDenoise;
   - faces whose material is just an image on UVs (carpet, runner, marquetry, bead lattice, inlays) keep their
     own UVs and image; everything else points at the albedo atlas. A few web materials per group, by
     gloss class (matte / satin / varnish = clear-coated / mirror / metal) so the web can pick a cheap or a reflective shader.
   - surface relief for the highlights: a tangent-space normal map baked for the seating (pew bevels, cushions),
     a small tiling board profile for striped, bumped materials (ceiling planks, wainscot) on a third UV set,
     and normal maps made from the height images of the marquetry, bead lattice and the St Mark relief;
   - shell faces that cannot be seen from anywhere a visitor can stand are dropped before unwrapping.
3. Every Icon_* / Win_* object stays its own mesh with its photo at its own resolution; they share one lightmap.
4. Chandeliers: the realised `_export` crystals (vertex colour Col: R = per-crystal sparkle) and the frames,
   one mesh per chandelier type, placed as instances; no lightmap (emissive / reflective on the web).
5. UV0 = base textures, UV1 = lightmap. Lightmaps are RGBM-encoded WebP (sRGB colour x alpha x range).
6. GLB export, then meshopt compression with gltf-transform (web/node_modules/.bin or the studio project's).
"""
import bpy, sys, os, json, math, subprocess, time, shutil
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
QUICK, REUSE = "quick" in ARGS, "reuse" in ARGS
ROOT = os.path.dirname(HERE)
BLEND = os.path.join(HERE, "church.blend")
BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"
CACHE = os.path.join(HERE, "export_cache")
PUBLIC = os.path.join(ROOT, "web", "public")
LM_DIR = os.path.join(PUBLIC, "lm")
os.makedirs(CACHE, exist_ok=True)
os.makedirs(LM_DIR, exist_ok=True)

if "assemble" in ARGS or not os.path.exists(BLEND):
    subprocess.run([BLENDER, "-b", "--python", os.path.join(HERE, "assemble.py"), "--", "--no-render"], check=True)
bpy.ops.wm.open_mainfile(filepath=BLEND)
import common  # after open_mainfile: only its constants are used

sc = bpy.context.scene
T0 = time.time()


def log(*a):
    print("[export %5.0fs]" % (time.time() - T0), *a, flush=True)


# ------------------------------------------------------------------ settings
RGBM_RANGE = 8.0
# name, collections, lightmap size, albedo atlas size
GROUPS = [
    ("shell", ["Shell"], 2048, 4096),
    ("seating", ["Seating"], 2048, 2048),
    ("icono", ["Iconostasis", "Throne"], 2048, 4096),
    ("shrines", ["Shrines", "IconStands"], 1024, 2048),
]
PICS_LM = 1024
LM_SAMPLES = 24 if QUICK else int(os.environ.get("LM_SAMPLES", "128"))
LM_BOOST = {"shell": 2, "pics": 2}   # x samples: big plain plaster and the window casings show denoiser mottle first
NB = 16                              # boards per repeat of a board-profile normal tile
DROP_UNSEEN = ("shell",)             # groups whose never-seen faces are deleted before unwrapping
NORMAL_GROUPS = ("seating",)         # groups that get a baked tangent-space normal map on the atlas UVs
if QUICK:
    GROUPS = [(n, c, max(256, lm // 4), alb // 2) for n, c, lm, alb in GROUPS]
    PICS_LM = 256
ALB_SAMPLES = 8 if QUICK else 24
ENV_SIZE = (512, 256)
PROBE = (0.0, common.NAVE_L * 0.5, 3.2)          # Blender coordinates


def is_pic(o):
    return o.name.startswith(("Icon_", "Win_"))


try:
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = True
    sc.cycles.device = "GPU"
except Exception as e:  # CPU still works, only slower
    log("no GPU:", e)
try:
    sc.render.engine = "CYCLES"
except TypeError:
    pass
rb = sc.render.bake
rb.margin = 0
rb.use_clear = False
rb.use_selected_to_active = False
rb.target = "IMAGE_TEXTURES"
EXPOSURE = sc.view_settings.exposure
VIEW = sc.view_settings.view_transform


# ------------------------------------------------------------------ helpers
def select_only(objs):
    if bpy.context.object and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]


def bsdf(m):
    return next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if m and m.node_tree else None


def pixels(img):
    a = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    img.pixels.foreach_get(a)
    return a.reshape(img.size[1], img.size[0], 4)


def new_float(name, size):
    img = bpy.data.images.new(name, size, size, alpha=True, float_buffer=True)
    img.generated_color = (0, 0, 0, 0)
    return img


def dilate(rgb, valid, steps):
    """Grow island colours into the empty gutters so filtering and mipmaps never pull black in."""
    rgb, valid = rgb.copy(), valid.copy()
    for _ in range(steps):
        if valid.all():
            break
        acc = np.zeros_like(rgb)
        cnt = np.zeros(valid.shape, np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            v = np.roll(valid, (dy, dx), axis=(0, 1))
            acc += np.roll(rgb, (dy, dx), axis=(0, 1)) * v[..., None]
            cnt += v
        grow = (~valid) & (cnt > 0)
        rgb[grow] = acc[grow] / cnt[grow][:, None]
        valid |= grow
    return rgb, valid


def lin_to_srgb(c):
    c = np.clip(c, 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)


def save_bytes(arr, path):
    """arr: h x w x 4 floats 0..1, written to an 8-bit PNG exactly as given (straight alpha)."""
    h, w = arr.shape[:2]
    img = bpy.data.images.new("__save", w, h, alpha=True)
    img.alpha_mode = "STRAIGHT"
    img.pixels.foreach_set(np.ascontiguousarray(arr, np.float32).ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def denoise(arr):
    """OpenImageDenoise through the compositor (the denoiser Cycles uses for renders). arr: h x w x 3."""
    h, w = arr.shape[:2]
    src = bpy.data.images.new("__dn_in", w, h, alpha=False, float_buffer=True)
    full = np.ones((h, w, 4), np.float32)
    full[..., :3] = arr
    src.pixels.foreach_set(full.ravel())
    tree = bpy.data.node_groups.new("__dn", "CompositorNodeTree")
    keep_tree = sc.compositing_node_group
    sc.compositing_node_group = tree
    i = tree.nodes.new("CompositorNodeImage")
    i.image = src
    d = tree.nodes.new("CompositorNodeDenoise")
    tree.links.new(i.outputs[0], d.inputs["Image"])
    tree.interface.new_socket("Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    go = tree.nodes.new("NodeGroupOutput")
    tree.links.new(d.outputs[0], go.inputs[0])
    cam = None
    if not sc.camera:
        cam = bpy.data.objects.new("__dn_cam", bpy.data.cameras.new("__dn_cam"))
        sc.collection.objects.link(cam)
        sc.camera = cam
    hidden = [o for o in sc.objects if not o.hide_render]
    for o in hidden:
        o.hide_render = True  # nothing to render; only the compositor runs
    r = sc.render
    keep = (r.resolution_x, r.resolution_y, r.resolution_percentage, sc.cycles.samples, r.filepath)
    r.resolution_x, r.resolution_y, r.resolution_percentage = w, h, 100
    sc.cycles.samples = 1
    r.image_settings.file_format = "OPEN_EXR"
    r.image_settings.color_depth = "32"
    path = os.path.join(CACHE, "_dn.exr")
    r.filepath = path
    bpy.ops.render.render(write_still=True)
    for o in hidden:
        o.hide_render = False
    r.resolution_x, r.resolution_y, r.resolution_percentage, sc.cycles.samples, r.filepath = keep
    res = bpy.data.images.load(path)
    out = pixels(res)[..., :3].copy()
    bpy.data.images.remove(res)
    bpy.data.images.remove(src)
    sc.compositing_node_group = keep_tree
    bpy.data.node_groups.remove(tree)
    if cam:
        bpy.data.objects.remove(cam)
    return out


def max_filter(a, r):
    o = a.copy()
    for ax in (0, 1):
        t = o.copy()
        for k in range(1, r + 1):
            for s in (k, -k):
                sh = np.roll(o, s, axis=ax)
                # no wrap-around
                if ax == 0:
                    if s > 0: sh[:s] = 0
                    else: sh[s:] = 0
                else:
                    if s > 0: sh[:, :s] = 0
                    else: sh[:, s:] = 0
                t = np.maximum(t, sh)
        o = t
    return o


def box_blur(a, r):
    o = a.copy()
    for ax in (0, 1):
        t = np.zeros_like(o)
        for k in range(-r, r + 1):
            t += np.roll(o, k, axis=ax)
        o = t / (2 * r + 1)
    return o


def save_rgbm(rgb, name, quality=92):
    """Linear light -> RGBM: 8-bit sRGB colour x a per-pixel multiplier in alpha (x RGBM_RANGE on the web).
    The multiplier is kept spatially smooth (local max, blurred) so lossy WebP does not break gradients;
    this is the studio project's encoding (scripts/publish-bake.mjs)."""
    lin = np.clip(rgb, 0, RGBM_RANGE)
    need = lin.max(-1) / RGBM_RANGE
    want = np.maximum(box_blur(max_filter(need, 6), 6), need)
    m = np.clip(np.ceil(want * 255) / 255, 1 / 255, 1)
    out = np.empty(rgb.shape[:2] + (4,), np.float32)
    out[..., :3] = np.round(lin_to_srgb(lin / (m[..., None] * RGBM_RANGE)) * 255) / 255
    out[..., 3] = m
    png = os.path.join(CACHE, name + ".png")
    save_bytes(out, png)
    cwebp = shutil.which("cwebp") or "/opt/homebrew/bin/cwebp"
    if os.path.exists(cwebp):
        dst = os.path.join(LM_DIR, name + ".webp")
        subprocess.run([cwebp, "-quiet", "-q", str(quality), "-alpha_q", "100", "-exact", "-sharp_yuv", "-m", "6",
                        png, "-o", dst], check=True)
    else:
        dst = os.path.join(LM_DIR, name + ".png")
        shutil.copy(png, dst)
    log("lightmap", os.path.basename(dst), "%d KB" % (os.path.getsize(dst) / 1024), "max %.2f mean %.3f" % (lin.max(), lin.mean()))
    return "lm/" + os.path.basename(dst)


# ------------------------------------------------------------------ material classification
def classify(m):
    """How a material's base colour reaches the web: 'image' (an image on UVs, passed through),
    or 'atlas' (flat or procedural, baked into the group's albedo atlas)."""
    b = bsdf(m)
    info = {"kind": "atlas", "rough": 0.5, "metal": 0.0, "emit": 0.0, "emit_color": (1, 1, 1), "emit_image": False, "coat": 0.0}
    if not b:
        return info
    r, me = b.inputs["Roughness"], b.inputs["Metallic"]
    info["rough"] = 0.5 if r.is_linked else r.default_value
    info["metal"] = 0.0 if me.is_linked else me.default_value
    es, ec = b.inputs["Emission Strength"], b.inputs["Emission Color"]
    if not es.is_linked and es.default_value > 0:
        info["emit"] = es.default_value
        if ec.is_linked:
            info["emit_image"] = ec.links[0].from_node.type == "TEX_IMAGE"
            if not info["emit_image"]:
                info["emit"] = 0.0
        else:
            info["emit_color"] = tuple(ec.default_value[:3])
    # a clear coat (varnished pews, ceiling, shrines) is what the eye reads as the gloss: its roughness wins
    cw, cr = b.inputs["Coat Weight"], b.inputs["Coat Roughness"]
    if not cw.is_linked and cw.default_value >= 0.3:
        info["coat"] = 0.12 if cr.is_linked else max(0.08, cr.default_value)
    bc = b.inputs["Base Color"]
    info["color"] = tuple(bc.default_value[:3])
    if not bc.is_linked:
        return info
    node, tint = bc.links[0].from_node, (1.0, 1.0, 1.0)
    if node.type == "VECT_MATH" and node.operation in ("MULTIPLY", "SCALE"):
        a = node.inputs[0]
        if node.operation == "SCALE":
            k = node.inputs["Scale"]
            if not a.is_linked or k.is_linked:
                return info
            tint = (k.default_value,) * 3
        else:
            other = node.inputs[1]
            if a.is_linked == other.is_linked:
                return info
            if not a.is_linked:
                a, other = other, a
            tint = tuple(other.default_value[:3])
        node = a.links[0].from_node
    if node.type != "TEX_IMAGE" or not node.image or node.image.source != "FILE" and not node.image.has_data:
        return info
    v = node.inputs["Vector"]
    uv = None
    if v.is_linked:
        src = v.links[0].from_node
        if src.type == "UVMAP":
            uv = src.uv_map or None
        elif not (src.type == "TEX_COORD" and v.links[0].from_socket.name == "UV"):
            return info
    info.update(kind="image", image=node.image, tint=tint, uv=uv)
    return info


INFO = {}


def info_of(m):
    if m.name not in INFO:
        INFO[m.name] = classify(m)
    return INFO[m.name]


def gloss_class(i):
    if i["metal"] >= 0.5:
        return "metal", 0.3, 1.0
    if i.get("coat"):
        return "varnish", 0.25, 0.0  # the room's reflection stays soft (the planks' bump breaks it up in Cycles);
        #                              the lamps' highlights use the coat's own roughness (material extra "coat")
    r = i["rough"]
    if r <= 0.15:
        return "mirror", 0.08, 0.0
    if r <= 0.32:
        return "varnish", 0.25, 0.0
    if r <= 0.5:
        return "satin", 0.4, 0.0
    return "matte", 0.9, 0.0


class EmitOverride:
    """Temporarily make each material emit its base colour, so an EMIT bake gives the albedo."""

    def __init__(self, mats):
        self.undo = []
        for m in mats:
            b = bsdf(m)
            if not b:
                continue
            nt = m.node_tree
            out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL" and n.is_active_output), None)
            if not out or not out.inputs[0].is_linked:
                continue
            orig = out.inputs[0].links[0].from_socket
            e = nt.nodes.new("ShaderNodeEmission")
            bc = b.inputs["Base Color"]
            if bc.is_linked:
                nt.links.new(bc.links[0].from_socket, e.inputs[0])
            else:
                e.inputs[0].default_value = bc.default_value
            nt.links.new(e.outputs[0], out.inputs[0])
            self.undo.append((nt, e, orig, out))

    def restore(self):
        for nt, e, orig, out in self.undo:
            nt.links.new(orig, out.inputs[0])
            nt.nodes.remove(e)


def target(objs, image):
    for o in objs:
        for s in o.material_slots:
            m = s.material
            if not m:
                continue
            n = m.node_tree.nodes.get("__bake") or m.node_tree.nodes.new("ShaderNodeTexImage")
            n.name = "__bake"
            n.image = image
            for x in m.node_tree.nodes:
                x.select = False
            n.select = True
            m.node_tree.nodes.active = n


def untarget():
    for m in bpy.data.materials:
        if m.node_tree and "__bake" in m.node_tree.nodes:
            m.node_tree.nodes.remove(m.node_tree.nodes["__bake"])


def bake(objs, kind, image, samples, **passes):
    target(objs, image)
    select_only(objs)
    rb.use_pass_direct = passes.get("direct", False)
    rb.use_pass_indirect = passes.get("indirect", False)
    rb.use_pass_color = passes.get("color", False)
    sc.cycles.samples = samples
    bpy.ops.object.bake(type=kind)
    untarget()


def pack(margin):
    """Pack the islands in edit mode; margin is the gutter between islands as a fraction of the texture
    (given in texels by the callers), not scaled with the island count."""
    try:
        bpy.ops.uv.pack_islands(margin=margin, margin_method="ADD", rotate=True)
    except TypeError:
        bpy.ops.uv.pack_islands(margin=margin, rotate=True)


def unwrap(objs, layer, margin):
    """Smart-project the given objects together into one UV space, equal texel density."""
    for o in objs:
        me = o.data
        uv = me.uv_layers.get(layer) or me.uv_layers.new(name=layer, do_init=False)
        render = next((l for l in me.uv_layers if l.active_render), None)
        me.uv_layers.active = uv
        if render and render.name != layer:
            render.active_render = True  # procedural materials that read UVs keep reading the original set
    select_only(objs)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=0.0, area_weight=0.0,
                             correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.select_all(action="SELECT")
    bpy.ops.uv.average_islands_scale()
    pack(margin)
    bpy.ops.object.mode_set(mode="OBJECT")


def uv_get(me, name):
    a = np.empty(len(me.loops) * 2, np.float32)
    me.uv_layers[name].uv.foreach_get("vector", a)
    return a.reshape(-1, 2)


def tris(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def uv_sig(objs):
    """A short fingerprint of the active UV layout, so cached bakes are only reused on the same unwrap."""
    n, tot = 0, 0.0
    for o in objs:
        n += len(o.data.polygons)
        tot += float(uv_get(o.data, o.data.uv_layers.active.name).sum(dtype=np.float64))
    return "%d_%d" % (n, int(round(tot * 100)))


def drop_unseen(objs):
    """Delete faces no visitor can see: no line of sight (from either side) to any point of a grid of standing
    and looking positions inside the nave. Outer wall faces, backs and buried ends go; they would only take
    lightmap and atlas space. The check is by ray casts against every mesh in the scene."""
    import bmesh
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    # one BVH of every mesh in the view layer (scene.ray_cast walks all the crystal instances on every call)
    verts, polys = [], []
    for ob in bpy.context.view_layer.objects:
        if ob.type != "MESH" or not ob.data.polygons:
            continue
        base, m = len(verts), ob.matrix_world
        verts += [m @ v.co for v in ob.data.vertices]
        polys += [[base + i for i in p.vertices] for p in ob.data.polygons]
    bvh = BVHTree.FromPolygons(verts, polys)
    hw = common.NAVE_W / 2
    views = [Vector((x, y, z)) for z in (1.6, 3.0, common.CEIL_H - 0.9)
             for x in np.linspace(-hw + 0.7, hw - 0.7, 5) for y in np.linspace(0.6, common.NAVE_L - 0.5, 10)]
    removed = kept = 0
    for o in objs:
        mw = o.matrix_world
        nm = mw.to_3x3().inverted().transposed()
        bm = bmesh.new()
        bm.from_mesh(o.data)
        dead, last, order = [], 0, list(range(len(views)))
        for f in bm.faces:
            c = mw @ f.calc_center_median()
            n = (nm @ f.normal).normalized()
            pts = [c]
            if f.calc_area() > 0.25:  # a big face can be seen in part: also try toward a few of its corners
                vs = f.verts[:: max(1, len(f.verts) // 4)][:4]
                pts += [c.lerp(mw @ v.co, 0.7) for v in vs]
            seen = False
            for pt in pts:
                for side in (1.0, -1.0):
                    org = pt + n * (0.012 * side)
                    for k in [last] + order:
                        d = views[k] - org
                        if d.dot(n) * side <= 0.02:
                            continue
                        dist = d.length
                        if bvh.ray_cast(org, d / dist, dist - 0.02)[0] is None:
                            seen, last = True, k
                            break
                    if seen:
                        break
                if seen:
                    break
            if seen:
                kept += 1
            else:
                dead.append(f)
        removed += len(dead)
        if dead:
            bmesh.ops.delete(bm, geom=dead, context="FACES")
            bm.to_mesh(o.data)
            o.data.update()
        bm.free()
    bpy.context.view_layer.update()
    return removed, kept


def save_normal(arr, valid, path):
    """A tangent-space normal map (already encoded 0..1), flat where nothing was baked, gutters filled."""
    rgb, grown = dilate(arr, valid, 16)
    rgb[~grown] = (0.5, 0.5, 1.0)
    out = np.ones(rgb.shape[:2] + (4,), np.float32)
    out[..., :3] = rgb
    save_bytes(out, path)


def load_data_image(path, name):
    img = bpy.data.images.load(path, check_existing=False)
    img.name = name
    img.colorspace_settings.name = "Non-Color"
    img.pack()
    return img


def board_detail(m):
    """Striped, bumped board materials (ceiling planks, wainscot): which UV axis runs across the boards, boards
    per UV unit, and the groove depth. Their relief is far finer than any atlas texel, so it ships as a tiling
    profile instead (board_tile)."""
    b = bsdf(m)
    n = b.inputs["Normal"] if b else None
    if not n or not n.is_linked or n.links[0].from_node.type != "BUMP":
        return None
    bump = n.links[0].from_node
    for node in m.node_tree.nodes:
        if node.type == "MATH" and node.operation == "MULTIPLY" and node.inputs[0].is_linked and not node.inputs[1].is_linked:
            link = node.inputs[0].links[0]
            sep = link.from_node
            if sep.type == "SEPXYZ" and sep.inputs[0].is_linked and sep.inputs[0].links[0].from_node.type == "TEX_COORD":
                return {"axis": 0 if link.from_socket.name == "X" else 1, "per_unit": node.inputs[1].default_value,
                        "depth": bump.inputs["Distance"].default_value * bump.inputs["Strength"].default_value}
    return None


TILES = {}


def board_tile(d):
    """NB boards across, as a normal map: the V groove between boards exactly as the material's bump defines it
    (height = min(6 x distance to the board edge, 1) x depth), plus what real boards add and the bump lacks: each
    board sits at its own slight tilt and is a little cupped. That is what breaks a lamp's mirror image into
    strips along the boards (reference/IMG_7905.jpg)."""
    key = (round(d["per_unit"], 4), round(d["depth"], 5))
    if key in TILES:
        return TILES[key]
    W = 2048
    x = (np.arange(W) + 0.5) / (W // NB)
    f, idx = x - np.floor(x), np.floor(x).astype(int) % NB
    width_m = 1.0 / d["per_unit"]
    groove = np.where(f < 1 / 6, 1.0, np.where(f > 5 / 6, -1.0, 0.0)) * 6.0 * d["depth"] / width_m
    rng = np.random.default_rng(7)
    slope = groove + rng.uniform(-0.014, 0.014, NB)[idx] + (0.5 - f) * 0.03
    nrm = np.stack([-slope, np.zeros(W), np.ones(W)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    out = np.ones((4, W, 4), np.float32)
    out[..., :3] = (nrm * 0.5 + 0.5)[None]
    path = os.path.join(CACHE, "boards_%d.png" % len(TILES))
    save_bytes(out, path)
    TILES[key] = load_data_image(path, "boards_%d" % len(TILES))
    return TILES[key]


HEIGHT_NORMALS = {}


def height_normal(m, m_per_uv):
    """A normal map from the height image a material's Bump node reads (marquetry, bead lattice, the relief)."""
    b = bsdf(m)
    n = b.inputs["Normal"] if b else None
    if not n or not n.is_linked or n.links[0].from_node.type != "BUMP":
        return None
    bump = n.links[0].from_node
    h = bump.inputs["Height"]
    if not h.is_linked or h.links[0].from_node.type != "TEX_IMAGE" or not h.links[0].from_node.image:
        return None
    img = h.links[0].from_node.image
    if img.name in HEIGHT_NORMALS:
        return HEIGHT_NORMALS[img.name]
    hgt = pixels(img)[..., 0].astype(np.float64)
    depth = bump.inputs["Distance"].default_value * bump.inputs["Strength"].default_value * (-1 if bump.invert else 1)
    texel = max(m_per_uv, 1e-4) / img.size[0]
    du = (np.roll(hgt, -1, 1) - np.roll(hgt, 1, 1)) * 0.5 * depth / texel
    dv = (np.roll(hgt, -1, 0) - np.roll(hgt, 1, 0)) * 0.5 * depth / texel
    nrm = np.stack([-np.clip(du, -2, 2), -np.clip(dv, -2, 2), np.ones_like(du)], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True)
    out = np.ones(hgt.shape + (4,), np.float32)
    out[..., :3] = nrm * 0.5 + 0.5
    path = os.path.join(CACHE, "nrm_%s.png" % os.path.splitext(img.name)[0].replace(".", "_"))
    save_bytes(out, path)
    HEIGHT_NORMALS[img.name] = load_data_image(path, "nrm_" + os.path.splitext(img.name)[0])
    return HEIGHT_NORMALS[img.name]


def metres_per_uv(me, layer, poly_index, scale=1.0):
    """How many metres one UV unit spans on this face (first edge)."""
    p = me.polygons[poly_index]
    l0, l1 = p.loop_indices[0], p.loop_indices[1]
    uv = me.uv_layers[layer].uv
    du = (uv[l1].vector - uv[l0].vector).length
    dx = (me.vertices[me.loops[l1].vertex_index].co - me.vertices[me.loops[l0].vertex_index].co).length * scale
    return dx / du if du > 1e-9 else 1.0


def bake_lightmap(objs, name, size):
    """Diffuse direct + indirect (no surface colour) on the active UV set, dilated and denoised."""
    samples = LM_SAMPLES * (1 if QUICK else LM_BOOST.get(name, 1))
    cache = os.path.join(CACHE, "lm_%s_%d_%d_%s.npy" % (name, size, samples, uv_sig(objs)))
    if REUSE and os.path.exists(cache):
        log("lightmap", name, "from cache")
        return np.load(cache)
    img = new_float("__lm_" + name, size)
    t = time.time()
    bake(objs, "DIFFUSE", img, samples, direct=True, indirect=True)
    px = pixels(img)
    valid = px[..., 3] > 0.5
    log("lightmap", name, size, "baked in %.0fs, coverage %.0f%%" % (time.time() - t, 100 * valid.mean()))
    rgb, _ = dilate(px[..., :3], valid, 12)
    rgb = denoise(rgb)
    rgb = np.maximum(rgb, 0)
    bpy.data.images.remove(img)
    np.save(cache, rgb)
    return rgb


# ------------------------------------------------------------------ 0. chandelier export variants
has_mesh = lambda c: any(o.type == "MESH" for o in c.objects)
EXPORT_COLLS = {c.name[:-len("_export")]: c for c in bpy.data.collections if c.name.endswith("_export") and has_mesh(c)}
if not EXPORT_COLLS:  # a church.blend assembled before assemble.py carried them
    with bpy.data.libraries.load(os.path.join(common.ASSETS, "chandeliers.blend"), link=False) as (src, dst):
        dst.collections = [n for n in src.collections if n.endswith("_export")]
    EXPORT_COLLS = {c.name[:-len("_export")]: c for c in dst.collections if c and has_mesh(c)}
log("chandelier export variants:", sorted(EXPORT_COLLS))

# ------------------------------------------------------------------ 1. environment probe
env_path = os.path.join(LM_DIR, "env.hdr")
if not (REUSE and os.path.exists(env_path)):
    cam = bpy.data.objects.new("__probe", bpy.data.cameras.new("__probe"))
    sc.collection.objects.link(cam)
    cam.data.type = "PANO"
    try:
        cam.data.panorama_type = "EQUIRECTANGULAR"
    except Exception:
        cam.data.cycles.panorama_type = "EQUIRECTANGULAR"
    cam.location = PROBE
    cam.rotation_euler = (math.pi / 2, 0, -math.pi / 2)  # image centre looks along +X: three's equirect convention
    cam.data.clip_start = 0.05
    sc.camera = cam
    sc.cycles.samples = 16 if QUICK else 96
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = ENV_SIZE[0], ENV_SIZE[1], 100
    sc.render.image_settings.file_format = "HDR"
    sc.render.filepath = env_path
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
    sc.camera = None
    log("env probe", "%d KB" % (os.path.getsize(env_path) / 1024))

# ------------------------------------------------------------------ 2. groups: atlas, albedo, join, lightmap
for o in list(sc.objects):  # modifiers applied, parents cleared (world transform kept)
    if o.type != "MESH":
        continue
    if o.modifiers:
        dg = bpy.context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), depsgraph=dg)
        o.modifiers.clear()
        o.data = me
    if o.parent:
        mw = o.matrix_world.copy()
        o.parent = None
        o.matrix_world = mw
bpy.context.view_layer.update()

built = []   # (group name, joined object, lightmap file, albedo image or None, has 'atlas' separate from 'lm')
STATS = {"groups": {}}
for name, colls, lm_size, alb_size in GROUPS:
    objs = [o for c in colls if c in bpy.data.collections for o in bpy.data.collections[c].all_objects
            if o.type == "MESH" and not is_pic(o) and o.name in sc.objects]
    if not objs:
        log("group", name, "is empty")
        continue
    protos = {}
    for o in objs:
        protos.setdefault(o.data.name, o)
    protos = list(protos.values())
    shared = len(protos) < len(objs)
    log("group", name, len(objs), "objects,", len(protos), "meshes,", sum(tris(o) for o in objs), "tris")

    if name in DROP_UNSEEN and not shared:
        t = time.time()
        removed, kept = drop_unseen(objs)
        log("group", name, "dropped %d faces nobody can see, kept %d (%.0fs)" % (removed, kept, time.time() - t))

    # -- albedo atlas
    unwrap(protos, "atlas", 3.0 / (alb_size if shared else min(alb_size, lm_size)))
    sig = uv_sig(protos)
    alb_png = os.path.join(CACHE, "albedo_%s_%d_%s.png" % (name, alb_size, sig))
    if not (REUSE and os.path.exists(alb_png)):
        mats = {s.material for o in protos for s in o.material_slots if s.material}
        ov = EmitOverride(mats)
        img = new_float("__alb_" + name, alb_size)
        t = time.time()
        bake(protos, "EMIT", img, ALB_SAMPLES)
        ov.restore()
        px = pixels(img)
        valid = px[..., 3] > 0.5
        log("albedo", name, alb_size, "baked in %.0fs, coverage %.0f%%" % (time.time() - t, 100 * valid.mean()))
        rgb, _ = dilate(px[..., :3], valid, 16)
        out = np.ones((alb_size, alb_size, 4), np.float32)
        out[..., :3] = lin_to_srgb(rgb)
        save_bytes(out, alb_png)
        bpy.data.images.remove(img)
    albedo = bpy.data.images.load(alb_png)
    albedo.name = "albedo_" + name
    albedo.pack()

    # -- baked normal map (bevels, cushions): only where the highlights need it
    normal = None
    if name in NORMAL_GROUPS:
        nrm_png = os.path.join(CACHE, "normal_%s_%d_%s.png" % (name, alb_size, sig))
        if not (REUSE and os.path.exists(nrm_png)):
            img = new_float("__nrm_" + name, alb_size)
            img.colorspace_settings.name = "Non-Color"
            rb.normal_space = "TANGENT"
            t = time.time()
            bake(protos, "NORMAL", img, 16 if QUICK else 48)
            px = pixels(img)
            save_normal(px[..., :3], px[..., 3] > 0.5, nrm_png)
            bpy.data.images.remove(img)
            log("normal", name, alb_size, "baked in %.0fs" % (time.time() - t))
        normal = load_data_image(nrm_png, "normal_" + name)

    # -- make instances real, join
    for o in objs:
        if o.data.users > 1:
            o.data = o.data.copy()
    select_only(objs)
    bpy.ops.object.join()
    g = bpy.context.view_layer.objects.active
    g.name = "G_" + name
    me = g.data
    me.uv_layers.active = me.uv_layers["atlas"]
    lm = me.uv_layers.new(name="lm", do_init=True)  # a copy of the atlas set
    me.uv_layers.active = lm
    if shared:  # instances sit on top of each other in the atlas: repack so every copy has its own texels
        select_only([g])
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.uv.select_all(action="SELECT")
        pack(2.0 / lm_size)
        bpy.ops.object.mode_set(mode="OBJECT")
    rgb = bake_lightmap([g], name, lm_size)
    g["lm"] = save_rgbm(rgb, "lm_" + name)
    built.append((name, g, albedo, normal))

# ------------------------------------------------------------------ 3. pictures: own meshes, one shared lightmap
pics = [o for o in sc.objects if o.type == "MESH" and is_pic(o)]
for o in pics:
    if o.data.users > 1:
        o.data = o.data.copy()
unwrap(pics, "lm", 3.0 / PICS_LM)
rgb = bake_lightmap(pics, "pics", PICS_LM)
pics_lm = save_rgbm(rgb, "lm_pics")
for o in pics:
    o["lm"] = pics_lm
log("pictures:", len(pics))

# ------------------------------------------------------------------ 4. web materials, UV0 / UV1
WEB = {}


def web_material(key, image=None, color=(1, 1, 1), rough=0.5, metal=0.0, emit=0.0, emit_color=(1, 1, 1),
                 emit_image=False, normal=None, normal_uv="UV0", **props):
    if key in WEB:
        return WEB[key]
    m = bpy.data.materials.new(key)
    m.use_nodes = True
    b = bsdf(m)
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if image:
        uvn = m.node_tree.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = "UV0"
        t = m.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = image
        m.node_tree.links.new(uvn.outputs[0], t.inputs[0])
        m.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
        if emit_image:
            m.node_tree.links.new(t.outputs["Color"], b.inputs["Emission Color"])
    if emit:
        if not emit_image:
            b.inputs["Emission Color"].default_value = (*emit_color, 1)
        b.inputs["Emission Strength"].default_value = emit
    if normal:
        uvn = m.node_tree.nodes.new("ShaderNodeUVMap")
        uvn.uv_map = normal_uv
        t = m.node_tree.nodes.new("ShaderNodeTexImage")
        t.image = normal
        nm = m.node_tree.nodes.new("ShaderNodeNormalMap")
        nm.uv_map = normal_uv
        m.node_tree.links.new(uvn.outputs[0], t.inputs[0])
        m.node_tree.links.new(t.outputs["Color"], nm.inputs["Color"])
        m.node_tree.links.new(nm.outputs["Normal"], b.inputs["Normal"])
    for k, v in props.items():
        m[k] = v
    WEB[key] = m
    return m


def passthrough(orig, i, m_per_uv=1.0):
    return web_material("P_" + orig.name.replace(".", "_"), image=i["image"], rough=0.25 if i.get("coat") else i["rough"],
                        normal=height_normal(orig, m_per_uv),
                        coat=i.get("coat") or 0.0, metal=i["metal"],
                        emit=i["emit"] if i["emit_image"] else 0.0, emit_image=i["emit_image"],
                        tint=list(i["tint"]), kind="image")


def set_uvs(me, uv0, uv1, uv2=None):
    while me.uv_layers:
        me.uv_layers.remove(me.uv_layers[0])
    for nm, data in (("UV0", uv0), ("UV1", uv1)) + ((("UV2", uv2),) if uv2 is not None else ()):
        l = me.uv_layers.new(name=nm, do_init=False)
        l.uv.foreach_set("vector", np.ascontiguousarray(data, np.float32).ravel())
    me.uv_layers["UV0"].active_render = True
    me.uv_layers.active = me.uv_layers["UV0"]
    for ca in list(me.color_attributes):
        me.color_attributes.remove(ca)


for name, g, albedo, normal in built:
    me = g.data
    n_poly = len(me.polygons)
    mat_idx = np.empty(n_poly, np.int32)
    me.polygons.foreach_get("material_index", mat_idx)
    loop_total = np.empty(n_poly, np.int32)
    me.polygons.foreach_get("loop_total", loop_total)
    loop_mat = np.repeat(mat_idx, loop_total)
    atlas, lm = uv_get(me, "atlas"), uv_get(me, "lm")
    uv0 = atlas.copy()
    uv2 = None
    orig_layers = [l.name for l in me.uv_layers if l.name not in ("atlas", "lm")]
    first_poly = {}
    for pi in range(n_poly - 1, -1, -1):
        first_poly[int(mat_idx[pi])] = pi
    new_mats, remap = [], np.zeros(max(1, len(me.materials)), np.int32)
    for si, m in enumerate(me.materials):
        if m is None:
            wm = web_material("%s_matte" % name, image=albedo, normal=normal, rough=0.9, group=name, kind="atlas", gloss="matte")
        else:
            i = info_of(m)
            if i["kind"] == "image":
                layer = i["uv"] if i["uv"] in orig_layers else ("UVMap" if "UVMap" in orig_layers else (orig_layers[0] if orig_layers else None))
                wm = passthrough(m, i, metres_per_uv(me, layer, first_poly[si]) if layer and si in first_poly else 1.0)
                if layer:
                    sel = loop_mat == si
                    uv0[sel] = uv_get(me, layer)[sel]
            elif i["emit"] >= 0.5:
                wm = web_material("E_" + m.name.replace(".", "_"), color=i["color"], rough=i["rough"], metal=i["metal"],
                                  emit=i["emit"], emit_color=i["emit_color"], kind="emit")
            else:
                cls, rough, metal = gloss_class(i)
                detail = board_detail(m) if "UVMap" in orig_layers else None
                if detail:  # boards: the atlas for colour, a tiling groove profile on a third UV set for the highlights
                    if uv2 is None:
                        uv2 = np.zeros_like(atlas)
                    sel = loop_mat == si
                    src = uv_get(me, "UVMap")[sel]
                    uv2[sel, 0] = src[:, detail["axis"]] * detail["per_unit"] / NB
                    uv2[sel, 1] = src[:, 1 - detail["axis"]]
                    wm = web_material("%s_%s_%s" % (name, cls, m.name.replace(".", "_")), image=albedo, rough=rough, metal=metal,
                                      normal=board_tile(detail), normal_uv="UV2", group=name, kind="atlas", gloss=cls,
                                      boards=1, coat=0.12 if cls == "varnish" else 0.0)
                else:
                    wm = web_material("%s_%s" % (name, cls), image=albedo, normal=normal, rough=rough, metal=metal, group=name,
                                      kind="atlas", gloss=cls, coat=0.12 if cls == "varnish" else 0.0)
        if wm not in new_mats:
            new_mats.append(wm)
        remap[si] = new_mats.index(wm)
    set_uvs(me, uv0, lm, uv2)
    me.materials.clear()
    for wm in new_mats:
        me.materials.append(wm)
    me.polygons.foreach_set("material_index", remap[mat_idx])
    me.update()
    STATS["groups"][name] = {"tris": tris(g), "materials": [m.name for m in new_mats]}
    log("group", name, "->", [m.name for m in new_mats])

for o in pics:
    me = o.data
    orig = next((l.name for l in me.uv_layers if l.name != "lm"), "lm")
    set_uvs(me, uv_get(me, orig), uv_get(me, "lm"))
    mats = [s.material for s in o.material_slots]
    me.materials.clear()
    for m in mats:
        i = info_of(m) if m else None
        if i and i["kind"] == "image":
            me.materials.append(passthrough(m, i, metres_per_uv(me, "UV0", 0, o.matrix_world.to_scale().x)))
        else:
            log("WARNING picture without an image material:", o.name, m.name if m else None)
            me.materials.append(web_material("P_flat_" + o.name, color=i["color"] if i else (0.5, 0.5, 0.5), kind="image"))

# ------------------------------------------------------------------ 5. chandeliers
out_coll = bpy.data.collections.new("WebChandeliers")
sc.collection.children.link(out_coll)
ch_objs, ch_tris = [], 0
CH_MATS = {
    "ChandelierCrystal": lambda: web_material("X_crystal", color=(1, 0.95, 0.88), rough=0.05, emit=1.0, emit_color=(1, 0.9, 0.76), kind="crystal"),
    "ChandelierChrome": lambda: web_material("M_chrome", color=(0.8, 0.8, 0.82), rough=0.18, metal=1.0, kind="metal"),
    "ChandelierBeadBand": lambda: web_material("E_beadband", color=(0.42, 0.42, 0.44), rough=0.5, emit=1.2, emit_color=(1, 0.96, 0.9), kind="emit"),
    "ChandelierBulb": lambda: web_material("E_bulb", color=(1, 0.9, 0.75), rough=0.5, emit=45.0, emit_color=(1, 0.9, 0.76), kind="emit"),
}


def ch_material(m):
    return CH_MATS[m.name.split(".")[0]]()


kind_mesh = {}
for kind, coll in EXPORT_COLLS.items():
    crystal, frame = [], []
    for o in coll.objects:
        if o.type != "MESH":
            continue
        c = o.copy()
        c.data = o.data.copy()
        out_coll.objects.link(c)
        (crystal if "crystals" in o.name else frame).append(c)
    meshes = []
    for part, lst in (("X", crystal), ("F", frame)):
        if not lst:
            continue
        select_only(lst)
        bpy.ops.object.join()
        j = bpy.context.view_layer.objects.active
        me = j.data
        mats = [ch_material(s.material) for s in j.material_slots]
        me.materials.clear()
        for m in mats:
            me.materials.append(m)
        while me.uv_layers:
            me.uv_layers.remove(me.uv_layers[0])
        for a in [a for a in me.attributes if a.name in ("sparkle", "_sparkle")]:
            me.attributes.remove(a)
        if part == "X":
            col = me.color_attributes.get("Col")
            me.color_attributes.active_color = col
            me.color_attributes.render_color_index = list(me.color_attributes).index(col)
        else:
            for ca in list(me.color_attributes):
                me.color_attributes.remove(ca)
        me.name = "Ch%s_%s" % (part, kind)
        meshes.append(me)
        bpy.data.objects.remove(j)
    kind_mesh[kind] = meshes

rods = []
for o in list(bpy.data.collections["Chandeliers"].objects):
    if o.type == "EMPTY" and o.instance_collection and o.instance_collection.name in kind_mesh:
        tag = o.name.split("_")[-1]
        for me in kind_mesh[o.instance_collection.name]:
            n = bpy.data.objects.new("%s_%s" % (me.name, tag), me)
            out_coll.objects.link(n)
            n.matrix_world = o.matrix_world
            ch_objs.append(n)
            ch_tris += tris(n)
    elif o.type == "MESH" and o.name.startswith("ChandelierRod"):
        if o.data.users > 1:
            o.data = o.data.copy()
        rods.append(o)
if rods:
    select_only(rods)
    bpy.ops.object.join()
    r = bpy.context.view_layer.objects.active
    r.name = "ChandelierRods"
    r.data.materials.clear()
    r.data.materials.append(CH_MATS["ChandelierChrome"]())
    ch_objs.append(r)
    ch_tris += tris(r)
bpy.context.view_layer.update()
log("chandeliers:", len(ch_objs), "nodes,", ch_tris, "tris")

# ------------------------------------------------------------------ 6. export
# what the web needs to know rides in the scene extras (three: gltf.scene.userData)
to3 = lambda v: [v[0], v[2], -v[1]]
sc["lm_range"] = RGBM_RANGE
sc["exposure"] = EXPOSURE
sc["view_transform"] = VIEW
sc["env"] = "lm/env.hdr"
sc["probe"] = to3(PROBE)
sc["box_min"] = [-common.NAVE_W / 2, 0.0, -common.NAVE_L - 0.3]
sc["box_max"] = [common.NAVE_W / 2, common.CEIL_H, 0.0]
sc["quick"] = QUICK
# the chandelier lamps, for the web's specular highlights on varnish and metal: x, y, z (three), radiance of the
# lamp's sphere (a Blender point light of P watts and radius r looks like a sphere of radiance P / (4 pi^2 r^2)), r
lamps = []
for o in bpy.data.objects:
    if o.type == "LIGHT" and o.data.type == "POINT" and o.name in sc.objects:
        r = max(o.data.shadow_soft_size, 0.05)
        p = o.matrix_world.translation
        lamps += [p.x, p.z, -p.y, o.data.energy / (4 * math.pi ** 2 * r * r), r]
        sc["lamp_color"] = list(o.data.color)
sc["lamps"] = lamps

export_objs = [g for _, g, _, _ in built] + pics + ch_objs
select_only(export_objs)
raw = os.path.join(CACHE, "church_raw.glb")
bpy.ops.export_scene.gltf(
    filepath=raw, use_selection=True, export_format="GLB", export_yup=True, export_apply=False,
    export_texcoords=True, export_normals=True, export_materials="EXPORT", export_extras=True,
    export_image_format="WEBP", export_image_quality=86,
    export_vertex_color="ACTIVE", export_all_vertex_colors=False, export_active_vertex_color_when_no_material=True,
    export_cameras=False, export_lights=False, export_animations=False, export_skins=False, export_morph=False)
log("raw glb %.1f MB" % (os.path.getsize(raw) / 1048576))

final = os.path.join(PUBLIC, "church.glb")
cli = next((p for p in (os.environ.get("GLTF_TRANSFORM", ""),
                        os.path.join(ROOT, "web/node_modules/.bin/gltf-transform"),
                        os.path.expanduser("~/dev/portfolio/studio/node_modules/.bin/gltf-transform")) if p and os.path.exists(p)), None)
if cli:
    env = dict(os.environ, PATH=os.environ.get("PATH", "") + ":/opt/homebrew/bin:/usr/local/bin")
    subprocess.run([cli, "optimize", raw, final, "--compress", "meshopt", "--texture-compress", "false",
                    "--instance", "true", "--instance-min", "2", "--join", "false", "--flatten", "false",
                    "--palette", "false", "--simplify", "false", "--weld", "true", "--prune", "true",
                    "--prune-attributes", "false", "--resample", "false"], check=True, env=env)
else:
    log("WARNING: gltf-transform not found, church.glb is not meshopt-compressed")
    shutil.copy(raw, final)

STATS.update({
    "quick": QUICK, "lm_samples": LM_SAMPLES,
    "tris": {"groups": sum(v["tris"] for v in STATS["groups"].values()), "pictures": sum(tris(o) for o in pics),
             "chandeliers": ch_tris},
    "pictures": sorted(o.name for o in pics),
    "materials": sorted(WEB),
    "glb_mb": round(os.path.getsize(final) / 1048576, 2),
    "lm_files": {f: round(os.path.getsize(os.path.join(LM_DIR, f)) / 1024) for f in sorted(os.listdir(LM_DIR))},
    "seconds": round(time.time() - T0),
})
STATS["tris"]["total"] = sum(STATS["tris"].values())
with open(os.path.join(HERE, "export_report.json"), "w") as f:
    json.dump(STATS, f, indent=1)
log("DONE", json.dumps({k: STATS[k] for k in ("tris", "glb_mb", "lm_files", "seconds")}))
