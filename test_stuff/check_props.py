import bpy

def test():
    fbx_path = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\MavuikaBodyBody.fbx"
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.import_scene.fbx(filepath=fbx_path)
    obj = bpy.context.selected_objects[0]
    for key, value in obj.items():
        print(f"{key}: {value}")

test()
