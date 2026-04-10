import os
import struct
import numpy as np

def test_duplicates():
    buf_path = r"C:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\test_stuff\MavuikaBodyPosition.buf"
    
    with open(buf_path, "rb") as f:
        data = f.read()
    
    stride = 40
    num_verts = len(data) // stride
    print(f"Total buffer vertices: {num_verts}")
    
    buf_f32 = np.frombuffer(data, dtype=np.float32).reshape(num_verts, stride // 4)
    # Positions are first 3 floats (XYZ)
    coords = buf_f32[:, :3]
    
    # BodyDress exported vertices = 4599. BodyBody = 8787.
    # Where does BodyBody start? The user says it grouped them...
    # BodyDress offset = ? Maybe it's sequential. Let's find unique coords.
    
    unique_coords, indices, counts = np.unique(coords, axis=0, return_index=True, return_counts=True)
    print(f"Unique coordinates across entire buffer: {len(unique_coords)}")
    
    # Let's see how many have completely identical coords
    duplicate_count = num_verts - len(unique_coords)
    print(f"Number of completely identical positional coordinates (duplicates) in buffer: {duplicate_count}")

if __name__ == "__main__":
    test_duplicates()
