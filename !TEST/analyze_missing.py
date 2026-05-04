import os
from analyze_buffers import parse_buf

def analyze_missing():
    base_dir = r"c:\Users\Rayvy\AppData\Roaming\Blender Foundation\Blender\5.0\scripts\addons\RZMenu\!TEST"
    
    vb0_c = parse_buf(os.path.join(base_dir, "Component6_VB0_CORRECT_EXAMPLE.buf"))
    sk_c  = parse_buf(os.path.join(base_dir, "Component6_Boobies_CORRECT_EXAMPLE.buf"))
    
    vb0_u = parse_buf(os.path.join(base_dir, "Component6_VB0_UNCORRECT_EXAMPLE.buf"))
    sk_u  = parse_buf(os.path.join(base_dir, "Component6_Boobies_UNCORRECT_EXAMPLE.buf"))
    
    # Create dict of base position -> delta
    # Since positions might have slight floating point differences, round to 4 decimals
    
    def get_deltas(vb0, sk):
        res = {}
        for i in range(len(vb0)):
            dx = sk[i][0] - vb0[i][0]
            dy = sk[i][1] - vb0[i][1]
            dz = sk[i][2] - vb0[i][2]
            key = (round(vb0[i][0], 4), round(vb0[i][1], 4), round(vb0[i][2], 4))
            # Store delta and slot index
            res[key] = (dx, dy, dz, i)
        return res

    dict_c = get_deltas(vb0_c, sk_c)
    dict_u = get_deltas(vb0_u, sk_u)
    
    print("Vertices with significant delta in CORRECT, but NO DELTA in UNCORRECT:")
    missing_count = 0
    for key, (dx, dy, dz, slot) in dict_c.items():
        if abs(dx) > 1e-4 or abs(dy) > 1e-4 or abs(dz) > 1e-4:
            if key in dict_u:
                ux, uy, uz, uslot = dict_u[key]
                if abs(ux) < 1e-4 and abs(uy) < 1e-4 and abs(uz) < 1e-4:
                    print(f"  Pos: {key} (Correct Slot {slot} -> Uncorrect Slot {uslot})")
                    print(f"    Correct Delta: ({dx:.4f}, {dy:.4f}, {dz:.4f})")
                    print(f"    Uncorrect Delta: ({ux:.4f}, {uy:.4f}, {uz:.4f})")
                    missing_count += 1
            else:
                print(f"  Pos {key} not found in Uncorrect!")
                missing_count += 1
                
    print(f"\nTotal missing: {missing_count}")
    
    print("\nVertices with WRONG delta in UNCORRECT (difference > 0.001):")
    wrong_count = 0
    for key, (dx, dy, dz, slot) in dict_c.items():
        if abs(dx) > 1e-4 or abs(dy) > 1e-4 or abs(dz) > 1e-4:
            if key in dict_u:
                ux, uy, uz, uslot = dict_u[key]
                diff = abs(ux - dx) + abs(uy - dy) + abs(uz - dz)
                if diff > 0.001 and (abs(ux) > 1e-4 or abs(uy) > 1e-4 or abs(uz) > 1e-4):
                    print(f"  Pos: {key} (Correct Slot {slot} -> Uncorrect Slot {uslot})")
                    print(f"    Correct Delta: ({dx:.4f}, {dy:.4f}, {dz:.4f})")
                    print(f"    Uncorrect Delta: ({ux:.4f}, {uy:.4f}, {uz:.4f})")
                    wrong_count += 1
    print(f"\nTotal wrong: {wrong_count}")

if __name__ == '__main__':
    analyze_missing()
