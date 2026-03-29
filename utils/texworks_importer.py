# RZMenu/utils/texworks_importer.py
import bpy
import os
import re
import json

def import_from_folder(context, directory):
    """
    Core logic for importing textures from a dump folder.
    Supports both pattern-based (EFMI/WWMI) and JSON-based (XXMI) algorithms.
    """
    rzm = context.scene.rzm
    game_mode = rzm.game.selection
    
    print("\n" + "="*50)
    print(f"[RZM Importer] Starting Auto-Import")
    print(f"[RZM Importer] Path: {directory}")
    print(f"[RZM Importer] Detected Game: {game_mode}")
    print("="*50)

    if not os.path.exists(directory):
        print(f"[RZM Importer] ERROR: Directory does not exist: {directory}")
        return 0, f"Directory {directory} does not exist."

    # Games that use pattern-based scan
    PATERN_GAMES = {'ArknightsEndfield', 'WutheringWaves'}
    # Games that use hash.json scan
    JSON_GAMES = {'GenshinImpact', 'ZenlessZoneZero', 'HonkaiStarRail'}

    if game_mode in PATERN_GAMES:
        print(f"[RZM Importer] Action: Using pattern-based scanner (EFMI/WWMI)...")
        return _import_pattern_based(context, directory)
    elif game_mode in JSON_GAMES:
        print(f"[RZM Importer] Action: Using hash.json parser (XXMI)...")
        return _import_json_based(context, directory)
    else:
        print(f"[RZM Importer] ERROR: No importer implemented for {game_mode}")
        return 0, f"Auto-import not implemented for game mode: {game_mode}"

def _import_pattern_based(context, directory):
    # Import inside function to avoid circular import during registration
    from ..operators.export_manager import get_target_path
    
    rzm = context.scene.rzm
    files = os.listdir(directory)
    print(f"[RZM Importer] Files found in directory: {len(files)}")
    
    # Pattern: Components-(\d+) t=([0-9a-fA-F]+)\.(dds|png|jpg)
    pattern = re.compile(r"Components-([\d-]+)\s+t=([0-9a-fA-F]+)\.(dds|png|jpg|jpeg)", re.IGNORECASE)
    
    imported_count = 0
    existing_hashes = {o.hash.lower() for o in rzm.tw_overrides}
    existing_names = {o.name.lower() for o in rzm.tw_overrides}
    
    folder_name = os.path.basename(directory.rstrip(os.sep))
    mod_base = get_target_path(context)
    print(f"[RZM Importer] Mod root base: {mod_base}")
    
    for f in files:
        match = pattern.match(f)
        if not match:
            continue
            
        comp_idx_str, tex_hash, ext = match.groups()
        print(f"[RZM Importer] Found matching file: {f}")
        print(f"    -> Component: {comp_idx_str}, Hash: {tex_hash}, Ext: {ext}")
        
        comp_idx_str = comp_idx_str.replace('-', '.')
        
        if tex_hash.lower() in existing_hashes:
            # print(f"    -> SKIPPED: Hash {tex_hash} already in overrides.")
            continue
        
        name_base = f"TWComponent{comp_idx_str}"
        final_name = name_base
        counter = 1
        while final_name.lower() in existing_names:
            final_name = f"{name_base}.{counter}"
            counter += 1
            
        res_name = f"{final_name}_RES"
        
        abs_f_path = os.path.join(directory, f)
        store_path = _get_relative_path(abs_f_path, mod_base)

        print(f"    -> Adding Resource: {res_name} (Path: {store_path})")
        # 1. Create Resource (Relative Path)
        res = rzm.tw_resources.add()
        res.name = res_name
        res.type = 'ON_DISK'
        res.path = store_path
        res.qt_tag = folder_name
        
        print(f"    -> Adding Override: {final_name} (Hash: {tex_hash.lower()})")
        # 2. Create Override
        over = rzm.tw_overrides.add()
        over.name = final_name
        over.hash = tex_hash.lower()
        over.resource_name = res_name
        over.qt_tag = folder_name
        
        existing_hashes.add(tex_hash.lower())
        existing_names.add(final_name.lower())
        imported_count += 1
        
    print(f"[RZM Importer] Import finished. Total added: {imported_count}")
    return imported_count, f"Added {imported_count} pattern-based items."

def _import_json_based(context, directory):
    json_path = os.path.join(directory, "hash.json")
    print(f"[RZM Importer] Checking for hash.json at: {json_path}")
    
    if not os.path.exists(json_path):
        print(f"[RZM Importer] ERROR: hash.json not found in {directory}!")
        return 0, f"hash.json not found in {directory}."

    rzm = context.scene.rzm
    with open(json_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            print(f"[RZM Importer] Successfully parsed hash.json. Items in root: {len(data)}")
        except json.JSONDecodeError:
            print(f"[RZM Importer] ERROR: Failed to parse hash.json (Invalid JSON).")
            return 0, "Failed to parse hash.json."

    imported_count = 0
    existing_hashes = {o.hash.lower() for o in rzm.tw_overrides}
    existing_names = {o.name.lower() for o in rzm.tw_overrides}
    
    folder_name = os.path.basename(directory.rstrip(os.sep))
    
    for comp in data:
        comp_name = comp.get("component_name", "Unknown")
        tex_hashes_lods = comp.get("texture_hashes", [])
        print(f"[RZM Importer] Parsing component: {comp_name} ({len(tex_hashes_lods)} LOD categories)")
        
        for lod_idx, tex_list in enumerate(tex_hashes_lods):
            print(f"    [LOD {lod_idx}] Textures entries: {len(tex_list)}")
            for tex_data in tex_list:
                if len(tex_data) < 3:
                    continue
                
                tex_type = tex_data[0] # "Diffuse", "NormalMap", etc.
                ext = tex_data[1]      # ".dds"
                tex_hash = tex_data[2].lower()
                
                if tex_hash in existing_hashes:
                    # print(f"        -> SKIPPED: Hash {tex_hash} already present.")
                    continue
                
                name_base = f"TW_{comp_name}_{tex_type}"
                final_name = name_base
                counter = 1
                while final_name.lower() in existing_names:
                    final_name = f"{name_base}.{counter}"
                    counter += 1
                    
                res_name = f"{final_name}_RES"
                store_path = f"{tex_hash}{ext}"
                
                print(f"        -> Adding Resource: {res_name} (Hash as path: {store_path})")
                # 1. Create Resource
                res = rzm.tw_resources.add()
                res.name = res_name
                res.type = 'ON_DISK'
                res.path = store_path
                res.qt_tag = folder_name
                
                print(f"        -> Adding Override: {final_name} (Hash: {tex_hash})")
                # 2. Create Override
                over = rzm.tw_overrides.add()
                over.name = final_name
                over.hash = tex_hash
                over.resource_name = res_name
                over.qt_tag = folder_name
                
                existing_hashes.add(tex_hash)
                existing_names.add(final_name.lower())
                imported_count += 1
                
    print(f"[RZM Importer] Import finished. Total added: {imported_count}")
    return imported_count, f"Added {imported_count} items from hash.json."

def _get_relative_path(abs_path, mod_base):
    # Fallback to absolute if no mod_base or path doesn't start with it
    if not mod_base or not abs_path.startswith(mod_base):
        return abs_path
    
    rel_path = os.path.relpath(abs_path, mod_base)
    # Common convention: if in Textures subfolder, strip it for shorter paths
    if rel_path.startswith(f"Textures{os.sep}"):
        rel_path = os.path.relpath(abs_path, os.path.join(mod_base, "Textures"))
    return rel_path.replace(os.sep, '/')
