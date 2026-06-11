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
        
    print(f"[Mod Producer] Filtering tiers in INI: {os.path.basename(ini_path)}")
    with open(ini_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    out_lines = []
    skip_mode = False # Can be False, True (delete all), or "MESH_KEEP" / "MESH_DELETE"
    deleted_sections = set()
    
    # Pre-compile regex for [EDIT] lines and Mesh protected lines
    edit_regex = re.compile(r"^(.*?filename\s*=\s*)/[^/]+/(.*)$")
    mesh_protected = re.compile(r"^\s*(draw|drawindexed|drawinstanced|\$CD_|run\s*=\s*CustomShader|Resource/|ps-t\d)", re.IGNORECASE)
    mesh_volatile = re.compile(r"^\s*(if|elif|else|endif)", re.IGNORECASE)
    global_var_re = re.compile(r"^\s*(global\s+(?:persist\s+)?\$[a-zA-Z0-9_.]+)\s*=\s*(.*)$", re.IGNORECASE)
    
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
            else:
                # Track deleted sections
                if stripped.startswith("[") and stripped.endswith("]"):
                    sec_name = stripped[1:-1].strip()
                    deleted_sections.add(sec_name)
                    
                m_var = global_var_re.match(line)
                if m_var:
                    out_lines.append(f"{m_var.group(1)} = 0\n")
                    i += 1
                    continue
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
        
    # --- POST-PARSE: COMMENT OUT DELETED SECTION REFERENCES ---
    if deleted_sections:
        print(f"[Mod Producer] Commenting out references to deleted sections: {deleted_sections}")
        deleted_regex = re.compile(r'\b(' + '|'.join(re.escape(s) for s in deleted_sections) + r')\b')
        final_lines = []
        for line in out_lines:
            stripped = line.strip()
            if not stripped or stripped.startswith(";") or stripped.startswith("["):
                final_lines.append(line)
            elif deleted_regex.search(line):
                final_lines.append(f";{line}")
            else:
                final_lines.append(line)
        out_lines = final_lines
        
    with open(ini_path, 'w', encoding='utf-8') as f:
        f.writelines(out_lines)

def delete_disabled_inis(target_path):
    print(f"[Mod Producer] Cleaning up disabled .ini files in copy...")
    deleted_count = 0
    for root, _, files in os.walk(target_path):
        for file in files:
            if file.lower().endswith(".ini") and file.lower().startswith("disabled"):
                ini_full = os.path.join(root, file)
                try:
                    os.remove(ini_full)
                    print(f"[Mod Producer] Deleted disabled INI: {os.path.relpath(ini_full, target_path)}")
                    deleted_count += 1
                except Exception as e:
                    print(f"[Mod Producer] Failed to delete disabled INI {ini_full}: {e}")
    print(f"[Mod Producer] Deleted {deleted_count} disabled INI files.")

import fnmatch

def extract_path_from_line(line, ini_path, target_path):
    stripped = line.strip()
    if not stripped or stripped.startswith(';'):
        return None
        
    parts = stripped.split('=', 1)
    if len(parts) != 2:
        return None
        
    key = parts[0].strip().lower()
    value = parts[1].strip().strip('"\'')
    
    # Strip "ref " prefix if present
    if value.lower().startswith('ref '):
        value = value[4:].strip().strip('"\'')
        
    # Check if the value looks like a file path
    is_path = False
    if '/' in value or '\\' in value:
        is_path = True
    else:
        ext = os.path.splitext(value)[1].lower()
        if ext in {'.hlsl', '.dds', '.buf', '.txt', '.png', '.jpg', '.jpeg', '.tga', '.bmp', '.ini', '.ib', '.vb'}:
            is_path = True
            
    if not is_path:
        return None
        
    # Resolve the path
    if value.startswith('/') or value.startswith('\\'):
        # Relative to target_path (mod root)
        clean_path = value.lstrip('/\\')
        full_path = os.path.abspath(os.path.join(target_path, clean_path))
    else:
        # Relative to the directory of the ini file
        clean_path = value
        ini_dir = os.path.dirname(ini_path)
        full_path = os.path.abspath(os.path.join(ini_dir, clean_path))
        
    # Return path relative to target_path, with forward slashes and lowercased for case-insensitive matching
    rel_path = os.path.relpath(full_path, target_path)
    return rel_path.replace('\\', '/').lower()

def destructive_cleanup(target_path):
    print(f"[Mod Producer] Starting destructive cleanup in: {target_path}")
    
    # 1. Build ignore patterns
    ignore_patterns = {
        '*.ini',
        '.deleteignore',
        'deleteignore.txt',
        'deleteignore',
        'readme.txt',
        'readme.md'
    }
    
    # Check for deleteignore files
    ignore_filenames = ['.deleteignore', 'deleteignore.txt', 'deleteignore']
    for fname in ignore_filenames:
        p = os.path.join(target_path, fname)
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            ignore_patterns.add(line)
                print(f"[Mod Producer] Loaded patterns from {fname}: {ignore_patterns}")
            except Exception as e:
                print(f"[Mod Producer] Failed to read ignore file {fname}: {e}")
                
    # 2. Extract referenced files from all active INI files
    used_files = set()
    for root, _, files in os.walk(target_path):
        for file in files:
            if file.lower().endswith(".ini"):
                ini_path = os.path.join(root, file)
                if file.lower().startswith("disabled"):
                    continue
                try:
                    with open(ini_path, 'r', encoding='utf-8', errors='ignore') as f:
                        for line in f:
                            rel_path_norm = extract_path_from_line(line, ini_path, target_path)
                            if rel_path_norm:
                                used_files.add(rel_path_norm)
                except Exception as e:
                    print(f"[Mod Producer] Failed to parse references in {file}: {e}")
                    
    print(f"[Mod Producer] Found {len(used_files)} active file references in INI files.")
    
    # Helper for matching ignore patterns
    def matches_pattern(rel_path, pattern):
        rel_path_norm = rel_path.replace('\\', '/').lower()
        pattern_norm = pattern.replace('\\', '/').strip().lower()
        
        if pattern_norm.endswith('/'):
            dir_pattern = pattern_norm.rstrip('/')
            return rel_path_norm == dir_pattern or rel_path_norm.startswith(dir_pattern + '/')
            
        if '*' in pattern_norm or '?' in pattern_norm:
            return fnmatch.fnmatch(rel_path_norm, pattern_norm) or fnmatch.fnmatch(os.path.basename(rel_path_norm), pattern_norm)
        else:
            return rel_path_norm == pattern_norm or os.path.basename(rel_path_norm) == pattern_norm

    # 3. Scan and delete unreferenced/unignored files
    deleted_files_count = 0
    for root, _, files in os.walk(target_path):
        for file in files:
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, target_path)
            rel_path_norm = rel_path.replace('\\', '/').lower()
            
            # Check if used
            if rel_path_norm in used_files:
                continue
                
            # Check if matches any deleteignore pattern
            keep = False
            for pat in ignore_patterns:
                if matches_pattern(rel_path_norm, pat):
                    keep = True
                    break
                    
            if not keep:
                try:
                    os.remove(file_path)
                    print(f"[Mod Producer] Deleted unused file: {rel_path_norm}")
                    deleted_files_count += 1
                except Exception as e:
                    print(f"[Mod Producer] Failed to delete unused file {file_path}: {e}")
                    
    print(f"[Mod Producer] Cleanup completed: deleted {deleted_files_count} unused files.")
    
    # 4. Remove empty subdirectories
    for root, dirs, _ in os.walk(target_path, topdown=False):
        for d in dirs:
            dir_path = os.path.join(root, d)
            if not os.listdir(dir_path):
                try:
                    os.rmdir(dir_path)
                    print(f"[Mod Producer] Removed empty directory: {os.path.relpath(dir_path, target_path)}")
                except Exception as e:
                    print(f"[Mod Producer] Failed to remove empty directory {dir_path}: {e}")

def process_directories(new_folder_path):
    """Legacy wrapper, delegates to destructive_cleanup"""
    destructive_cleanup(new_folder_path)

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
        
        project_part = f"{char}_{outfit}" if (char and outfit) else (char or outfit)
        if not project_part:
            project_part = os.path.basename(os.path.normpath(base_target))
            
        prefix = prefs.author_name.strip() if (prefs and prefs.author_name) else "UNKNOWN"
        
        # Sibling build: Use @ prefix as requested
        folder_name = f"@{prefix}_{project_part}" if prefix else f"@{project_part}"
        if suffix:
            folder_name += f"_{suffix}"
            
        # Use Path.parent to avoid "inside" issues with trailing slashes
        base_dir = Path(base_target).parent
        target_path = str(base_dir / folder_name)
        
        if os.path.abspath(target_path) == os.path.abspath(base_target):
            self.report({'ERROR'}, "Build path would overwrite original! Add a suffix.")
            return {'CANCELLED'}

        print(f"\n[Mod Producer] ================= START BUILD: {folder_name} =================")
        try:
            if os.path.exists(target_path):
                print(f"[Mod Producer] Removing existing build folder: {target_path}")
                shutil.rmtree(target_path)
            
            # Clean copy: Ignore .py, .bak, and cache
            print(f"[Mod Producer] Copying from '{base_target}' to '{target_path}'...")
            ignore_func = shutil.ignore_patterns('*.py', '*.bak', '__pycache__')
            shutil.copytree(base_target, target_path, ignore=ignore_func)
        except Exception as e:
            self.report({'ERROR'}, f"Copying failed: {e}")
            return {'CANCELLED'}

        # 1. Delete disabled INI files in the copy
        delete_disabled_inis(target_path)

        # 2. Filter tiers in active INI files
        active_tiers = [t.strip() for t in mp.active_tiers.split(",") if t.strip()]
        processed_count = 0
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.lower().endswith(".ini"):
                    ini_full = os.path.join(root, file)
                    parse_ini_file(ini_full, active_tiers)
                    processed_count += 1

        # 3. Perform destructive cleanup
        destructive_cleanup(target_path)

        # 4. Perform Inquisitor Cleanup & Real Compression on remaining INI files
        from .cleanup_ops import inquisitor_cleanup_logic, real_compression_logic
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.lower().endswith(".ini"):
                    ini_full = os.path.join(root, file)
                    print(f"[Mod Producer] Running post-build optimizations on: {file}")
                    inquisitor_cleanup_logic(ini_full, operator=None, create_backup=False)
                    real_compression_logic(ini_full, operator=None, create_backup=False)

        print(f"[Mod Producer] ================= BUILD FINISHED: {folder_name} =================\n")
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
        print(f"\n[Mod Producer] ================= START BATCH BUILD: {target_path} =================")
        if not os.path.exists(target_path):
            self.report({'ERROR'}, f"Path not found: {target_path}")
            return {'CANCELLED'}
        
        inis = [f for f in os.listdir(target_path) if f.lower().endswith(".ini")]
        print(f"[Mod Producer] Found {len(inis)} .ini files: {inis}")
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
            
            # --- NESTING PROTECTION (Hang Prevention) ---
            if os.path.abspath(version_path).startswith(os.path.abspath(target_path) + os.sep):
                self.report({'WARNING'}, f"Skipping nested build path: {version_path}")
                continue

            print(f"\n[Mod Producer] --- Processing profile: {profile.name} -> {folder_name} ---")
            try:
                if os.path.exists(version_path):
                    print(f"[Mod Producer] Removing existing build folder: {version_path}")
                    shutil.rmtree(version_path)
                
                # Clean copy: Ignore .py, .bak, and cache
                print(f"[Mod Producer] Copying from '{target_path}' to '{version_path}'...")
                ignore_func = shutil.ignore_patterns('*.py', '*.bak', '__pycache__')
                shutil.copytree(target_path, version_path, ignore=ignore_func)
                
                # 1. Delete disabled INI files in the copy
                delete_disabled_inis(version_path)

                # 2. Filter tiers in active INI files
                active_tiers = {t.strip() for t in profile.active_tiers.split(",") if t.strip()}
                for root, _, files in os.walk(version_path):
                    for file in files:
                        if file.lower().endswith(".ini"):
                            ini_full = os.path.join(root, file)
                            parse_ini_file(ini_full, active_tiers)
                
                # 3. Perform destructive cleanup
                destructive_cleanup(version_path)
                
                # 4. Perform Inquisitor Cleanup & Real Compression on remaining INI files
                from .cleanup_ops import inquisitor_cleanup_logic, real_compression_logic
                for root, _, files in os.walk(version_path):
                    for file in files:
                        if file.lower().endswith(".ini"):
                            ini_full = os.path.join(root, file)
                            print(f"[Mod Producer] Running post-build optimizations on: {file}")
                            inquisitor_cleanup_logic(ini_full, operator=None, create_backup=False)
                            real_compression_logic(ini_full, operator=None, create_backup=False)
                
                # --- PACKAGING ---
                if profile.zip_output:
                    zip_name = f"{version_path}.zip"
                    print(f"[Mod Producer] Zipping folder to: {zip_name}")
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
                print(f"[Mod Producer] {msg}")
                self.report({'ERROR'}, msg)
                batch_log.append(f"Failed {profile.name}")
                continue

        print(f"[Mod Producer] ================= BATCH BUILD FINISHED: {target_path} =================\n")
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
