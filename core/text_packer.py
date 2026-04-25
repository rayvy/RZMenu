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
    builds a dynamic character map across ALL languages, packs them into 
    binary buffers (texts.bin, texts_1.bin, etc.), and returns mapping.
    """
    rzm = scene.rzm
    
    ALIGN_MAP = {
        'LEFT': 0, 'CENTER': 1, 'RIGHT': 2,
        'FREE_LEFT': 3, 'FREE_CENTER': 4, 'FREE_RIGHT': 5
    }

    # Pass 1: Global Character Survey
    custom_chars = []
    seen_chars = set()
    
    def survey_text(text, element, host=None):
        if not text: return
        resolved = resolve_meta_text(text, scene, element, host)
        for c in resolved:
            ord_c = ord(c)
            if ord_c < 32 or ord_c > 126:
                if c not in seen_chars:
                    seen_chars.add(c)
                    custom_chars.append(c)

    def survey_all(item, host=None):
        # Survey base texts
        if hasattr(item, 'text_id'): survey_text(item.text_id, item if not host else host, host)
        if hasattr(item, 'hover_text_id'): survey_text(item.hover_text_id, item if not host else host, host)
        # Survey sub-items for conditional text
        if hasattr(item, 'text_mode') and item.text_mode == 'CONDITIONAL_LIST':
            for cond in item.conditional_texts:
                survey_all(cond, item if not host else host)
        # Survey localized texts
        if hasattr(item, 'localized_texts'):
            for lt in item.localized_texts:
                if lt.text_id: survey_text(lt.text_id, item if not host else host, host)
                if lt.hover_text_id: survey_text(lt.hover_text_id, item if not host else host, host)

    for element in rzm.elements:
        if not element.is_helper and not element.disable_export:
            survey_all(element)
    for host in rzm.elements:
        if not host.disable_export and host.helper_ids:
            for ref in host.helper_ids:
                helper = next((e for e in rzm.elements if e.id == ref.helper_id), None)
                if helper: survey_all(helper, host)

    custom_chars.sort()
    char_to_code = {chr(i): i for i in range(32, 128)}
    for i, c in enumerate(custom_chars):
        char_to_code[c] = 128 + i
    RZMTextMapCache.custom_chars = custom_chars

    # Helper to get text with fallback
    def get_loc_text(item, prop_name, lang_idx=None):
        base_val = getattr(item, prop_name, "")
        if lang_idx is None or lang_idx <= 0:
            return base_val
        if hasattr(item, 'localized_texts'):
            for lt in item.localized_texts:
                if lt.language_index == lang_idx:
                    val = getattr(lt, prop_name, "")
                    if val.strip():  # Only use valid override
                        return val
        return base_val

    # Pass 2: Generation Generator function
    res_dir = os.path.join(export_dir, "res")
    os.makedirs(res_dir, exist_ok=True)
    
    base_mapping = None

    def build_buffer_for_lang(lang_idx=None):
        collected_items = []
        
        def collect(text, align, key, subgroup, element, host=None):
            if not text: return
            resolved = resolve_meta_text(text, scene, element, host)
            collected_items.append({
                'resolved': resolved, 
                'align': ALIGN_MAP.get(align, 0),
                'key': key, 
                'subgroup': subgroup
            })

        for element in rzm.elements:
            if not element.is_helper and not element.disable_export:
                t = get_loc_text(element, 'text_id', lang_idx)
                if t: collect(t, element.text_align, (element.id, -1), 'single', element)
                
                if element.text_mode == 'CONDITIONAL_LIST':
                    for i, cond in enumerate(element.conditional_texts):
                        ct = get_loc_text(cond, 'text_id', lang_idx)
                        if ct: collect(ct, element.text_align, (element.id, -1, i), 'conditional', element)
                
                hov = get_loc_text(element, 'hover_text_id', lang_idx)
                if hov: collect(hov, element.text_align, (element.id, -1, 'hover'), 'single', element)

        for host in rzm.elements:
            if not host.disable_export and host.helper_ids:
                for ref in host.helper_ids:
                    helper = next((e for e in rzm.elements if e.id == ref.helper_id), None)
                    if helper:
                        t = get_loc_text(helper, 'text_id', lang_idx)
                        if t: collect(t, helper.text_align, (helper.id, host.id), 'single', helper, host)
                        
                        if helper.text_mode == 'CONDITIONAL_LIST':
                            for i, cond in enumerate(helper.conditional_texts):
                                ct = get_loc_text(cond, 'text_id', lang_idx)
                                if ct: collect(ct, helper.text_align, (helper.id, host.id, i), 'conditional', helper, host)
                        
                        hov = get_loc_text(helper, 'hover_text_id', lang_idx)
                        if hov: collect(hov, helper.text_align, (helper.id, host.id, 'hover'), 'single', helper, host)

        # Build binary memory mapping
        mapping = {'single': {}, 'conditional': {}}
        unique_texts = [(None, 0)]
        for item in collected_items:
            slot_id = len(unique_texts)
            unique_texts.append((item['resolved'], item['align']))
            mapping[item['subgroup']][item['key']] = (slot_id, len(item['resolved']))

        slots = {0: (0, 0, 0, 0)}
        current_char_offset = len(unique_texts)

        for i in range(1, len(unique_texts)):
            resolved, align = unique_texts[i]
            encoded_len = len(resolved)
            slots[i] = (current_char_offset, encoded_len, align, 0)
            for j, c in enumerate(resolved):
                code = char_to_code.get(c, 32)
                slots[current_char_offset + j] = (0, 0, 0, code)
            current_char_offset += encoded_len

        # Pack
        text_buffer = bytearray()
        max_idx = max(slots.keys()) if slots else -1
        for i in range(max_idx + 1):
            r, g, b, a = slots.get(i, (0, 0, 0, 0))
            text_buffer.extend(struct.pack('<HHHH', r, g, b, a))
            
        file_name = "texts.bin" if lang_idx is None else f"texts_{lang_idx}.bin"
        with open(os.path.join(res_dir, file_name), 'wb') as f:
            f.write(text_buffer)
            
        return mapping

    # Build default buffer
    base_mapping = build_buffer_for_lang(None)

    # Build language buffers if languages are defined
    meta = scene.rzm.meta_data
    if hasattr(meta, 'languages'):
        for lang in meta.languages:
            if lang.index > 0:
                build_buffer_for_lang(lang.index)

    # Save to scene for Jinja2 access (persistent representation uses Base mapping)
    def stringify_key(k):
        return ":".join(str(x) for x in k)

    json_mapping = {
        'single': {stringify_key(k): v for k, v in base_mapping['single'].items()},
        'conditional': {stringify_key(k): v for k, v in base_mapping['conditional'].items()}
    }
    scene.rzm.text_mapping_json = json.dumps(json_mapping)

    return base_mapping

def get_text_mapping_for_j2(scene, export_dir):
    return pack_project_text(scene, export_dir)
