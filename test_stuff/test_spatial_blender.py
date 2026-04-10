import bpy
import numpy as np

def test():
    # Load FBX
    fbx_path = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\MavuikaBodyBody.fbx"
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.import_scene.fbx(filepath=fbx_path)
    obj = bpy.context.selected_objects[0]
    
    # Load buf
    buf_path = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\MavuikaBodyPosition.buf"
    with open(buf_path, 'rb') as f:
        data = f.read()
    buf_f32 = np.frombuffer(data, dtype=np.float32).reshape(-1, 10)
    
    # Simulate puppet_master_ops Fast Path block
    ba_co = np.array([v.co for v in obj.data.vertices], dtype=np.float32)
    vb_off = 5462
    vb_cnt = 8787
    
    buf_slice = buf_f32[vb_off : vb_off + vb_cnt, :3]
    
    print("Testing KDTree...")
    try:
        from scipy.spatial import KDTree
        kdt = KDTree(ba_co)
        dists, nearest_idx = kdt.query(buf_slice, workers=-1)
        max_dist = np.max(dists)
        print(f"Max dist: {max_dist}")
        
        # Test shape assignment
        # delta is hypothetical
        delta = np.zeros_like(ba_co)
        delta_mapped = delta[nearest_idx]
        
    except Exception as e:
        import traceback
        print("EXCEPTION:", traceback.format_exc())

test()
