import numpy as np

def read_obj_verts(path):
    verts = []
    with open(path, 'r') as f:
        for line in f:
            if line.startswith('v '):
                parts = line.strip().split()
                verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return np.array(verts, dtype=np.float32)

def test_spatial():
    from scipy.spatial import KDTree
    
    buf_path = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\MavuikaBodyPosition.buf"
    with open(buf_path, 'rb') as f:
        data = f.read()
    
    buf_f32 = np.frombuffer(data, dtype=np.float32).reshape(-1, 10)[:, :3]
    print(f"Buf size: {len(buf_f32)}")
    
    obj_path = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\MavuikaBodyBody.obj"
    ba_co = read_obj_verts(obj_path)
    print(f"Blender obj vertices: {len(ba_co)}")
    
    kdt = KDTree(ba_co)
    
    vb_cnt = 8787
    
    # BodyBody offset is likely 5462
    for offset in [0, 5462, 14249]:
        if offset + vb_cnt > len(buf_f32): continue
        buf_slice = buf_f32[offset:offset+vb_cnt]
        dists, _ = kdt.query(buf_slice, workers=-1)
        max_d = np.max(dists)
        print(f"Offset {offset}: max dist = {max_d:.6f}, mean dist = {np.mean(dists):.6f}")

if __name__ == "__main__":
    test_spatial()
