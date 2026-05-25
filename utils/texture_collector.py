# RZMenu/utils/texture_collector.py
import bpy
import os
import json
from pathlib import Path

def clean_res_name(name):
    if not name:
        return ""
    name = name.lower()
    # Strip Resource prefix
    if name.startswith("resource\\"):
        name = name[9:]
    elif name.startswith("resource/"):
        name = name[9:]
    elif name.startswith("resource"):
        name = name[8:]
    
    # Strip common texture extensions
    for ext in ['.dds', '.png', '.jpg', '.jpeg']:
        if name.endswith(ext):
            name = name[:-len(ext)]
            break
    return name

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
                
                path_str = str(raw_val)
                # We want the filename part if it's a path
                filename = os.path.basename(path_str)
                if filename:
                    used_textures.add(filename)

    # 2. Collect existing resources (cleaned of Resource prefix and extensions)
    existing_resources = {clean_res_name(res.name) for res in rzm.tw_resources}
    
    # 3. Identify missing textures
    missing_textures = []
    for tex_name in used_textures:
        # Compare cleaned versions
        if clean_res_name(tex_name) not in existing_resources:
            missing_textures.append(tex_name)
            print(f"[RZM Collector] Missing Texture detected: {tex_name}")

    # 4. Save to scene property for Jinja2
    if missing_textures:
        scene["rzm_missing_textures"] = ",".join(missing_textures)
    
    return len(missing_textures)

