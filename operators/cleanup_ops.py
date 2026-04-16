# RZMenu/operators/cleanup_ops.py
import bpy
import os
import re
from pathlib import Path
from collections import defaultdict
from .export_manager import get_target_path

# --- INQUISITOR Logic (from test.py) ---

def inquisitor_cleanup_logic(target_path, operator=None):
    if not os.path.exists(target_path):
        if operator: operator.report({'ERROR'}, f"File not found: {target_path}")
        return False

    with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    section_pattern = re.compile(r'^\[(.+)\]')
    run_pattern = re.compile(r'run\s*=\s*(CommandList(?:Element)?)(.+)', re.IGNORECASE)
    trigger_phrase = ";[META-INFO] [START] [MOD-BLOCK]"
    
    used_blocks = set()
    for line in lines:
        active_part = line.split(';')[0].split('#')[0]
        call = run_pattern.search(active_part)
        if call:
            prefix = call.group(1) 
            name = call.group(2).strip().lower()
            used_blocks.add(f"{prefix.lower()}{name}")

    new_lines = []
    in_purge_zone = False
    removed_empty = 0
    removed_comments = 0
    removed_blocks = 0
    
    i = 0
    while i < len(lines):
        line = lines[i]
        raw_line = line.strip()

        if trigger_phrase in line:
            in_purge_zone = True
            new_lines.append(line)
            i += 1
            continue

        if not in_purge_zone:
            new_lines.append(line)
            i += 1
            continue

        # --- PURGE ZONE ---
        if not raw_line:
            removed_empty += 1
            i += 1
            continue

        if raw_line.startswith(';'):
            removed_comments += 1
            i += 1
            continue

        match = section_pattern.match(raw_line)
        if match:
            section_full = match.group(1).lower()
            is_cmd = section_full.startswith("commandlist")
            is_elem = section_full.startswith("commandlistelement")
            
            if is_cmd or is_elem:
                if section_full in used_blocks:
                    new_lines.append(line)
                    i += 1
                    while i < len(lines) and not section_pattern.match(lines[i].strip()):
                        content_line = lines[i]
                        if content_line.strip() and not content_line.strip().startswith(';'):
                            new_lines.append(content_line)
                        else:
                            if not content_line.strip(): removed_empty += 1
                            else: removed_comments += 1
                        i += 1
                    continue
                else:
                    removed_blocks += 1
                    i += 1
                    while i < len(lines) and not section_pattern.match(lines[i].strip()):
                        i += 1
                    continue

        new_lines.append(line)
        i += 1

    if removed_blocks + removed_empty + removed_comments > 0:
        backup_name = target_path + ".bak"
        with open(backup_name, 'w', encoding='utf-8') as b:
            b.writelines(lines)
        
        with open(target_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        if operator:
            operator.report({'INFO'}, f"Cleanup Done: -{removed_empty} empty, -{removed_comments} comments, -{removed_blocks} blocks.")
        return True
    else:
        if operator: operator.report({'INFO'}, "File is already clean.")
        return False

# --- REAL COMPRESSION Logic (from test2.py) ---

TRIGGER_PHRASE = ";[META-INFO] [START] [MOD-BLOCK]"
WHITELIST_PREFIXES = ('$', 'run', 'post run', 'pre run', 'x', 'y', 'z', 'w')
BLACKLIST_VARS = {'$positionx', '$positiony', '$sizex', '$sizey'}

def get_all_vars(line):
    return re.findall(r'\$[a-zA-Z0-9_.]+', line)

def real_compression_logic(target_path, operator=None):
    if not os.path.exists(target_path):
        if operator: operator.report({'ERROR'}, f"File not found: {target_path}")
        return False

    with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()

    # 1. Collect Globals
    global_vars = set()
    in_constants = False
    for line in lines:
        raw = line.strip().lower()
        if raw == "[constants]": in_constants = True
        elif in_constants and raw.startswith('['): in_constants = False
        if in_constants and raw.startswith("global"):
            for v in get_all_vars(raw): global_vars.add(v.lower())

    # 2. Find patterns
    elements = {}
    current_elem = None
    in_zone = False
    section_re = re.compile(r'^\[(CommandListElement.+)\]', re.IGNORECASE)

    for line in lines:
        if TRIGGER_PHRASE in line: in_zone = True
        if not in_zone: continue
        match = section_re.match(line.strip())
        if match:
            current_elem = match.group(1)
            elements[current_elem] = []
        elif current_elem:
            # Если встретили начало ЛЮБОГО другого блока - закрываем текущий
            if line.strip().startswith('['):
                current_elem = None
            elif line.strip():
                elements[current_elem].append(line.strip())

    patterns = defaultdict(list)
    for name, content in elements.items():
        i = 0
        while i < len(content):
            chunk = []
            j = i
            while j < len(content):
                line = content[j].strip()
                line_low = line.lower()
                if any(line_low.startswith(p) for p in WHITELIST_PREFIXES):
                    vars_in_line = get_all_vars(line_low)
                    if not vars_in_line or all(v in global_vars for v in vars_in_line):
                        if not (vars_in_line and vars_in_line[0] in BLACKLIST_VARS):
                            chunk.append(line)
                            j += 1
                            continue
                break 
            if len(chunk) >= 2:
                patterns[tuple(chunk)].append(name)
                i = j
            else: i += 1

    # 3. Prepare replacements
    valid_replacements = {}
    idx_attr, idx_cmd = 0, 0
    for block, owners in patterns.items():
        if (len(block) * len(owners)) - (len(owners) + 1 + len(block)) > 0:
            is_attr = all(l.startswith('$') for l in block)
            new_name = f"CommandListGetDeduplicated{'Attribute' if is_attr else 'CommandList'}.{idx_attr if is_attr else idx_cmd}"
            if is_attr: idx_attr += 1 
            else: idx_cmd += 1
            valid_replacements[block] = new_name

    if not valid_replacements:
        if operator: operator.report({'INFO'}, "Nothing to compress.")
        return False

    # 4. Generate content
    new_lines = []
    in_zone = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if TRIGGER_PHRASE in line: in_zone = True
        match = section_re.match(line.strip())
        if in_zone and match:
            new_lines.append(line)
            elem_name = match.group(1)
            content = elements.get(elem_name, [])
            j = 0
            while j < len(content):
                found_match = False
                for block, new_name in sorted(valid_replacements.items(), key=lambda x: len(x[0]), reverse=True):
                    if tuple(content[j:j+len(block)]) == block:
                        new_lines.append(f"    run = {new_name}\n")
                        j += len(block)
                        found_match = True
                        break
                if not found_match:
                    new_lines.append(f"    {content[j]}\n")
                    j += 1
            
            # Пропускаем строки оригинального файла до начала СЛЕДУЮЩЕГО блока
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('['):
                i += 1
            continue
        new_lines.append(line)
        i += 1

    new_lines.append("\n; --- DEDUPLICATED BLOCKS START ---\n")
    for block, name in valid_replacements.items():
        new_lines.append(f"\n[{name}]\n")
        for bl in block:
            new_lines.append(f"    {bl}\n")

    # 5. Write
    backup = target_path + ".bak"
    with open(backup, 'w', encoding='utf-8') as b: b.writelines(lines)
    with open(target_path, 'w', encoding='utf-8') as f: f.writelines(new_lines)
    
    if operator:
        operator.report({'INFO'}, f"Compressed: Created {len(valid_replacements)} deduplicated blocks.")
    return True

# --- Operators ---

class RZM_OT_InquisitorCleanup(bpy.types.Operator):
    """Clean up .ini file: remove unused blocks, comments, and empty lines after mod-block trigger."""
    bl_idname = "rzm.inquisitor_cleanup"
    bl_label = "Clean Up .ini (Inquisitor)"
    bl_options = {'REGISTER', 'UNDO'}
    
    target_file : bpy.props.StringProperty(name="Target File", description="Full path to the .ini file")

    def execute(self, context):
        path = self.target_file
        if not path:
            folder = get_target_path(context)
            if not folder:
                self.report({'ERROR'}, "No target folder found.")
                return {'CANCELLED'}
            # Try to find the first .ini that isn't backup or archived
            for f in os.listdir(folder):
                if f.lower().endswith('.ini') and not any(x in f.lower() for x in ["bak", "archived", "disabled"]):
                    path = os.path.join(folder, f)
                    break
        
        if not path:
            self.report({'ERROR'}, "Target .ini file not found in mod folder.")
            return {'CANCELLED'}

        inquisitor_cleanup_logic(bpy.path.abspath(path), self)
        return {'FINISHED'}

class RZM_OT_RealCompression(bpy.types.Operator):
    """Compress .ini file: deduplicate common attribute and command sequences."""
    bl_idname = "rzm.real_compression"
    bl_label = "Compress .ini (Deduplication)"
    bl_options = {'REGISTER', 'UNDO'}
    
    target_file : bpy.props.StringProperty(name="Target File", description="Full path to the .ini file")

    def execute(self, context):
        path = self.target_file
        if not path:
            folder = get_target_path(context)
            if not folder:
                self.report({'ERROR'}, "No target folder found.")
                return {'CANCELLED'}
            for f in os.listdir(folder):
                if f.lower().endswith('.ini') and not any(x in f.lower() for x in ["bak", "archived", "disabled"]):
                    path = os.path.join(folder, f)
                    break
        
        if not path:
            self.report({'ERROR'}, "Target .ini file not found in mod folder.")
            return {'CANCELLED'}

        real_compression_logic(bpy.path.abspath(path), self)
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_InquisitorCleanup,
    RZM_OT_RealCompression
]
