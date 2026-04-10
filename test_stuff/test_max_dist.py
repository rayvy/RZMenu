import bpy
import numpy as np
import sys
import os

def test_spatial():
    from scipy.spatial import KDTree
    
    buf_path = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\MavuikaBodyPosition.buf"
    with open(buf_path, 'rb') as f:
        data = f.read()
    
    buf_f32 = np.frombuffer(data, dtype=np.float32).reshape(-1, 10)[:, :3]
    print(f"Buf size: {len(buf_f32)}")
    
    fbx_path = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\MavuikaBodyBody.fbx"
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()
    bpy.ops.import_scene.fbx(filepath=fbx_path)
    
    obj = bpy.context.selected_objects[0]
    
    # We evaluate it to ensure modifiers are applied if any (although there shouldn't be for ba_co)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    
    ba_co = np.array([v.co for v in mesh.vertices], dtype=np.float32)
    print(f"Blender obj vertices: {len(ba_co)}")
    
    kdt = KDTree(ba_co)
    
    # Check all possible offsets to see if any matches perfectly
    # We know exporter count for BodyBody is 8787
    vb_cnt = 8787
    
    # Instead of trusting vb_off, let's search for the best offset!
    best_offset = -1
    best_max_dist = float('inf')
    
    # Since head is 5462, let's check around 5462
    for offset in [0, 5462, 5462+200, 18848-8787]:
        if offset + vb_cnt > len(buf_f32): continue
        buf_slice = buf_f32[offset:offset+vb_cnt]
        dists, _ = kdt.query(buf_slice, workers=-1)
        max_d = np.max(dists)
        print(f"Offset {offset}: max dist = {max_d:.6f}, mean dist = {np.mean(dists):.6f}")
        
    eval_obj.to_mesh_clear()

test_spatial()
