# RZMenu/utils/texture_collector.py
import bpy
import os
import json
from pathlib import Path
from ..operators.export_manager import get_target_path

def collect_missing_textures(context):
    """
    Analyzes textures used in meshes and compares them with TexWorks resources 
    and existing mod files. Marks missing textures for auto-generation in the template.
    """
    scene = context.scene
    rzm = scene.rzm
    
    # 1. Collect textures used in meshes (Block 1)
    used_textures = set() # Store (slot_name, texture_path)
    for obj in scene.objects:
        if obj.type != 'MESH': continue
        for key in obj.keys():
            if key.startswith("rzm.TexSlot."):
                raw_val = obj[key]
                if not raw_val: continue
                
                # Clean prefix "Resource" or "Resource\"
                safe_val = str(raw_val)
                if safe_val.startswith('Resource\\'):
                    safe_val = safe_val[9:]
                elif safe_val.startswith('Resource'):
                    safe_val = safe_val[8:]
                
                # If no extension, default to .dds
                if not Path(safe_val).suffix:
                    safe_val += ".dds"
                
                used_textures.add(safe_val)

    # 2. Collect existing resources (Block 2)
    # 2a. TexWorks Resources
    existing_resources = {res.name for res in rzm.tw_resources}
    
    # 2b. Existing mod files (if export_texture_slots is enabled)
    mod_textures = set()
    if rzm.export_texture_slots:
        target_path = get_target_path(context)
        if target_path:
            tex_folder = Path(target_path) / "Textures"
            if tex_folder.exists():
                for f in tex_folder.glob("**/*"):
                    if f.is_file():
                        # We match by filename (ignoring Case as 3dmigoto does)
                        mod_textures.add(f.name.lower())

    # 3. Identify missing textures
    missing_textures = []
    for tex_path in used_textures:
        tex_name = Path(tex_path).name
        # Check if it's in resources or physical files
        if tex_name not in existing_resources and tex_name.lower() not in mod_textures:
            missing_textures.append(tex_name)
            print(f"[RZM Collector] Missing Texture detected: {tex_name}")

    # 4. Save to scene property for Jinja2
    # We store as a JSON string to handle it as a list in the template (if possible) 
    # or just a comma-separated string.
    scene["rzm_missing_textures"] = ",".join(missing_textures)
    
    return len(missing_textures)
