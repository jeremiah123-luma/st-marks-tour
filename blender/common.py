"""Shared dimensions and helpers for every church-tour Blender script.

Units are metres. Facing the altar: +Y is toward the altar, +X is to the right,
+Z is up. Origin = floor, centre of the nave, at the inside face of the BACK wall.
Scale v3 (Nov 20: back windows sit in the corners, bay 3.5 m, so the nave is
shorter than v2; pews are on a tight 0.8 m pitch). Scale v2: no scan is coming. Anchored on the back-right exit door
(0.91 m) sitting under a window of the same width, so glass width = 1.0 m; bay
spacing, wall height and length follow from the 2019 side-wall photo. Estimates, so always read them
from here; never hardcode a copy.
"""
import os
import bpy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEX = os.path.join(ROOT, "textures")
ASSETS = os.path.join(ROOT, "blender", "assets")
PREVIEWS = os.path.join(ROOT, "blender", "previews")

# ---- room -------------------------------------------------------------
NAVE_W = 11.0          # inside width
NAVE_L = 17.5          # back wall to the FRONT face of the iconostasis
WALL_H = 6.6           # white wall height, where the wood ceiling cove starts
CEIL_H = 6.6           # flat centre of the wood ceiling
WAINSCOT_H = 1.0       # wood wainscot + heater covers along side walls

# ---- floor ------------------------------------------------------------
AISLE_W = 1.5          # centre aisle, runner is 1.1 wide
RUNNER_W = 1.1
CHORUS_Y = 12.9        # front edge of the raised chorus platform
CHORUS_H = 0.30        # two steps

# ---- pews -------------------------------------------------------------
PEW_ROWS = 12          # per block
PEW_PITCH = 0.80
PEW_FIRST_Y = 2.6      # back-most row (seat back position)
PEW_LEN = 3.85         # x from +-0.75 to +-4.6
PEW_SEAT_H = 0.44
PEW_BACK_H = 0.92

# ---- side walls (front = near altar) ------------------------------------
WINDOW_Y = [15.7, 12.2, 8.7, 5.2, 1.7]     # front -> back, both walls
WINDOW_W = 1.0 
WINDOW_SILL = 1.15
WINDOW_TOP = 5.05      # top of the round arch
SHORT_WINDOW_SILL = 3.2  # right wall, back-most window (above the stairs)
BRACKET_Y = [13.95, 10.45, 6.95, 3.45]      # ceiling brackets, between windows
SHRINE_Z = 1.75        # bottom shelf of a wall shrine
SHRINE_W, SHRINE_H = 0.95, 1.85

# name of the texture for each slot, front -> back. None = no shrine there.
LEFT_WINDOWS = ["abraham", "david", "three_youths", "moses", "daniel"]
RIGHT_WINDOWS = ["storm", "samaritan", "egypt", "lazarus", "healing"]
LEFT_SHRINES = [(13.95, "annunciation"), (10.45, "nativity"), (6.95, "antony"), (2.9, "mina")]
RIGHT_SHRINES = [(13.95, "pentecost"), (10.45, "ascension"), (6.95, "resurrection"), (2.9, "abraam")]

# ---- iconostasis --------------------------------------------------------
ICONO_H = 3.9          # top of the apostle row cornice
ICONO_D = 0.30
DOOR_W, DOOR_H = 1.3, 2.2          # arched openings
SIDE_DOOR_X = 2.5                  # centre of each side door

BLENDER = "/Applications/Blender.app/Contents/MacOS/Blender"


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    s = bpy.context.scene
    s.unit_settings.system = "METRIC"
    return s


def collection(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


def bsdf(mat):
    return next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")


def flat_material(name, rgb, rough=0.5, metallic=0.0):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = bsdf(m)
    b.inputs["Base Color"].default_value = (*rgb, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    return m


def image_material(name, rel_path, fallback=(0.75, 0.55, 0.2), rough=0.45, emit=0.0):
    """Material from textures/<rel_path>. Falls back to a flat colour when the
    file is not there yet, so scripts keep working before textures land."""
    path = os.path.join(TEX, rel_path)
    if not os.path.exists(path):
        return flat_material(name, fallback, rough)
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = bsdf(m)
    tex = m.node_tree.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(path, check_existing=True)
    m.node_tree.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough
    if emit:
        m.node_tree.links.new(tex.outputs["Color"], b.inputs["Emission Color"])
        b.inputs["Emission Strength"].default_value = emit
    return m


def save(name):
    """Save this asset as blender/assets/<name>.blend."""
    os.makedirs(ASSETS, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ASSETS, name + ".blend"))


def render_preview(name, cam_loc, look_at, lens=35, size=(960, 720), samples=48):
    """Quick Cycles preview to blender/previews/<name>.png. Add your own lights."""
    from mathutils import Vector
    s = bpy.context.scene
    cam = bpy.data.objects.new("PreviewCam", bpy.data.cameras.new("PreviewCam"))
    s.collection.objects.link(cam)
    cam.location = cam_loc
    d = Vector(look_at) - Vector(cam_loc)
    cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    cam.data.lens = lens
    s.camera = cam
    try:
        s.render.engine = "CYCLES"
    except TypeError:
        pass
    s.cycles.samples = samples
    s.cycles.use_denoising = True
    s.render.resolution_x, s.render.resolution_y = size
    s.render.filepath = os.path.join(PREVIEWS, name + ".png")
    os.makedirs(PREVIEWS, exist_ok=True)
    bpy.ops.render.render(write_still=True)
    bpy.data.objects.remove(cam)
