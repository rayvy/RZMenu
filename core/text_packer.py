# RZMenu/core/text_packer.py
import os
import struct
import bpy

import struct

class RZMTextMapCache:
    custom_chars = []
    
def resolve_meta_text(text, scene, element, host=None):
    """
    Replicates the logic of resolve_meta_var from utils.j2 in Python.
    Handles ~PT, ~PN, and other system meta-variables.
    """
    if not text or not isinstance(text, str) or "~" not in text:
        return str(text) if text is not None else ""
    
    rzm = scene.rzm
    meta = rzm.meta_data
    
    # 1. System Metadata
    author = meta.author_name if meta.author_name else "UNKNOWN"
    vars_map = {
        '~author_name': author,
        '~character_name': meta.character_name,
        '~outfit_name': meta.outfit_name,
        '~version_num': meta.version_num,
        '~mod_name': f"{meta.character_name} ({meta.outfit_name})",
        '~game_name': rzm.game.selection,
        '~menu_keybind': meta.menu_keybind,
        '~requirements': meta.requirements,
        '~community_respect': meta.community_respect,
        '~description': meta.description
    }
    
    # 2. Parent (Host) Data
    parent = host
    # If no explicit host, try to find parent by ID (for nested elements)
    if not parent and hasattr(element, 'parent_id') and element.parent_id:
        parent = next((e for e in rzm.elements if e.id == element.parent_id), None)
        
    if parent:
        p_name = getattr(parent, 'element_name', "")
        p_text = getattr(parent, 'text_id', "")
        p_hover = getattr(parent, 'hover_text_id', "")
        
        # Color string processing
        p_color_r, p_color_g, p_color_b, p_color_a = "1.0", "1.0", "1.0", "1.0"
        if hasattr(parent, 'color') and parent.color:
            p_color_r = str(round(parent.color[0], 3))
            p_color_g = str(round(parent.color[1], 3))
            p_color_b = str(round(parent.color[2], 3))
            p_color_a = str(round(parent.color[3], 3))
        p_color = f"{p_color_r},{p_color_g},{p_color_b},{p_color_a}"

        # Parent Value link logic
        p_val = ""
        p_min = "0.0"
        p_max = "1.0"
        if hasattr(parent, 'value_link') and parent.value_link:
            first_link = parent.value_link[0]
            if isinstance(first_link, str):
                v_name = first_link.lstrip('$@#~')
            elif hasattr(first_link, 'value_name'):
                v_name = first_link.value_name.lstrip('$@#~')
                p_min = str(getattr(first_link, 'value_min', 0.0))
                p_max = str(getattr(first_link, 'value_max', 1.0))
            else:
                v_name = ""
            p_val = "$" + v_name

        vars_map.update({
            '~PName': p_name, '~Pname': p_name, '~PN': p_name, '~pn': p_name,
            '~PText': p_text, '~Ptext': p_text, '~PT': p_text, '~pt': p_text,
            '~PHover': p_hover, '~Phover': p_hover, '~PH': p_hover, '~ph': p_hover,
            '~PColor': p_color, '~PC': p_color,
            '~PColor.r': p_color_r, '~PColor.R': p_color_r, '~PC.r': p_color_r, '~PC.R': p_color_r,
            '~PColor.g': p_color_g, '~PColor.G': p_color_g, '~PC.g': p_color_g, '~PC.G': p_color_g,
            '~PColor.b': p_color_b, '~PColor.B': p_color_b, '~PC.b': p_color_b, '~PC.B': p_color_b,
            '~PColor.a': p_color_a, '~PColor.A': p_color_a, '~PC.a': p_color_a, '~PC.A': p_color_a,
            '~ParentValue': p_val, '~PV': p_val, '~pv': p_val,
            '~ParentValueMin': p_min, '~PVMin': p_min, '~PVmin': p_min, '~pvmin': p_min,
            '~ParentValueMax': p_max, '~PVMax': p_max, '~PVmax': p_max, '~pvmax': p_max,
        })

    # 3. Perform replacements (longest keys first to avoid partial matches)
    sorted_keys = sorted(vars_map.keys(), key=len, reverse=True)
    resolved_text = text
    for key in sorted_keys:
        val = vars_map[key]
        if val is None: val = ""
        resolved_text = resolved_text.replace(key, str(val))
        
    return resolved_text

import json

def pack_project_text(scene, export_dir):
    """
    Collects all text from the scene elements, resolves meta-variables,
    builds a dynamic character map, packs it into a 16-bit binary file,
    and returns a mapping of element IDs to (offset, length).
    """
    rzm = scene.rzm
    
    # Pass 1: Collect resolved strings
    collected_strings = []
    
    def collect(text, key, subgroup, element, host=None):
        resolved = resolve_meta_text(text, scene, element, host)
        collected_strings.append({'resolved': resolved, 'key': key, 'subgroup': subgroup})

    # 1. Regular Elements
    for element in rzm.elements:
        if not element.is_helper and not element.disable_export:
            if element.text_id:
                collect(element.text_id, (element.id, -1), 'single', element)
            
            if element.text_mode == 'CONDITIONAL_LIST':
                for i, item in enumerate(element.conditional_texts):
                    collect(item.text_id, (element.id, -1, i), 'conditional', element)

            if element.hover_text_id:
                collect(element.hover_text_id, (element.id, -1, 'hover'), 'single', element)

    # 2. Helpers
    for host in rzm.elements:
        if not host.disable_export and host.helper_ids:
            for ref in host.helper_ids:
                helper = next((e for e in rzm.elements if e.id == ref.helper_id), None)
                if helper:
                    if helper.text_id:
                        collect(helper.text_id, (helper.id, host.id), 'single', helper, host)
                    
                    if helper.text_mode == 'CONDITIONAL_LIST':
                        for i, item in enumerate(helper.conditional_texts):
                            collect(item.text_id, (helper.id, host.id, i), 'conditional', helper, host)
                            
                    if helper.hover_text_id:
                        collect(helper.hover_text_id, (helper.id, host.id, 'hover'), 'single', helper, host)

    # Pass 2: Build Char Map
    custom_chars = []
    seen_chars = set()
    for item in collected_strings:
        for c in item['resolved']:
            ord_c = ord(c)
            # Use standard ASCII 32-126. Anything outside needs a mapping slot.
            if ord_c < 32 or ord_c > 126:
                if c not in seen_chars:
                    seen_chars.add(c)
                    custom_chars.append(c)

    # Sort to ensure determinism across exports with same chars
    custom_chars.sort()

    char_to_code = {}
    for i in range(32, 128):
        char_to_code[chr(i)] = i
    
    for i, c in enumerate(custom_chars):
        char_to_code[c] = 128 + i

    # Store in memory for font generator
    RZMTextMapCache.custom_chars = custom_chars

    # Pass 3: Encode and Pack (16-bit uints)
    mapping = {
        'single': {}, 
        'conditional': {} 
    }
    
    text_buffer = bytearray()
    current_offset = 0  # Offset in elements (characters), not bytes

    for item in collected_strings:
        resolved = item['resolved']
        key = item['key']
        subgroup = item['subgroup']
        
        encoded_len = len(resolved)
        for c in resolved:
            code = char_to_code.get(c, 32) # Space fallback
            # Pack as 16-bit unsigned integer (little-endian)
            text_buffer.extend(struct.pack('<H', code))
            
        offset = current_offset
        current_offset += encoded_len
        mapping[subgroup][key] = (offset, encoded_len)

    # Save to files
    bin_path = os.path.join(export_dir, "texts.bin")
    with open(bin_path, 'wb') as f:
        f.write(text_buffer)

    return mapping

def get_text_mapping_for_j2(scene, export_dir):
    return pack_project_text(scene, export_dir)
