import bpy
import os
import shutil
import re
from pathlib import Path
from bpy.props import StringProperty
from bpy.types import Operator
from .export_manager import get_target_path

def parse_ini_file(ini_path, active_tiers):
    with open(ini_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    out_lines = []
    skip_mode = False
    skip_end_tag = ""
    
    # Pre-compile regex for [EDIT] lines
    # Matches: filename = /SomeVar/RemainingPath.buf -> filename = RemainingPath.buf
    edit_regex = re.compile(r"^(.*?filename\s*=\s*)/[^/]+/(.*)$")
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # Are we currently skipping a block?
        if skip_mode:
            if stripped.startswith(";[META-INFO]") and "[END]" in stripped and "[DELETE]" in stripped:
                # We reached the end of the block we are deleting
                skip_mode = False
            # We skip this line whether it's the end tag or inner content
            i += 1
            continue
            
        # Is this a META-INFO tag?
        if stripped.startswith(";[META-INFO]"):
            # Extract tags [Tier1] [Tier2] etc.
            # Find all parts in brackets
            parts = re.findall(r"\[([\w\s-]+)\]", stripped)
            
            is_start = "START" in parts
            is_mark = "MARK" in parts
            is_end = "END" in parts
            
            action = ""
            if "DELETE" in parts: action = "DELETE"
            elif "EDIT" in parts: action = "EDIT"
            
            # Extract tiers. They are the parts after the entity Type and Name.
            # Example: [START] [DELETE] [SHAPE] [MyShape] [Premium] [NSFW]
            # Let's extract all tiers by checking which parts are defined in active_tiers.
            # Wait, the string 'parts' contains all brackets.
            # To be safe, we just check if ANY active tier is present in 'parts'.
            # If active_tiers is empty, it means base build, so we compare.
            
            # Get the exact tier tags (we know they are at the end, but easier to use sets)
            # Find the index of the Entity Name (SHAPE/ELEMENT/MESH)
            # parts usually are: META-INFO, START, DELETE, SHAPE, ShapeName, Tier1, Tier2
            # The tiers start from index 5.
            if len(parts) >= 5 and (is_start or is_mark):
                tier_tags = parts[5:]
                
                # Check if at least one tier tag matches our active tiers for this build
                has_active_tier = any(t in active_tiers for t in tier_tags)
                
                if not has_active_tier:
                    if action == "DELETE" and is_start:
                        # Skip until we find the END tag for this block
                        skip_mode = True
                    elif action == "EDIT" and is_mark:
                        # We need to edit the NEXT line (or previous?)
                        # The user template puts filename = ... right after the MARK or before?
                        # Let's assume the MARK is right before the line we need to edit
                        # or right after?
                        # Wait, in the updated core.j2 I put MARK right BEFORE the filename.
                        # So we edit the NEXT line.
                        
                        # Let's edit the next non-empty, non-comment line
                        j = i + 1
                        while j < len(lines):
                            next_line = lines[j]
                            if next_line.strip() and not next_line.strip().startswith(";"):
                                m = edit_regex.match(next_line)
                                if m:
                                    lines[j] = f"{m.group(1)}{m.group(2)}\n"
                                break
                            j += 1
                            
            # We don't add the META-INFO lines themselves to out_lines
            i += 1
            continue
            
        out_lines.append(line)
        i += 1
        
    with open(ini_path, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)

def process_directories(new_folder_path, active_tiers):
    # Process the directories (like 0, 1, 2 = shape keys) and delete them 
    # if they lack metadata tags that map to our active tiers.
    # The logic here: user said 
    # "мы смотрим какие у него мета тэги есть... Если отсутствует какой либо мета-тэг ... мы удаляем."
    # Since META-INFO dictates tiers for shape keys, we should parse core.j2 or ini
    # to understand which folder belongs to which shape?
    # Actually, if we deleted the logic blocks from the INI, we don't strictly *need* 
    # to delete the folders to make it work, but deleting the folders saves disk space!
    
    # Wait, how do we know which '/FolderName/' corresponds to which deleted shape?
    # The INI file had:
    # filename = /ShapeKeyName/Meshes/...
    # If the shape is deleted, that folder 'ShapeKeyName' can be deleted?
    # But different components might share the same folder if they belong to the same shape key.
    # If we parsed all lines that were DELETED or EDITED, and collected the folder names
    # that were part of those lines, we could delete those folders?
    # If the INI doesn't reference a directory anymore, maybe we can safely delete it?
    # No, an easier way is to just look for referenced folders in the FINAL ini,
    # and delete any folders in the mod directory that are NOT referenced in the final INI!
    
    allowed_dirs = {"Meshes", "tex", "textures", "Texture", "Resource"}
    
    # Find all referenced subdirectories in the final parsed INI
    ini_path = os.path.join(new_folder_path, 'merged.ini')
    if not os.path.exists(ini_path):
        return
        
    with open(ini_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # Extract all top-level directory names referenced in paths in ini
    # e.g., filename = /FolderName/Meshes/...
    # Match: filename\s*=\s*/([^/]+)/
    referenced_folders = set()
    for match in re.finditer(r"filename\s*=\s*/([^/\s]+)/", content):
        referenced_folders.add(match.group(1).lower())
        
    # Also grab without leading slash
    for match in re.finditer(r"filename\s*=\s*([^/\s]+)/", content):
        referenced_folders.add(match.group(1).lower())
        
    # Standard allowed folders
    referenced_folders.update(d.lower() for d in allowed_dirs)
    referenced_folders.add("0") # Usually base is /0/ or just Meshes/
    
    # Now iterate the actual directories in the output folder
    for item in os.listdir(new_folder_path):
        item_path = os.path.join(new_folder_path, item)
        if os.path.isdir(item_path):
            # If this directory is not referenced in the INI, delete it!
            if item.lower() not in referenced_folders:
                print(f"[Mod Producer] Deleting unreferenced shape directory: {item}")
                shutil.rmtree(item_path, ignore_errors=True)

class RZM_OT_ModProducerBuild(Operator):
    bl_idname = "rzm.mod_producer_build"
    bl_label = "Build Mod Tiers"
    bl_description = "Generate a specific Tier Build from the selected base folder"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        mp = context.scene.rzm_mod_producer
        base_folder = get_target_path(context)
        
        if not base_folder or not os.path.exists(base_folder):
            self.report({'ERROR'}, "Central Mod Path is invalid or does not exist. Please export once or set path.")
            return {'CANCELLED'}
            
        base_dir = Path(base_folder)
        original_name = base_dir.name
        
        # Clean up original name overrides
        clean_name = re.sub(r"(?i)^(ARCHIVED|DISABLED)", "", original_name).strip()
        clean_name = clean_name.strip(" _-")
        
        # Construct new name
        prefix = mp.author_prefix.strip()
        if prefix and not prefix.startswith("@"):
            prefix = "@" + prefix
            
        suffix = mp.build_suffix.strip()
        
        new_folder_name = clean_name
        if prefix: new_folder_name = f"{prefix}_{new_folder_name}"
        if suffix: new_folder_name = f"{new_folder_name}_{suffix}"
        
        new_folder_path = base_dir.parent / new_folder_name
        
        # Copy directory
        if new_folder_path.exists():
            self.report({'INFO'}, f"Overwriting existing build folder: {new_folder_name}")
            shutil.rmtree(new_folder_path)
            
        self.report({'INFO'}, f"Copying mod to {new_folder_name}...")
        shutil.copytree(base_dir, new_folder_path)
        
        active_tiers = [t.strip() for t in mp.active_tiers.split(",") if t.strip()]
        
        # Parse all INI files in the new directory
        for f in new_folder_path.glob("*.ini"):
            parse_ini_file(str(f), active_tiers)
            
        # Optional: Delete unused shape key folders
        process_directories(str(new_folder_path), active_tiers)
        
        self.report({'INFO'}, f"Successfully built {new_folder_name} with tiers: {active_tiers}")
        return {'FINISHED'}

class RZM_OT_ToggleBuildTier(Operator):
    bl_idname = "rzm.toggle_build_tier"
    bl_label = "Toggle Build Tier"
    bl_options = {'INTERNAL'}

    tier_id: StringProperty()

    def execute(self, context):
        mp = context.scene.rzm_mod_producer
        active = [t.strip() for t in mp.active_tiers.split(",") if t.strip()]
        
        if self.tier_id in active:
            active.remove(self.tier_id)
        else:
            active.append(self.tier_id)
            
        mp.active_tiers = ",".join(active)
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_ModProducerBuild,
    RZM_OT_ToggleBuildTier
]
