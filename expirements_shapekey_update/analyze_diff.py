import struct
import os

file1 = r"G:\XXMI\EFMI\Mods\YvonneCasualX\Meshes\Component6_VB0.buf"
file2 = r"G:\XXMI\EFMI\Mods\YvonneCasualX\Blend\Component6_VB0_Sport.buf"

def analyze():
    if not os.path.exists(file1) or not os.path.exists(file2):
        print(f"Error: Files not found.\n{file1}\n{file2}")
        return

    with open(file1, "rb") as f1, open(file2, "rb") as f2:
        d1 = f1.read()
        d2 = f2.read()

    if len(d1) != len(d2):
        print(f"Sizes differ: {len(d1)} vs {len(d2)}")
        return

    stride = 16
    count = len(d1) // stride
    diff_count = 0
    max_dist = 0
    
    for i in range(count):
        offset = i * stride
        v1 = struct.unpack_from("<3f", d1, offset)
        v2 = struct.unpack_from("<3f", d2, offset)
        
        # Check remaining 4 bytes (stride 16)
        rest1 = d1[offset+12:offset+16]
        rest2 = d2[offset+12:offset+16]
        
        if v1 != v2:
            diff_count += 1
            dist = sum((a-b)**2 for a, b in zip(v1, v2))**0.5
            max_dist = max(max_dist, dist)
        
        if rest1 != rest2:
            print(f"Non-position data changed at vertex {i}!")

    print(f"Total vertices: {count}")
    print(f"Changed vertices: {diff_count}")
    print(f"Max distance change: {max_dist}")

if __name__ == "__main__":
    analyze()
