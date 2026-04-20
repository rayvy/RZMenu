# RZMenu/core/text_packer.py
import os
import struct
import bpy
import json

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
    if not parent and hasattr(element, 'parent_id') and element.parent_id != -1:
        parent = next((e for e in rzm.elements if e.id == element.parent_id), None)
        
    if parent:
        p_name = getattr(parent, 'element_name', "")
        p_text = getattr(parent, 'text_id', "")
        p_hover = getattr(parent, 'hover_text_id', "")
        
        p_color_r, p_color_g, p_color_b, p_color_a = "1.0", "1.0", "1.0", "1.0"
        if hasattr(parent, 'color') and parent.color:
            p_color_r = str(round(parent.color[0], 3)); p_color_g = str(round(parent.color[1], 3))
            p_color_b = str(round(parent.color[2], 3)); p_color_a = str(round(parent.color[3], 3))
        p_color = f"{p_color_r},{p_color_g},{p_color_b},{p_color_a}"

        p_val = ""; p_min = "0.0"; p_max = "1.0"
        if hasattr(parent, 'value_link') and parent.value_link:
            first_link = parent.value_link[0]
            v_name = first_link.value_name.lstrip('$@#~') if hasattr(first_link, 'value_name') else ""
            p_min = str(getattr(first_link, 'value_min', 0.0))
            p_max = str(getattr(first_link, 'value_max', 1.0))
            p_val = "$" + v_name

        vars_map.update({
            '~PName': p_name, '~Pname': p_name, '~PN': p_name, '~pn': p_name,
            '~PText': p_text, '~Ptext': p_text, '~PT': p_text, '~pt': p_text,
            '~PHover': p_hover, '~Phover': p_hover, '~PH': p_hover, '~ph': p_hover,
            '~PColor': p_color, '~PC': p_color,
            '~PColor.r': p_color_r, '~PC.r': p_color_r, '~PColor.g': p_color_g, '~PC.g': p_color_g,
            '~PColor.b': p_color_b, '~PC.b': p_color_b, '~PColor.a': p_color_a, '~PC.a': p_color_a,
            '~ParentValue': p_val, '~PV': p_val, '~pv': p_val,
        })

    sorted_keys = sorted(vars_map.keys(), key=len, reverse=True)
    resolved_text = text
    for key in sorted_keys:
        val = vars_map[key]
        resolved_text = resolved_text.replace(key, str(val) if val is not None else "")
        
    return resolved_text

def pack_project_text(scene, export_dir):
    """
    Unified text packer using the internal Blender loc_database.
    Static Indexing: Each unique (Resolved Text, Loc Key) pair gets a fixed index.
    """
    rzm = scene.rzm
    res_dir = os.path.join(export_dir, "res")
    os.makedirs(res_dir, exist_ok=True)
    
    # 1. Collect all translatable units from all elements
    units = [] # List of {'text': resolved_val, 'key': loc_key, 'id_key': (elem_id, host_id, type)}
    
    def add_unit(text, loc_key, elem, host, unit_type):
        """Helper to resolve and add a text unit with context."""
        resolved = resolve_meta_text(text, scene, elem, host)
        units.append({
            'text': resolved,
            'loc_key': loc_key,
            'id_key': (int(elem.id) if elem else -1, int(host.id) if host else -1, str(unit_type))
        })

    for elem in rzm.elements:
        if elem.disable_export: continue
        # Main text
        if elem.text_id: add_unit(elem.text_id, elem.loc_key, elem, None, 'main')
        # Hover text
        if elem.hover_text_id: add_unit(elem.hover_text_id, elem.hover_loc_key, elem, None, 'hover')
        # Conditional texts
        if elem.text_mode == 'CONDITIONAL_LIST':
            for i, ct in enumerate(elem.conditional_texts):
                add_unit(ct.text_id, ct.loc_key, elem, None, f"cond_{i}")

        # If it's a host, process helper instances
        if elem.helper_ids:
            for ref in elem.helper_ids:
                h = next((e for e in rzm.elements if e.id == ref.helper_id), None)
                if h:
                    if h.text_id: add_unit(h.text_id, h.loc_key, h, elem, 'main')
                    if h.hover_text_id: add_unit(h.hover_text_id, h.hover_loc_key, h, elem, 'hover')
                    if h.text_mode == 'CONDITIONAL_LIST':
                        for i, ct in enumerate(h.conditional_texts):
                            add_unit(ct.text_id, ct.loc_key, h, elem, f"cond_{i}")

    # 2. Build unique master list and mapping
    master_list = [] # List of {'default': text, 'loc_key': key}
    identity_to_index = {}
    mapping = {'single': {}, 'conditional': {}} # For Jinja templates
    
    # Reserve Index 0 for empty/unknown
    master_list.append({'default': "", 'loc_key': ""})
    
    for u in units:
        identity = (u['text'], u['loc_key'])
        if identity not in identity_to_index:
            identity_to_index[identity] = len(master_list)
            master_list.append({'default': u['text'], 'loc_key': u['loc_key']})
        
        idx = identity_to_index[identity]
        elem_id, host_id, u_type = u['id_key']
        
        # Use string keys for reliable Jinja lookup: "elemId_hostId_type"
        mapping_key = f"{elem_id}_{host_id}_{u_type}"
        
        if u_type.startswith('cond_'):
            # For conditional, we also store in a sub-dict for easier access
            mapping['conditional'][mapping_key] = idx
        else:
            mapping['single'][mapping_key] = idx

    # 3. Process Languages
    db_map = {} # loc_key -> {lang_id: text}
    for entry in rzm.loc_database:
        db_map[entry.name] = {t.lang_id: t.text for t in entry.translations}
        
    languages = rzm.languages if rzm.languages else [None]
    all_translated_texts = [] # List of Lists: [lang_idx][unit_idx]
    
    for lang in languages:
        lang_id = lang.lang_id if lang else ""
        lang_texts = []
        for unit in master_list:
            text = unit['default']
            l_key = unit['loc_key']
            if l_key and l_key in db_map:
                translated = db_map[l_key].get(lang_id, "")
                if translated: text = translated
            lang_texts.append(text)
        all_translated_texts.append(lang_texts)

    # 4. Global Character Union for Font Atlas
    total_chars = set()
    for lang_set in all_translated_texts:
        for s in lang_set:
            if s:
                for c in s:
                    if ord(c) > 126: total_chars.add(c)
    custom_chars = sorted(list(total_chars))
    RZMTextMapCache.custom_chars = custom_chars
    
    char_to_code = {chr(i): i for i in range(32, 128)}
    for i, c in enumerate(custom_chars): char_to_code[c] = 128 + i

    # 5. Pack Buffers
    for i, lang in enumerate(languages):
        lang_id = lang.lang_id if lang else ""
        lang_texts = all_translated_texts[i]
        
        text_buffer = bytearray()
        meta_buffer = bytearray()
        curr_off = 0
        
        for s in lang_texts:
            s_len = len(s)
            meta_buffer.extend(struct.pack('<II', curr_off, s_len))
            for c in s:
                text_buffer.extend(struct.pack('<H', char_to_code.get(c, 32)))
            curr_off += s_len
            
        suffix = f"_{lang_id}" if lang_id else ""
        with open(os.path.join(res_dir, f"texts{suffix}.bin"), 'wb') as f: f.write(text_buffer)
        with open(os.path.join(res_dir, f"texts_meta{suffix}.bin"), 'wb') as f: f.write(meta_buffer)
        
        # Save as main if active
        if lang and rzm.active_language_index < len(rzm.languages) and rzm.languages[rzm.active_language_index] == lang:
             with open(os.path.join(res_dir, "texts.bin"), 'wb') as f: f.write(text_buffer)
             with open(os.path.join(res_dir, "texts_meta.bin"), 'wb') as f: f.write(meta_buffer)

    return mapping

def get_text_mapping_for_j2(scene, export_dir):
    return pack_project_text(scene, export_dir)
