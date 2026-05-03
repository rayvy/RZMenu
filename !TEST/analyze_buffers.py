import struct
import sys
import os

def parse_buf(filepath, stride=48):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return []
    
    with open(filepath, 'rb') as f:
        data = f.read()
    
    num_verts = len(data) // stride
    verts = []
    for i in range(num_verts):
        offset = i * stride
        # Endfield VB0 usually starts with px, py, pz (3 floats)
        px, py, pz = struct.unpack('<fff', data[offset:offset+12])
        verts.append((px, py, pz))
    return verts

def analyze():
    base_dir = r"c:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\!TEST"
    
    vb0_c = parse_buf(os.path.join(base_dir, "Component6_VB0_CORRECT_EXAMPLE.buf"))
    sk_c  = parse_buf(os.path.join(base_dir, "Component6_Boobies_CORRECT_EXAMPLE.buf"))
    
    vb0_u = parse_buf(os.path.join(base_dir, "Component6_VB0_UNCORRECT_EXAMPLE.buf"))
    sk_u  = parse_buf(os.path.join(base_dir, "Component6_Boobies_UNCORRECT_EXAMPLE.buf"))
    
    print("=== CORRECT EXAMPLE ===")
    print(f"VB0 length: {len(vb0_c)}, SK length: {len(sk_c)}")
    
    deltas_c = []
    for i in range(len(vb0_c)):
        dx = sk_c[i][0] - vb0_c[i][0]
        dy = sk_c[i][1] - vb0_c[i][1]
        dz = sk_c[i][2] - vb0_c[i][2]
        if abs(dx) > 1e-5 or abs(dy) > 1e-5 or abs(dz) > 1e-5:
            deltas_c.append((i, dx, dy, dz, vb0_c[i]))
            
    print(f"Non-zero deltas: {len(deltas_c)}")
    print("First 5 deltas:")
    for i, dx, dy, dz, base in deltas_c[:5]:
        print(f"  Slot {i}: base=({base[0]:.4f}, {base[1]:.4f}, {base[2]:.4f}) delta=({dx:.4f}, {dy:.4f}, {dz:.4f})")

    print("\n=== UNCORRECT EXAMPLE ===")
    print(f"VB0 length: {len(vb0_u)}, SK length: {len(sk_u)}")
    
    deltas_u = []
    for i in range(min(len(vb0_u), len(sk_u))):
        dx = sk_u[i][0] - vb0_u[i][0]
        dy = sk_u[i][1] - vb0_u[i][1]
        dz = sk_u[i][2] - vb0_u[i][2]
        if abs(dx) > 1e-5 or abs(dy) > 1e-5 or abs(dz) > 1e-5:
            deltas_u.append((i, dx, dy, dz, vb0_u[i]))
            
    print(f"Non-zero deltas: {len(deltas_u)}")
    print("First 5 deltas:")
    for i, dx, dy, dz, base in deltas_u[:5]:
        print(f"  Slot {i}: base=({base[0]:.4f}, {base[1]:.4f}, {base[2]:.4f}) delta=({dx:.4f}, {dy:.4f}, {dz:.4f})")

if __name__ == '__main__':
    analyze()
