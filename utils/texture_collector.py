# RZMenu/utils/texture_collector.py
import bpy
import os
import json
from pathlib import Path

def collect_missing_textures(context):
    """
    Analyzes textures used in meshes and compares them with TexWorks resources 
    and existing mod files. Marks missing textures for auto-generation in the template.
    """
    scene = context.scene
    rzm = scene.rzm
    
    # Reset missing textures log
    scene["rzm_missing_textures"] = ""
    
    # 1. Collect textures used in meshes
    used_textures = set() # Store (filename)
    for obj in scene.objects:
        if obj.type != 'MESH': continue
        for key in obj.keys():
            if key.startswith("rzm.TexSlot."):
                raw_val = obj[key]
                if not raw_val: continue
                
                # Extract filename without Resource/ prefix
                # The user says: "rzm_missing_textures должно попадать чисто название"
                # "Если юзер там напишет в названии 'Diffuse.dds', ну что же... [ResourceDiffuse.dds]"
                
                path_str = str(raw_val)
                # Remove Resource prefix if exists
                if path_str.lower().startswith("resource\\"):
                    path_str = path_str[9:]
                elif path_str.lower().startswith("resource/"):
                    path_str = path_str[9:]
                elif path_str.lower().startswith("resource"):
                    path_str = path_str[8:]
                
                # We want the filename part if it's a path
                filename = os.path.basename(path_str)
                if filename:
                    used_textures.add(filename)

    # 2. Collect existing resources
    existing_resources = {res.name.lower() for res in rzm.tw_resources}
    
    # 3. Identify missing textures
    missing_textures = []
    for tex_name in used_textures:
        # Check if it's already in resources (case-insensitive check)
        if tex_name.lower() not in existing_resources:
            missing_textures.append(tex_name)
            print(f"[RZM Collector] Missing Texture detected: {tex_name}")

    # 4. Save to scene property for Jinja2
    if missing_textures:
        scene["rzm_missing_textures"] = ",".join(missing_textures)
    
    return len(missing_textures)
