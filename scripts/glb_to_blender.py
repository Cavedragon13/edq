"""Import a 3D Asset Studio GLB into a ready-to-use Blender scene.

Run headless (the folder must contain model.glb):
  blender -b --python scripts/glb_to_blender.py -- /home/edq/ai_generated/asset3d/<folder>
Outputs in that folder: mesh.blend, mesh_front.png, mesh_34.png

The GLB already carries PBR materials (base color, metallic/roughness, normal,
AO), so the glTF importer builds the shader graph; this script only frames it,
lights it and saves. Called by the 3D Asset Studio "Make Blender scene" button.
"""
import os
import sys

import bpy
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
if not argv:
    sys.exit("usage: blender -b --python glb_to_blender.py -- <asset folder>")
HERE = os.path.abspath(argv[0])
HEIGHT = 1.2   # largest dimension after scaling (Blender units)

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=os.path.join(HERE, "model.glb"))
meshes = [o for o in scene.objects if o.type == 'MESH']
if not meshes:
    sys.exit("no mesh in model.glb")

# Parent everything under one empty so the asset moves/scales as a unit.
root = bpy.data.objects.new("Asset", None)
scene.collection.objects.link(root)
for ob in scene.objects:
    if ob.parent is None and ob is not root:
        ob.parent = root
bpy.context.view_layer.update()

corners = [ob.matrix_world @ Vector(c) for ob in meshes for c in ob.bound_box]
lo = Vector((min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners)))
hi = Vector((max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners)))
scale = HEIGHT / max(hi - lo)
root.scale = (scale, scale, scale)
root.location = (-(lo.x + hi.x) / 2 * scale, -(lo.y + hi.y) / 2 * scale, -lo.z * scale)  # centered, on the floor
bpy.context.view_layer.update()
mid_z = (hi.z - lo.z) * scale / 2
target = Vector((0, 0, mid_z))

cam_data = bpy.data.cameras.new("Camera")
cam_data.lens = 70
cam = bpy.data.objects.new("Camera", cam_data)
scene.collection.objects.link(cam)
scene.camera = cam


def aim(ob, loc):
    ob.location = loc
    ob.rotation_euler = (target - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()


for name, loc, energy in [("Key", (-2.0, -3.0, 3.0), 400), ("Fill", (2.5, -2.0, 1.5), 150), ("Rim", (0.0, 3.0, 2.5), 250)]:
    ld = bpy.data.lights.new(name, 'AREA')
    ld.energy, ld.size = energy, 2.0
    lo_ob = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(lo_ob)
    aim(lo_ob, loc)

world = bpy.data.worlds.new("World")
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.05, 0.05, 0.06, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
scene.world = world

scene.render.resolution_x, scene.render.resolution_y = 900, 1200
aim(cam, (0.0, -4.2, mid_z))
blend_path = os.path.join(HERE, "mesh.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path)
print(f"saved {blend_path}")

# Quick previews: workbench showing the imported base-color textures.
scene.render.engine = 'BLENDER_WORKBENCH'
scene.display.shading.light = 'STUDIO'
scene.display.shading.color_type = 'TEXTURE'
for tag, loc in [("front", (0.0, -4.2, mid_z)), ("34", (-3.0, -3.0, HEIGHT * 0.75))]:
    aim(cam, loc)
    scene.render.filepath = os.path.join(HERE, f"mesh_{tag}.png")
    bpy.ops.render.render(write_still=True)
print("done")
