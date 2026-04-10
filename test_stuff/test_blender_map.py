import bpy
import sys
import os

addon_dir = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu"
if addon_dir not in sys.path:
    sys.path.append(addon_dir)

from operators.export_cache import reconstruct_vertex_map_from_mesh, get_vblayout_semantics

def run_test():
    # Load the FBX object into current scene to test
    fbx_path = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\MavuikaBodyBody.fbx"
    
    # clear scene
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    
    bpy.ops.import_scene.fbx(filepath=fbx_path)
    
    obj = bpy.context.selected_objects[0]
    print(f"Loaded object: {obj.name}")
    print(f"Vertices: {len(obj.data.vertices)}")
    
    layout = get_vblayout_semantics(obj)
    print(f"Layout semantics: {layout}")
    
    try:
        v_map = reconstruct_vertex_map_from_mesh(obj.data, obj)
        if v_map is None:
            print("v_map is None!")
        else:
            print(f"v_map length: {len(v_map)}")
    except Exception as e:
        print(f"Exception: {e}")

run_test()
