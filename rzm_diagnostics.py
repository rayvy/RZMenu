import bpy
import os

def run_diagnostics():
    col_name = "SKIRK EXPORT"
    col = bpy.data.collections.get(col_name)
    
    print("\n" + "="*80)
    print(f" RZMENU DIAGNOSTICS: {col_name}")
    print("="*80)
    
    if not col:
        print(f"!!! Error: Collection '{col_name}' not found.")
        return

    total_v = 0
    total_l = 0
    
    for obj in col.all_objects:
        if obj.type != 'MESH': continue
        
        mesh = obj.data
        v_cnt = len(mesh.vertices)
        l_cnt = len(mesh.loops)
        split_factor = l_cnt / v_cnt if v_cnt > 0 else 0
        
        total_v += v_cnt
        total_l += l_cnt
        
        mods = [m.name for m in obj.modifiers if m.show_viewport]
        keys = len(mesh.shape_keys.key_blocks) if mesh.shape_keys else 0
        
        print(f"\n> Object: {obj.name}")
        print(f"  - Vertices: {v_cnt:,}")
        print(f"  - Loops:    {l_cnt:,}")
        print(f"  - Split Factor: {split_factor:.2f}x (1 vertex -> {split_factor:.2f} buffer vertices)")
        
        if split_factor > 1.5:
            print(f"    [!] Mapping Risk: Typical mapping will LOSE {int((l_cnt-v_cnt)/l_cnt*100)}% of vertex updates!")
        
        if mods:
            print(f"  - Active Modifiers: {', '.join(mods)}")
            if any(m in [m.type for m in obj.modifiers] for m in ['MIRROR', 'SUBSURF', 'DECIMATE']):
                 print("    [!] TOPOLOGY RISK: Generative modifiers detected. Fast Path mapping may be unstable.")

    print("\n" + "="*80)
    print(f" SUMMARY FOR {col_name}")
    print(f" Total Blender Vertices: {total_v:,}")
    print(f" Total Potential Buffer Vertices: {total_l:,}")
    print(f" Complexity Score: {total_l / total_v if total_v > 0 else 0:.2f}")
    print("="*80)
    print("ANALYSIS: If Splitting Factor > 1.0, 1-to-1 Mapping causes SPIKES/TEARS at seams.")
    print("SOLUTION: Use Many-to-1 Mapping (Buffer-to-Blender) to keep seams closed.")
    print("="*80 + "\n")

if __name__ == "__main__":
    run_diagnostics()
