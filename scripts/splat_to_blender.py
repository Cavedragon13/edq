"""Build a colored mesh in Blender from a TripoSplat splat folder.

Run headless (the folder must contain splat.ply):
  blender -b --python scripts/splat_to_blender.py -- /home/edq/ai_generated/triposplat/<folder>
Outputs in that folder: mesh.blend, mesh_front.png, mesh_34.png

Called by the TripoSplat Dragonsuite service's "Make Blender mesh" button.
"""
import os
import sys
import numpy as np
import bpy
from mathutils import Vector, kdtree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    sys.exit("usage: blender -b --python splat_to_blender.py -- <splat folder>")
HERE = os.path.abspath(argv[0])
PLY = os.path.join(HERE, "splat.ply")
HEIGHT = 1.2          # final character height in Blender units (m)
OPACITY_MIN = 0.3     # drop faint floaters
RADIUS = 0.009        # point radius for volume fusing (after scaling)
VOXEL = 0.0035        # voxel size for the surface mesh
K_COLOR = 8           # neighbours averaged per mesh vertex

# ---------- load splat ----------
raw = open(PLY, "rb").read()
start = raw.index(b"end_header\n") + len(b"end_header\n")
a = np.frombuffer(raw[start:], dtype="<f4").reshape(-1, 17)
op = 1.0 / (1.0 + np.exp(-a[:, 9]))
keep = op > OPACITY_MIN
a, op = a[keep], op[keep]

# TripoSplat uses OpenCV axes (Y down, character faces +X).
# Blender: Z up, front faces -Y.
x, y, z = a[:, 0], a[:, 1], a[:, 2]
pts = np.stack([z, -x, -y], axis=1)
pts -= np.array([(pts[:, 0].min() + pts[:, 0].max()) / 2,
                 (pts[:, 1].min() + pts[:, 1].max()) / 2,
                 pts[:, 2].min()])
pts *= HEIGHT / (pts.max(0) - pts.min(0)).max()   # largest dimension = HEIGHT
MID_Z = pts[:, 2].max() / 2

srgb = np.clip(0.5 + 0.28209479 * a[:, 6:9], 0.0, 1.0)
lin = np.where(srgb <= 0.04045, srgb / 12.92, ((srgb + 0.055) / 1.055) ** 2.4)
print(f"splat points kept: {len(pts)}")

# ---------- fresh scene ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

def colored_mesh(name, verts, colors):
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(verts))
    me.vertices.foreach_set("co", verts.astype(np.float32).ravel())
    ca = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
    rgba = np.concatenate([colors, np.ones((len(colors), 1))], axis=1).astype(np.float32)
    ca.data.foreach_set("color", rgba.ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    scene.collection.objects.link(ob)
    return ob

points_ob = colored_mesh("SplatPoints", pts, lin)

# ---------- points -> volume -> mesh via Geometry Nodes ----------
ng = bpy.data.node_groups.new("SplatToSurface", 'GeometryNodeTree')
ng.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
ng.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
n_in = ng.nodes.new("NodeGroupInput")
n_out = ng.nodes.new("NodeGroupOutput")
m2p = ng.nodes.new("GeometryNodeMeshToPoints")
p2v = ng.nodes.new("GeometryNodePointsToVolume")
v2m = ng.nodes.new("GeometryNodeVolumeToMesh")

def set_input(node, name, value):
    for s in node.inputs:
        if s.name == name:
            s.default_value = value
            return
    raise KeyError(f"{node.bl_idname} has no input {name!r}: {[s.name for s in node.inputs]}")

def set_mode(node, value):
    # Resolution mode is a node property in older Blender, a menu socket in newer.
    if hasattr(node, "resolution_mode"):
        node.resolution_mode = value
    else:
        set_input(node, "Resolution Mode", {"VOXEL_SIZE": "Size", "VOXEL_AMOUNT": "Amount", "GRID": "Grid"}.get(value, value))

set_input(m2p, "Radius", RADIUS)
set_mode(p2v, 'VOXEL_SIZE')
set_input(p2v, "Voxel Size", VOXEL)
set_input(p2v, "Radius", RADIUS)
set_input(p2v, "Density", 1.0)
set_mode(v2m, 'GRID')
set_input(v2m, "Threshold", 0.3)

ng.links.new(n_in.outputs[0], m2p.inputs["Mesh"])
ng.links.new(m2p.outputs["Points"], p2v.inputs["Points"])
ng.links.new(p2v.outputs["Volume"], v2m.inputs["Volume"])
ng.links.new(v2m.outputs["Mesh"], n_out.inputs[0])

mod = points_ob.modifiers.new("SplatToSurface", 'NODES')
mod.node_group = ng
dg = bpy.context.evaluated_depsgraph_get()
surf_me = bpy.data.meshes.new_from_object(points_ob.evaluated_get(dg))
points_ob.modifiers.remove(mod)
surf_me.name = "SplatMesh"
body = bpy.data.objects.new("SplatMesh", surf_me)
scene.collection.objects.link(body)
print(f"raw surface: {len(surf_me.vertices)} verts, {len(surf_me.polygons)} faces")

# light smoothing + decimate to a workable count
bpy.context.view_layer.objects.active = body
body.select_set(True)
sm = body.modifiers.new("Smooth", 'SMOOTH')
sm.factor, sm.iterations = 0.5, 3
dec = body.modifiers.new("Decimate", 'DECIMATE')
target = 250_000
dec.ratio = min(1.0, target / max(1, len(surf_me.polygons)))
bpy.ops.object.modifier_apply(modifier="Smooth")
bpy.ops.object.modifier_apply(modifier="Decimate")
me = body.data
print(f"final surface: {len(me.vertices)} verts, {len(me.polygons)} faces")

# ---------- transfer splat colors to mesh vertices ----------
tree = kdtree.KDTree(len(pts))
for i, p in enumerate(pts):
    tree.insert(p, i)
tree.balance()
nv = len(me.vertices)
co = np.empty(nv * 3, dtype=np.float32)
me.vertices.foreach_get("co", co)
co = co.reshape(-1, 3)
out = np.empty((nv, 4), dtype=np.float32)
out[:, 3] = 1.0
for i in range(nv):
    hits = tree.find_n(co[i], K_COLOR)
    idx = [h[1] for h in hits]
    d = np.array([h[2] for h in hits]) + 1e-5
    w = op[idx] / d
    out[i, :3] = (lin[idx] * w[:, None]).sum(0) / w.sum()
ca = me.color_attributes.new("Col", 'FLOAT_COLOR', 'POINT')
ca.data.foreach_set("color", out.ravel())
me.color_attributes.active_color = ca
for poly in me.polygons:
    poly.use_smooth = True

# ---------- material ----------
mat = bpy.data.materials.new("Splat_VertexColor")
nt = mat.node_tree
bsdf = nt.nodes.get("Principled BSDF")
attr = nt.nodes.new("ShaderNodeAttribute")
attr.attribute_name = "Col"
attr.location = (-300, 200)
nt.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.6
me.materials.append(mat)
pmat = mat.copy()
pmat.name = "SplatPoints_VertexColor"
points_ob.data.materials.append(pmat)

points_ob.hide_render = True
points_ob.hide_set(True)
body.select_set(True)
bpy.context.view_layer.objects.active = body

# ---------- camera, lights, world ----------
cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 70
cam = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam
target_pt = Vector((0, 0, MID_Z))

def aim(ob, loc):
    ob.location = loc
    ob.rotation_euler = (target_pt - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()

for name, loc, energy in [("Key", (-2.0, -3.0, 3.0), 400), ("Fill", (2.5, -2.0, 1.5), 150), ("Rim", (0.0, 3.0, 2.5), 250)]:
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy, ld.size = energy, 2.0
    lo = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo)
    aim(lo, loc)

world = bpy.data.worlds.new("World")
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.06, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
scene.world = world

scene.render.resolution_x, scene.render.resolution_y = 900, 1200
blend_path = os.path.join(HERE, "mesh.blend")
aim(cam, (0.0, -4.2, MID_Z))
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"saved {blend_path}")

# ---------- quick previews (workbench, vertex colors) ----------
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'VERTEX'
for tag, loc in [("front", (0.0, -4.2, MID_Z)), ("34", (-3.0, -3.0, HEIGHT * 0.75))]:
    aim(cam, loc)
    scene.render.filepath = os.path.join(HERE, f"mesh_{tag}.png")
    bpy.ops.render.render(write_still=True)
print("done")
