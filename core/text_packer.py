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
    builds a dynamic character map, packs it into a 4-channel R16G16B16A16_UINT
    binary file, and returns a mapping of element IDs to text_id.
    """
    rzm = scene.rzm
    
    # Text alignments mapping for the shader
    ALIGN_MAP = {
        'LEFT': 0, 'CENTER': 1, 'RIGHT': 2,
        'FREE_LEFT': 3, 'FREE_CENTER': 4, 'FREE_RIGHT': 5
    }
    
    # Pass 1: Collect resolved strings with alignment
    collected_items = []
    
    def collect(text, align, key, subgroup, element, host=None):
        if not text:
            return
        resolved = resolve_meta_text(text, scene, element, host)
        # Convert align enum to int
        align_int = ALIGN_MAP.get(align, 0)
        collected_items.append({
            'resolved': resolved, 
            'align': align_int,
            'key': key, 
            'subgroup': subgroup
        })

    # 1. Regular Elements
    for element in rzm.elements:
        if not element.is_helper and not element.disable_export:
            if element.text_id:
                collect(element.text_id, element.text_align, (element.id, -1), 'single', element)
            
            if element.text_mode == 'CONDITIONAL_LIST':
                for i, item in enumerate(element.conditional_texts):
                    collect(item.text_id, element.text_align, (element.id, -1, i), 'conditional', element)

            if element.hover_text_id:
                # Hover text uses the same alignment for now
                collect(element.hover_text_id, element.text_align, (element.id, -1, 'hover'), 'single', element)

    # 2. Helpers
    for host in rzm.elements:
        if not host.disable_export and host.helper_ids:
            for ref in host.helper_ids:
                helper = next((e for e in rzm.elements if e.id == ref.helper_id), None)
                if helper:
                    if helper.text_id:
                        collect(helper.text_id, helper.text_align, (helper.id, host.id), 'single', helper, host)
                    
                    if helper.text_mode == 'CONDITIONAL_LIST':
                        for i, item in enumerate(helper.conditional_texts):
                            collect(item.text_id, helper.text_align, (helper.id, host.id, i), 'conditional', helper, host)
                            
                    if helper.hover_text_id:
                        collect(helper.hover_text_id, helper.text_align, (helper.id, host.id, 'hover'), 'single', helper, host)

    # Pass 2: Build Char Map (needed for custom font generation)
    custom_chars = []
    seen_chars = set()
    for item in collected_items:
        for c in item['resolved']:
            ord_c = ord(c)
            # Use standard ASCII 32-126. Anything outside needs a mapping slot.
            if ord_c < 32 or ord_c > 126:
                if c not in seen_chars:
                    seen_chars.add(c)
                    custom_chars.append(c)

    custom_chars.sort()
    char_to_code = {chr(i): i for i in range(32, 128)}
    for i, c in enumerate(custom_chars):
        char_to_code[c] = 128 + i

    # Store in memory for font generator
    RZMTextMapCache.custom_chars = custom_chars

    # Pass 3: Group Unique Text + Align combinations and pack
    # mapping is now element_key -> (text_id, length)
    mapping = {
        'single': {}, 
        'conditional': {} 
    }
    
    unique_texts = [] # List of (resolved_text, align_int)
    text_to_id = {}   # (resolved_text, align_int) -> text_id
    
    unique_texts.append((None, 0)) 
    
    # Collect unique (text, align) pairs
    for item in collected_items:
        pair = (item['resolved'], item['align'])
        if pair not in text_to_id:
            text_to_id[pair] = len(unique_texts)
            unique_texts.append(pair)
        
        # We return a tuple (text_id, length) for the template to use
        mapping[item['subgroup']][item['key']] = (text_to_id[pair], len(item['resolved']))

    num_meta_slots = len(unique_texts)
    
    # We need to compute offsets for characters. Characters follow metadata slots.
    current_char_offset = num_meta_slots
    
    # Preparation for buffer
    # slot_data[index] = (R, G, B, A)
    slots = {} # index -> (R, G, B, A)
    
    # Slot 0 is always empty (already handled by unique_texts[0] = (None, 0))
    slots[0] = (0, 0, 0, 0)

    for i in range(1, len(unique_texts)):
        resolved, align = unique_texts[i]
        encoded_len = len(resolved)
        
        # Write metadata slot
        # R=offset, G=length, B=alignment, A=0
        slots[i] = (current_char_offset, encoded_len, align, 0)
        
        # Write character slots
        for j, c in enumerate(resolved):
            code = char_to_code.get(c, 32) # Space fallback
            # R=0, G=0, B=0, A=character_code
            slots[current_char_offset + j] = (0, 0, 0, code)
            
        current_char_offset += encoded_len

    # Pack buffer
    text_buffer = bytearray()
    max_index = max(slots.keys()) if slots else -1
    
    for i in range(max_index + 1):
        r, g, b, a = slots.get(i, (0, 0, 0, 0))
        # Pack as 4x 16-bit unsigned integers (little-endian)
        text_buffer.extend(struct.pack('<HHHH', r, g, b, a))

    # Save to files
    res_dir = os.path.join(export_dir, "res")
    os.makedirs(res_dir, exist_ok=True)
    
    bin_path = os.path.join(res_dir, "texts.bin")
    with open(bin_path, 'wb') as f:
        f.write(text_buffer)

    return mapping

def get_text_mapping_for_j2(scene, export_dir):
    return pack_project_text(scene, export_dir)
