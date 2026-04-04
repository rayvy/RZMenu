import bpy
import os
from pathlib import Path

def debug_efmi_batch_export(frame_start, frame_end):
    print("\n" + "="*50)
    print("EFMI BATCH EXPORT DEBUG START")
    print("="*50)
    
    scene = bpy.context.scene
    if not hasattr(scene, "efmi_tools_settings"):
        print("ERROR: EFMI-Tools settings not found!")
        return
    
    efmi = scene.efmi_tools_settings
    
    # 1. Save original settings
    original_settings = {
        "mod_output_folder": efmi.mod_output_folder,
        "copy_textures": efmi.copy_textures,
        "write_ini": efmi.write_ini,
        "apply_all_modifiers": efmi.apply_all_modifiers,
    }
    
    base_output_dir = Path(bpy.path.abspath(efmi.mod_output_folder))
    print(f"Base Output Directory: {base_output_dir}")
    
    if not base_output_dir or efmi.mod_output_folder == "":
        print("ERROR: Mod Output Folder is not set in EFMI settings!")
        return

    # 2. Apply batch settings
    print("Applying batch export overrides...")
    efmi.copy_textures = False
    efmi.write_ini = False
    efmi.apply_all_modifiers = True
    
    # 3. Batch Loop
    try:
        for frame in range(frame_start, frame_end + 1):
            print(f"\n>>> PROCESSING FRAME: {frame}")
            
            # Change frame
            scene.frame_set(frame)
            
            # Create subfolder path
            frame_folder = base_output_dir / str(frame)
            if not frame_folder.exists():
                frame_folder.mkdir(parents=True, exist_ok=True)
            
            # Update EFMI output folder (must be string for Blender property)
            efmi.mod_output_folder = str(frame_folder) + os.sep
            
            print(f"Targeting folder: {efmi.mod_output_folder}")
            
            # Call EFMI Export
            # Note: We use 'INVOKE_DEFAULT' or just call it directly. 
            # Since it's a script, internal logic should handle it.
            try:
                bpy.ops.efmi_tools.export_mod()
                print(f"SUCCESS: Frame {frame} exported.")
            except Exception as e:
                print(f"FAILED: Frame {frame} export error: {e}")
                
    finally:
        # 4. Restore settings
        print("\n" + "-"*30)
        print("Restoring original EFMI settings...")
        for key, value in original_settings.items():
            setattr(efmi, key, value)
        print("Done.")

    print("\n" + "="*50)
    print("EFMI BATCH EXPORT DEBUG FINISHED")
    print("="*50)

# --- RUN TEST ---
# Change these values to test a specific range
start_f = bpy.context.scene.frame_start
end_f = min(start_f + 2, bpy.context.scene.frame_end) # Test only 3 frames

debug_efmi_batch_export(start_f, end_f)
