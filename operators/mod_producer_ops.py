import bpy
import os
import shutil
import re
import zipfile
from pathlib import Path
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator
from .export_manager import get_target_path

def parse_ini_file(ini_path, active_tiers):
    if not os.path.exists(ini_path):
        return
        
    with open(ini_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    out_lines = []
    skip_mode = False # Can be False, True (delete all), or "MESH_KEEP" / "MESH_DELETE"
    
    # Pre-compile regex for [EDIT] lines and Mesh protected lines
    edit_regex = re.compile(r"^(.*?filename\s*=\s*)/[^/]+/(.*)$")
    mesh_protected = re.compile(r"^\s*(draw|drawindexed|drawinstanced|\$CD_|run\s*=\s*CustomShader|Resource/|ps-t\d)", re.IGNORECASE)
    mesh_volatile = re.compile(r"^\s*(if|elif|else|endif)", re.IGNORECASE)
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # --- MESH PROCESSING MODE ---
        if skip_mode in ["MESH_KEEP", "MESH_DELETE"]:
            if stripped.startswith(";[META-INFO]") and "[END]" in stripped:
                skip_mode = False
                # We don't add the END tag to the final file to keep it clean
                i += 1
                continue
            
            # Filter the line
            if mesh_volatile.match(line):
                # Erase conditionals (if, endif, etc.)
                pass
            elif mesh_protected.match(line):
                if skip_mode == "MESH_DELETE":
                    # Deactivate: Comment out instead of deleting
                    out_lines.append(f";{line}")
                else:
                    # Activate: Keep as is (unconditional)
                    out_lines.append(line)
            else:
                # Other lines (comments, unrelated) - erase in mesh mode
                pass
                
            i += 1
            continue

        # --- STANDARD SKIP MODE ---
        if skip_mode is True:
            if stripped.startswith(";[META-INFO]") and "[END]" in stripped and "[DELETE]" in stripped:
                skip_mode = False
            i += 1
            continue
            
        # --- TAG DETECTION ---
        if stripped.startswith(";[META-INFO]"):
            parts = re.findall(r"\[([\w\s-]+)\]", stripped)
            
            is_start = "START" in parts
            is_mark = "MARK" in parts
            is_end = "END" in parts
            
            action = ""
            if "DELETE" in parts: action = "DELETE"
            elif "EDIT" in parts: action = "EDIT"
            
            if len(parts) >= 5 and (is_start or is_mark):
                if "META-TAG-VAR" in parts:
                    # Special case for global tier indicator variables
                    tier_id = parts[4]
                    is_tier_active = tier_id in active_tiers
                    if not is_tier_active:
                        # Edit the next non-comment line to set the variable to 0
                        j = i + 1
                        while j < len(lines):
                            next_line = lines[j]
                            if next_line.strip() and not next_line.strip().startswith(";"):
                                lines[j] = re.sub(r"=\s*1", "= 0", next_line)
                                break
                            j += 1
                elif "MESH" in parts:
                    # [MESH] Logic: Safe Delete or Flattening
                    # Format: ;[META-INFO] [START] [DELETE] [MESH] [Name] [TierID1] [TierID2]
                    tier_tags = parts[5:] # [Name] is usually at parts[4], tiers start at parts[5]
                    # Actually parts[4] is the mesh name. Tiers are from parts[5].
                    has_active_tier = any(t in active_tiers for t in tier_tags) if tier_tags else True
                    
                    if action == "DELETE" and is_start:
                        if not has_active_tier:
                            skip_mode = "MESH_DELETE"
                        else:
                            skip_mode = "MESH_KEEP" # Flattening
                    # We skip the START tag itself
                    i += 1
                    continue
                else:
                    # Standard block deletion logic
                    tier_tags = parts[5:]
                    has_active_tier = all(t in active_tiers for t in tier_tags)
                    
                    if not has_active_tier:
                        if action == "DELETE" and is_start:
                            skip_mode = True
                        elif action == "EDIT" and is_mark:
                            j = i + 1
                            while j < len(lines):
                                next_line = lines[j]
                                if next_line.strip() and not next_line.strip().startswith(";"):
                                    m = edit_regex.match(next_line)
                                    if m:
                                        lines[j] = f"{m.group(1)}{m.group(2)}\n"
                                    break
                                j += 1
                            
            i += 1
            continue
            
        out_lines.append(line)
        i += 1
        
    with open(ini_path, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)

def process_directories(new_folder_path):
    """
    CLEANUP LOGIC: Blacklist-based approach to prevent data loss.
    Deletes only 'garbage' files like .bak, .py, .exe and the legacy ReadMe.txt.
    """
    blacklist_ext = {'.bak', '.py', '.exe'}
    blacklist_filenames = {'readme.txt'} # Case-insensitive check
    
    for root, dirs, files in os.walk(new_folder_path, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            ext = os.path.splitext(name)[1].lower()
            if ext in blacklist_ext or name.lower() in blacklist_filenames:
                try:
                    os.remove(file_path)
                except Exception as e:
                    print(f"[ModProducer] Failed to delete {file_path}: {e}")
        
        # Optional: Remove empty directories created by deleting files (if any)
        # However, we only delete specific files, so we don't prune folders unless requested.

class RZM_OT_ModProducerBuild(bpy.types.Operator):
    """Perform the cleanup/edit on a copy of the mod folder"""
    bl_idname = "rzm.mod_producer_build"
    bl_label = "Build Tier Version"
    bl_description = "Create a cleaned-up version of the mod based on active tiers"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from .tier_ops import get_prefs
        prefs = get_prefs(context)
        
        base_target = get_target_path(context)
        if not base_target:
            self.report({'ERROR'}, "Export path not set! Please check Export Manager.")
            return {'CANCELLED'}
        
        mp = context.scene.rzm_mod_producer
        suffix = mp.build_suffix.strip()
        
        meta = context.scene.rzm.meta_data
        char = getattr(meta, 'character_name', '').strip().replace(" ", "")
        outfit = getattr(meta, 'outfit_name', '').strip().replace(" ", "")
        
        project_part = f"{char}+{outfit}" if (char and outfit) else (char or outfit)
        if not project_part:
            project_part = os.path.basename(os.path.normpath(base_target))
            
        prefix = prefs.author_name.strip() if (prefs and prefs.author_name) else "UNKNOWN"
        
        # Sibling build: Use @ prefix as requested
        folder_name = f"@{prefix}_{project_part}" if prefix else f"@{project_part}"
        if suffix:
            folder_name += f"_{suffix}"
            
        target_path = os.path.join(os.path.dirname(base_target), folder_name)
        
        if os.path.abspath(target_path) == os.path.abspath(base_target):
            self.report({'ERROR'}, "Build path would overwrite original! Add a suffix.")
            return {'CANCELLED'}

        try:
            if os.path.exists(target_path):
                shutil.rmtree(target_path)
            
            # Clean copy: Ignore .py, .bak, and cache
            ignore_func = shutil.ignore_patterns('*.py', '*.bak', '__pycache__')
            shutil.copytree(base_target, target_path, ignore=ignore_func)
        except Exception as e:
            self.report({'ERROR'}, f"Copying failed: {e}")
            return {'CANCELLED'}

        active_tiers = [t.strip() for t in mp.active_tiers.split(",") if t.strip()]
        
        processed_count = 0
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.lower().endswith(".ini"):
                    ini_full = os.path.join(root, file)
                    parse_ini_file(ini_full, active_tiers)
                    processed_count += 1
        
        process_directories(target_path)

        self.report({'INFO'}, f"Build complete: '{folder_name}' ({processed_count} files processed)")
        return {'FINISHED'}

class RZM_OT_ModProducerBatchBuild(bpy.types.Operator):
    """Build all versions defined in Build Profiles"""
    bl_idname = "rzm.mod_producer_batch_build"
    bl_label = "Batch Build All Versions"
    bl_description = "Automatically build, clean and zip all versions defined in Build Profiles"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from .tier_ops import get_prefs
        prefs = get_prefs(context)
        if not prefs or not prefs.build_profiles:
            self.report({'ERROR'}, "No Build Profiles defined in Addon Preferences!")
            return {'CANCELLED'}
        
        target_path = get_target_path(context)
        print(f"Mod Producer: Build starting in: {target_path}")
        if not os.path.exists(target_path):
            self.report({'ERROR'}, f"Path not found: {target_path}")
            return {'CANCELLED'}
        
        inis = [f for f in os.listdir(target_path) if f.lower().endswith(".ini")]
        print(f"Mod Producer: Found {len(inis)} .ini files: {inis}")
        if not inis:
            self.report({'WARNING'}, f"No .ini files found in {target_path}")
            return {'CANCELLED'}

        batch_log = []
        base_dir = os.path.dirname(target_path)
        meta = context.scene.rzm.meta_data
        char = getattr(meta, 'character_name', '').strip()
        outfit = getattr(meta, 'outfit_name', '').strip()
        
        base_name = f"{char}{outfit}".replace(" ", "")
        if not base_name:
            base_name = os.path.basename(os.path.normpath(target_path))
            
        for profile in prefs.build_profiles:
            # Strip only OS-invalid characters, keep things like @ or spaces
            clean_profile_id = re.sub(r'[\\/:*?"<>|]', '', profile.name).strip()
            prefix = prefs.author_name.strip() if (prefs and prefs.author_name) else "UNKNOWN"
            
            # Combine formatting: Prefix_CharacterOutfit_ProfileName
            parts = []
            if prefix: parts.append(prefix)
            if base_name: parts.append(base_name)
            if clean_profile_id: parts.append(clean_profile_id)
            
            folder_name = "_".join(parts)
            # Add @ prefix for standard release naming
            if not folder_name.startswith("@"):
                folder_name = f"@{folder_name}"
            
            # Check global batch path from Preferences
            prod_root = prefs.batch_build_path.strip() if prefs.batch_build_path else ""
            if prod_root and os.path.exists(bpy.path.abspath(prod_root)):
                version_path = os.path.join(bpy.path.abspath(prod_root), folder_name)
            else:
                version_path = os.path.join(base_dir, folder_name)
            
            if os.path.abspath(version_path) == os.path.abspath(target_path):
                continue

            try:
                if os.path.exists(version_path):
                    shutil.rmtree(version_path)
                
                # Clean copy: Ignore .py, .bak, and cache
                ignore_func = shutil.ignore_patterns('*.py', '*.bak', '__pycache__')
                shutil.copytree(target_path, version_path, ignore=ignore_func)
                
                # --- APPLY TIER FILTERING ---
                active_tiers = {t.strip() for t in profile.active_tiers.split(",") if t.strip()}
                for root, _, files in os.walk(version_path):
                    for file in files:
                        if file.lower().endswith(".ini"):
                            ini_full = os.path.join(root, file)
                            parse_ini_file(ini_full, active_tiers)
                
                # --- PROCESS FOLDERS ---
                process_directories(version_path)
                
                # --- PACKAGING ---
                if profile.zip_output:
                    zip_name = f"{version_path}.zip"
                    with zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED) as z:
                        for root, _, files in os.walk(version_path):
                            for file in files:
                                f_path = os.path.join(root, file)
                                arcname = os.path.join(folder_name, os.path.relpath(f_path, version_path))
                                z.write(f_path, arcname)
                    shutil.rmtree(version_path)
                    batch_log.append(f"Zipped {folder_name}.zip")
                else:
                    batch_log.append(f"Created {folder_name}")
                    
            except Exception as e:
                msg = f"Failed profile '{profile.name}': {e}"
                print(f"Mod Producer: {msg}")
                self.report({'ERROR'}, msg)
                batch_log.append(f"Failed {profile.name}")
                continue

        if not batch_log:
            self.report({'WARNING'}, "Batch finished but no outputs were generated.")
        else:
            self.report({'INFO'}, f"Batch complete: {', '.join(batch_log)}")
        return {'FINISHED'}

class RZM_OT_ToggleBuildTier(Operator):
    bl_idname = "rzm.toggle_build_tier"
    bl_label = "Toggle Build Tier"
    bl_options = {'INTERNAL'}
    tier_id: StringProperty()
    def execute(self, context):
        mp = context.scene.rzm_mod_producer
        active = [t.strip() for t in mp.active_tiers.split(",") if t.strip()]
        if self.tier_id in active: active.remove(self.tier_id)
        else: active.append(self.tier_id)
        mp.active_tiers = ",".join(active)
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_ModProducerBuild,
    RZM_OT_ModProducerBatchBuild,
    RZM_OT_ToggleBuildTier
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
