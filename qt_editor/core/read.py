# RZMenu/qt_editor/core/read.py
import bpy
import re
from ..utils.image_cache import ImageCache
from ..utils.string_utils import find_common_pattern

# High Performance Data Layer: ID-to-Index Map
# This cache is rebuilt whenever we detect a structure change or on demand.
ID_CACHE = {} 
_LAST_COUNT = -1

def rebuild_id_cache(force=False):
    """Rebuilds the ID -> Index mapping for O(1) lookups."""
    global ID_CACHE, _LAST_COUNT
    if not bpy.context or not bpy.context.scene: return
    
    elements = bpy.context.scene.rzm.elements
    curr_count = len(elements)
    
    if not force and curr_count == _LAST_COUNT:
        return
        
    ID_CACHE = {elem.id: i for i, elem in enumerate(elements)}
    _LAST_COUNT = curr_count

def get_element_by_id(uid):
    """Returns the Blender element object for a given ID using O(1) lookup."""
    rebuild_id_cache()
    idx = ID_CACHE.get(uid)
    if idx is not None:
        elements = bpy.context.scene.rzm.elements
        if idx < len(elements):
            elem = elements[idx]
            if elem.id == uid:
                return elem
    
    # Fallback to linear search if cache is stale and rebuild didn't help (rare)
    rebuild_id_cache(force=True)
    idx = ID_CACHE.get(uid)
    if idx is not None:
        elements = bpy.context.scene.rzm.elements
        if idx < len(elements):
            elem = elements[idx]
            if elem.id == uid:
                return elem
                
    return None

def get_all_elements_list():
    results = []
    if not bpy.context or not bpy.context.scene: return results
    for elem in bpy.context.scene.rzm.elements:
        pid = getattr(elem, "parent_id", -1)
        results.append({
            "id": elem.id,
            "name": elem.element_name,
            "class_type": elem.elem_class,
            "parent_id": pid,
            "qt_priority": getattr(elem, "qt_priority", 0),
            "is_hidden": getattr(elem, "qt_hide", False),
            "is_selectable": getattr(elem, "qt_selectable", True),
            "is_preset": getattr(elem, "is_preset", False),
            "is_helper": getattr(elem, "is_helper", False),
            "is_template_prefab": getattr(elem, "is_template_prefab", False),
            "is_tab_container": getattr(elem, "is_tab_container", False),
            "page_color": list(getattr(elem, "page_color", (0.5, 0.5, 0.5, 1.0)))
        })
    return results

def get_variable_suggestions():
    """
    Returns a list of suggestion strings for formula autocomplete.
    Includes element names ($), rzm_values ($), toggles (@), and shapes (#).
    """
    suggestions = []
    if not bpy.context or not bpy.context.scene: return suggestions
    
    rzm = bpy.context.scene.rzm

    # 1. Elements (Standard Position/Size variables)
    for elem in rzm.elements:
        if getattr(elem, "is_preset", False) or getattr(elem, "disable_export", False):
            continue
        if not getattr(elem, "trackable", False) and elem.elem_class not in ['GRID_CONTAINER', 'ANCHOR']:
            continue
            
        # Sanitize name for usage in variables (alphanumeric + underscore)
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '', elem.element_name)
        if safe_name:
            # Flattened variations
            suggestions.append(f"${safe_name}PositionX")
            suggestions.append(f"${safe_name}PositionY")
            suggestions.append(f"${safe_name}SizeX")
            suggestions.append(f"${safe_name}SizeY")

    # 2. RZM Values ($)
    for val in rzm.rzm_values:
            name = val.value_name
            if not name.startswith("$"):
                name = f"${name}"
            suggestions.append(name)

    # 3. Toggles (@)
    for toggle in rzm.toggle_definitions:
        if toggle.toggle_name:
            suggestions.append(f"@{toggle.toggle_name}")

    # 4. Shapes (#)
    for shape in rzm.shapes:
        if shape.shape_name:
            suggestions.append(f"{shape.shape_name}") # Shape names usually have # prefix based on description

    # 5. System variables (~) — processed on exporter side
    suggestions.append("~ParentValue")
    suggestions.append("~PV")          # Short alias for ~ParentValue
    suggestions.append("~PName")
    suggestions.append("~PN")
    suggestions.append("~PText")
    suggestions.append("~PT")
    suggestions.append("~PHover")
    suggestions.append("~PH")
    suggestions.append("~PColor.r")
    suggestions.append("~PC.r")
    suggestions.append("~PColor.g")
    suggestions.append("~PC.g")
    suggestions.append("~PColor.b")
    suggestions.append("~PC.b")
    suggestions.append("~PColor.a")
    suggestions.append("~PC.a")
    suggestions.append("~PColor")
    suggestions.append("~PC")

    return sorted(suggestions)

def get_metadata_suggestions():
    """
    Returns a list of tags for Mod Info autocomplete, e.g. {{character_name}}
    Also returns ~ system variable aliases for use in text_id fields.
    """
    if not bpy.context or not bpy.context.scene: return []
    
    # {{tag}} style — for mod_info template text (meta.j2)
    meta_tags = [
        "{{character_name}}", "{{outfit_name}}", "{{version_num}}",
        "{{description}}", "{{menu_keybind}}",
        "{{requirements}}", "{{author_name}}", "{{community_respect}}",
        "{{mod_name}}", "{{game_name}}"
    ]
    
    # ~var style — for element text_id fields (resolve_meta_var in utils.j2)
    system_vars = [
        "~author_name", "~character_name", "~outfit_name",
        "~version_num", "~mod_name", "~game_name",
        "~menu_keybind", "~requirements",
        "~community_respect", "~description",
        "~PName", "~PN", "~PText", "~PT", "~PHover", "~PH", 
        "~PColor.r", "~PC.r", "~PColor.g", "~PC.g", "~PColor.b", "~PC.b", "~PColor.a", "~PC.a",
        "~PColor", "~PC"
    ]
    
    return sorted(meta_tags + system_vars)


def evaluate_mod_info(text, highlight=False):
    """
    Primitive replacement of tags for live preview in UI.
    If highlight is True, wraps replaced values in markers.
    """
    if not text or not bpy.context or not bpy.context.scene: return text
    rzm = bpy.context.scene.rzm
    meta = rzm.meta_data
    
    replacements = {
        "{{character_name}}": meta.character_name,
        "{{outfit_name}}": meta.outfit_name,
        "{{version_num}}": meta.version_num,
        "{{description}}": meta.description,
        "{{menu_keybind}}": meta.menu_keybind,
        "{{requirements}}": meta.requirements,
        "{{author_name}}": getattr(meta, "author_name", "UNKNOWN"),
        "{{community_respect}}": meta.community_respect,
        "{{mod_name}}": f"{meta.character_name} ({meta.outfit_name})",
        "{{game_name}}": rzm.game.name
    }
    
    result = text
    for tag, val in replacements.items():
        sub_val = str(val)
        if highlight:
            sub_val = f"\x01{sub_val}\x02"
        result = result.replace(tag, sub_val)
    return result


def evaluate_text_id(text_id, highlight=False, item_uid=-1):
    """
    Resolves ~system_var placeholders in element text_id for Qt viewport preview.
    In inspector the raw text_id stays as-is; viewport renders the resolved value.
    
    This mirrors the resolve_meta_var macro in utils.j2.
    """
    if not text_id or '~' not in text_id:
        return text_id
    if not bpy.context or not bpy.context.scene:
        return text_id
    
    rzm = bpy.context.scene.rzm
    meta = rzm.meta_data
    
    sys_vars = {
        "~author_name":       getattr(meta, "author_name", "UNKNOWN"),
        "~character_name":    meta.character_name,
        "~outfit_name":       meta.outfit_name,
        "~version_num":       meta.version_num,
        "~mod_name":          f"{meta.character_name} ({meta.outfit_name})",
        "~game_name":         rzm.game.name,
        "~menu_keybind":      meta.menu_keybind,
        "~requirements":      meta.requirements,
        "~community_respect": meta.community_respect,
        "~description":       meta.description,
    }
    
    if item_uid != -1:
        elem = get_element_by_id(item_uid)
        parent = None
        
        # Unpack Qt virtual ID to find exact host element if this is a preset/helper instance
        host_id = -1
        if item_uid >= 100000:
            current_id = item_uid
            while current_id >= 100000000: # It's a recursive child
                current_id = current_id // 1000
            host_id = current_id // 100000
        
        if elem:
            if getattr(elem, "parent_id", -1) != -1:
                parent = get_element_by_id(elem.parent_id)
            if not parent:
                # Origin element fallback - only used if not virtual
                for el in bpy.context.scene.rzm.elements:
                    if hasattr(el, "helper_ids") and any(h.helper_id == item_uid for h in el.helper_ids):
                        parent = el
                        break
                    if hasattr(el, "preset_ids") and any(p.preset_id == item_uid for p in el.preset_ids):
                        parent = el
                        break
                    if hasattr(el, "underlayer_preset_ids") and any(u.preset_id == item_uid for u in el.underlayer_preset_ids):
                        parent = el
                        break
        elif host_id != -1:
             # Virtual element (preset/helper instance) resolving to its exact host!
             parent = get_element_by_id(host_id)
             
        if parent is None and elem:
            parent = elem
            
        if parent:
                sys_vars["~PName"] = parent.element_name
                sys_vars["~Pname"] = parent.element_name
                sys_vars["~PN"] = parent.element_name
                sys_vars["~pn"] = parent.element_name
                sys_vars["~PText"] = getattr(parent, "text_id", "")
                sys_vars["~Ptext"] = sys_vars["~PText"]
                sys_vars["~PT"] = sys_vars["~PText"]
                sys_vars["~pt"] = sys_vars["~PText"]
                sys_vars["~PHover"] = getattr(parent, "hover_text_id", "")
                sys_vars["~Phover"] = sys_vars["~PHover"]
                sys_vars["~PH"] = sys_vars["~PHover"]
                sys_vars["~ph"] = sys_vars["~PHover"]
                if hasattr(parent, "color"):
                    c = parent.color
                else:
                    c = (1.0, 1.0, 1.0, 1.0)
                
                sys_vars["~PColor.r"] = sys_vars["~PColor.R"] = sys_vars["~PC.r"] = sys_vars["~PC.R"] = str(c[0])
                sys_vars["~PColor.g"] = sys_vars["~PColor.G"] = sys_vars["~PC.g"] = sys_vars["~PC.G"] = str(c[1])
                sys_vars["~PColor.b"] = sys_vars["~PColor.B"] = sys_vars["~PC.b"] = sys_vars["~PC.B"] = str(c[2])
                sys_vars["~PColor.a"] = sys_vars["~PColor.A"] = sys_vars["~PC.a"] = sys_vars["~PC.A"] = str(c[3])
                
                color_str = f"{c[0]},{c[1]},{c[2]},{c[3]}"
                sys_vars["~PColor"] = color_str
                sys_vars["~Pcolor"] = color_str
                sys_vars["~PC"] = color_str
                sys_vars["~pc"] = color_str

    
    result = text_id
    for var_key, var_val in sys_vars.items():
        if var_key in result:
            resolved = str(var_val) if var_val else ""
            if highlight:
                resolved = f"\x01{resolved}\x02"
            result = result.replace(var_key, resolved)
    return result

def get_available_languages():
    if not bpy.context or not bpy.context.scene: return []
    rzm = bpy.context.scene.rzm
    if not hasattr(rzm, 'meta_data'): return []
    return [(lang.index, lang.name) for lang in rzm.meta_data.languages]

def get_selection_details(selected_ids, active_id):

    if not bpy.context or not bpy.context.scene: return None
    elements = bpy.context.scene.rzm.elements
    selection = [get_element_by_id(uid) for uid in selected_ids]
    selection = [e for e in selection if e is not None]
    
    # Reference element for active values
    target = get_element_by_id(active_id)
    if not target and selection:
        target = selection[0]

    if target:
        # Check if parent is a grid container
        is_grid_child = False
        pid = getattr(target, "parent_id", -1)
        if pid != -1:
            parent = get_element_by_id(pid)
            if parent and getattr(parent, "elem_class", "") == "GRID_CONTAINER":
                is_grid_child = True

        # Helper to get "mixed" status: returns value if uniform, else None
        def get_uniform(prop_name, sub_idx=None, default=None):
            if not selection: return default
            vals = []
            for e in selection:
                if not hasattr(e, prop_name): 
                    vals.append(default)
                    continue
                raw = getattr(e, prop_name)
                val = raw[sub_idx] if sub_idx is not None else raw
                # Handle special types like color
                if prop_name == "color": val = tuple(val)
                vals.append(val)
            
            if not vals: return default
            return vals[0] if all(v == vals[0] for v in vals) else None

        color_uniform = get_uniform("color")
        color_vals = list(color_uniform) if color_uniform else [1.0, 1.0, 1.0, 1.0]
        if len(color_vals) == 3: color_vals.append(1.0)

        data = {
            "exists": True, "id": target.id, "active_id": active_id,
            "selected_ids": list(selected_ids), 
            "name": target.element_name if len(selection) <= 1 else "Multiple Elements",
            "name_pattern": find_common_pattern([e.element_name for e in selection])[0] if len(selection) > 1 else "",
            "original_names": [e.element_name for e in selection] if len(selection) > 1 else [],
            "class_type": get_uniform("elem_class"),
            
            # Identity & Meta
            "tag": get_uniform("tag", default=""),
            "priority": get_uniform("priority", default=0),
            "is_main_window": get_uniform("is_main_window", default=False),
            "is_tab_container": get_uniform("is_tab_container", default=False),
            "page_color": list(get_uniform("page_color") or (0.5, 0.5, 0.5, 1.0)),
            "disable_export": get_uniform("disable_export", default=False),
            "trackable": get_uniform("trackable", default=False),
            "export_tiers": [t.tier_id for t in selection[0].export_tiers] if selection else [],

            
            # Visibility
            "visibility_mode": get_uniform("visibility_mode", default="ALWAYS"),
            "visibility_condition": get_uniform("visibility_condition", default=""),
            
            # Events
            "hover_event_enabled": get_uniform("hover_event_enabled", default=False),
            "hover_event_formula": get_uniform("hover_event_formula", default=""),
            "click_event_enabled": get_uniform("click_event_enabled", default=False),
            "click_event_formula": get_uniform("click_event_formula", default=""),
            
            # Transform - Logic (Formula vs Static)
            "position_is_formula": get_uniform("position_is_formula", default=False),
            "size_is_formula": get_uniform("size_is_formula", default=False),
            
            # Transform - Static Values
            "pos_x": get_uniform("position", 0),
            "pos_y": get_uniform("position", 1), 
            "width": get_uniform("size", 0),
            "height": get_uniform("size", 1), 
            "rotation": get_uniform("rotation"),
            
            # Transform - Formulas
            "position_formula_x": get_uniform("position_formula_x", default=""),
            "position_formula_y": get_uniform("position_formula_y", default=""),
            "size_formula_x": get_uniform("size_formula_x", default=""),
            "size_formula_y": get_uniform("size_formula_y", default=""),
            "rotation_is_formula": get_uniform("rotation_is_formula", default=False),
            "rotation_formula": get_uniform("rotation_formula", default=""),
            "transform_is_formula": get_uniform("transform_is_formula", default=False),
            "transform_formula": get_uniform("transform_formula", default=""),

            # Anchor & Align
            "alignment": get_uniform("alignment"),
            "text_align": get_uniform("text_align"),
            
            # Style & Content
            "style_id": get_uniform("style_id", default=-1),
            "color": color_vals,
            "color_is_formula": get_uniform("color_is_formula", default=False),
            "color_formula_r": get_uniform("color_formula_r", default="1"),
            "color_formula_g": get_uniform("color_formula_g", default="1"),
            "color_formula_b": get_uniform("color_formula_b", default="1"),
            "color_formula_a": get_uniform("color_formula_a", default="1"),
            "font_slot": get_uniform("font_slot", default=0),
            "text_id": get_uniform("text_id", default=""),
            "text_id_is_data": get_uniform("text_id_is_data", default=False),
            "text_id_data_length": get_uniform("text_id_data_length", default=1),
            "text_id_pattern": find_common_pattern([e.text_id for e in selection])[0] if len(selection) > 1 else "",
            "original_text_ids": [e.text_id for e in selection] if len(selection) > 1 else [],
            "hover_text_id": get_uniform("hover_text_id", default=""),
            "hover_text_id_is_data": get_uniform("hover_text_id_is_data", default=False),
            "hover_text_id_data_length": get_uniform("hover_text_id_data_length", default=1),
            "hover_text_id_pattern": find_common_pattern([e.hover_text_id for e in selection])[0] if len(selection) > 1 else "",
            "original_hover_text_ids": [e.hover_text_id for e in selection] if len(selection) > 1 else [],
            "text_mode": get_uniform("text_mode", default="SINGLE"),
            "conditional_texts": [
                {"condition": ct.condition, "text_id": ct.text_id} 
                for ct in target.conditional_texts
            ] if target else [],
            "localized_texts": [
                {"language_index": lt.language_index, "text_id": lt.text_id, "hover_text_id": lt.hover_text_id} 
                for lt in target.localized_texts
            ] if target and hasattr(target, 'localized_texts') else [],
            
            # Images
            "image_mode": get_uniform("image_mode", default="SINGLE"),
            "image_id": get_uniform("image_id", default=-1),
            "image_source_type": next((img.source_type for img in bpy.context.scene.rzm.images if img.id == target.image_id), 'CUSTOM') if target and target.image_id != -1 else 'NONE',
            "svg_scale": get_uniform("svg_scale", default=1.0),
            "svg_offset_x": get_uniform("svg_offset", 0),
            "svg_offset_y": get_uniform("svg_offset", 1),
            "hover_image_id": get_uniform("hover_image_id", default=-1),
            "flip_x": get_uniform("flip_x", default=False),
            "flip_y": get_uniform("flip_y", default=False),
            "image_blending_mode": get_uniform("image_blending_mode", default='NONE'),
            "tile_uv_x": get_uniform("tile_uv", 0),
            "tile_uv_y": get_uniform("tile_uv", 1),
            "tile_size_x": get_uniform("tile_size", 0),
            "tile_size_y": get_uniform("tile_size", 1),
            "conditional_images": [
                {"condition": ci.condition, "image_id": ci.image_id} 
                for ci in target.conditional_images
            ] if target else [],

            # Grid Container
            "grid_cell_size": get_uniform("grid_cell_size"),
            "grid_rows": get_uniform("grid_min_cells", 1), # Mapping logic to min_cells Y for rows representation
            "grid_cols": get_uniform("grid_min_cells", 0), # Mapping logic to min_cells X
            # Note: Using raw names for actual data editing
            "grid_min_cells_x": get_uniform("grid_min_cells", 0),
            "grid_min_cells_y": get_uniform("grid_min_cells", 1),
            "grid_max_cells_x": get_uniform("grid_max_cells", 0),
            "grid_max_cells_y": get_uniform("grid_max_cells", 1),
            "grid_wrap_mode": get_uniform("grid_wrap_mode", default="SCROLL"),
            
            # Logic & Links
            "value_link_is_formula": get_uniform("value_link_is_formula", default=False),
            "value_link_formula": get_uniform("value_link_formula", default=""),
            "value_links": [
                {
                    "value_name": vl.value_name,
                    "value_name_pattern": find_common_pattern([
                        next((v.value_name for v in e.value_link if i < len(e.value_link)), "") 
                        for e in selection
                    ])[0] if len(selection) > 1 else "",
                    "original_value_names": [
                        next((v.value_name for v in e.value_link if i < len(e.value_link)), "") 
                        for e in selection
                    ] if len(selection) > 1 else [],
                    "value_min": vl.value_min,
                    "value_max": vl.value_max
                }
                for i, vl in enumerate(target.value_link)
            ] if target else [],
            
            "fx": [
                item.value for item in target.fx
            ] if target else [],
            "fn": [
                item.function_name for item in target.fn
            ] if target else [],
            "properties": [
                {"key": p.key, "type": p.value_type, "s": p.string_value, "i": p.int_value, "f": p.float_value} 
                for p in target.properties
            ] if target else [],
            "toggles": [
                {"name": t.toggle_name, "bits": [b.value for b in t.bits]} 
                for t in target.toggles
            ] if target else [],
            "disable_default_xy": get_uniform("disable_default_xy", default=False),

            # Button Specifics
            "disable_button_nums": get_uniform("disable_button_nums", default=False),
            "disable_button_popup": get_uniform("disable_button_popup", default=False),
            "disable_slider_nums": get_uniform("disable_slider_nums", default=False),
            "disable_slider_blur": get_uniform("disable_slider_blur", default=False),
            "disable_slider_prebuild_render": get_uniform("disable_slider_prebuild_render", default=False),

            # Editor Flags
            "is_hidden": get_uniform("qt_hide"),
            "is_locked_pos": get_uniform("qt_lock_pos", default=False),
            "is_locked_size": get_uniform("qt_lock_size", default=False),
            "qt_lock_ratio": get_uniform("qt_lock_ratio", default=False),
            
            # Computed Helpers
            "is_multi": len(selected_ids) > 1,
            "is_grid_child": is_grid_child,
            
            # Presets
            "is_preset": get_uniform("is_preset", default=False),
            "qt_preset_hide": get_uniform("qt_preset_hide", default=False),
            "preset_ids": [
                p.preset_id for p in target.preset_ids
            ] if target and hasattr(target, "preset_ids") else [],
            "underlayer_preset_ids": [
                p.preset_id for p in target.underlayer_preset_ids
            ] if target and hasattr(target, "underlayer_preset_ids") else [],

            # Helpers
            "is_helper": get_uniform("is_helper", default=False),
            "helper_ids": [
                h.helper_id for h in target.helper_ids
            ] if target and hasattr(target, "helper_ids") else [],

            # Template Prefab
            "is_template_prefab": get_uniform("is_template_prefab", default=False),
            "template_prefab": get_uniform("template_prefab", default="MAIN_BLOCK"),

            # Run Link binding (per-element, not per-variable)
            "run_link_id": get_uniform("run_link_id", default=-1),
        }

        return data
    return None

def get_viewport_data():
    results = []
    if not bpy.context or not bpy.context.scene: return results
    
    rzm = bpy.context.scene.rzm

    for idx, elem in enumerate(rzm.elements):
        color_list = None
        if hasattr(elem, "color"):
            color_list = list(elem.color)
            if len(color_list) == 3: color_list.append(1.0)

        # Prepare basic data
        item = {
            "id": elem.id,
            "order": idx,  # Array index for Z-ordering
            "name": elem.element_name,
            "class_type": elem.elem_class,
            "parent_id": getattr(elem, "parent_id", -1),

            # Static geometry (defaults)
            "pos_x": elem.position[0],
            "pos_y": elem.position[1],
            "width": elem.size[0],
            "height": elem.size[1],
            "rotation": elem.rotation,

            # Formula flags
            "pos_is_formula": getattr(elem, "position_is_formula", False),
            "size_is_formula": getattr(elem, "size_is_formula", False),
            "rotation_is_formula": getattr(elem, "rotation_is_formula", False),
            "transform_is_formula": getattr(elem, "transform_is_formula", False),

            # Formula strings (Important: sanitize/default to empty string)
            "formula_x": getattr(elem, "position_formula_x", ""),
            "formula_y": getattr(elem, "position_formula_y", ""),
            "formula_w": getattr(elem, "size_formula_x", ""),
            "formula_h": getattr(elem, "size_formula_y", ""),
            "transform_is_formula": getattr(elem, "transform_is_formula", False),
            "transform_formula": getattr(elem, "transform_formula", ""),
            "disable_export": getattr(elem, "disable_export", False),
            "trackable": getattr(elem, "trackable", False),


            # Visuals
            "image_id": elem.image_id,
            "hover_image_id": getattr(elem, "hover_image_id", -1),
            "image_blending_mode": getattr(elem, "image_blending_mode", 'NONE'),
            "image_source_type": next((img.source_type for img in rzm.images if img.id == elem.image_id), 'STATIC') if elem.image_id != -1 else 'NONE',
            "svg_preserve_color": next((img.svg_preserve_color for img in rzm.images if img.id == elem.image_id), True) if elem.image_id != -1 else True,
            "svg_scale": getattr(elem, "svg_scale", 1.0),
            "svg_offset_x": getattr(elem, "svg_offset", [0, 0])[0],
            "svg_offset_y": getattr(elem, "svg_offset", [0, 0])[1],
            "font_slot": getattr(elem, "font_slot", 0),
            "flip_x": getattr(elem, "flip_x", False),
            "flip_y": getattr(elem, "flip_y", False),
            "text_id": getattr(elem, "text_id", ""),
            "color": color_list,
            "is_hidden": getattr(elem, "qt_hide", False),
            "is_selectable": getattr(elem, "qt_selectable", True),
            "is_locked_pos": getattr(elem, "qt_lock_pos", False),
            "is_locked_size": getattr(elem, "qt_lock_size", False),
            "qt_lock_ratio": getattr(elem, "qt_lock_ratio", False),
            "alignment": getattr(elem, "alignment", "BOTTOM_LEFT"),
            "text_align": getattr(elem, "text_align", "LEFT"),

            # Formula Logic (Color / Logic)
            "color_is_formula": getattr(elem, "color_is_formula", False),
            "color_formula_r": getattr(elem, "color_formula_r", "1"),
            "color_formula_g": getattr(elem, "color_formula_g", "1"),
            "color_formula_b": getattr(elem, "color_formula_b", "1"),
            "color_formula_a": getattr(elem, "color_formula_a", "1"),
            "value_link_is_formula": getattr(elem, "value_link_is_formula", False),
            "value_link_formula": getattr(elem, "value_link_formula", ""),

            "is_tab_container": getattr(elem, "is_tab_container", False),
            "page_color": list(getattr(elem, "page_color", [0.5, 0.5, 0.5, 1.0])),
            "qt_preset_hide": getattr(elem, "qt_preset_hide", False),
            "is_helper": getattr(elem, "is_helper", False),
            "is_template_prefab": getattr(elem, "is_template_prefab", False),
            
            # Grid props
            "grid_cell_size": getattr(elem, "grid_cell_size", 50),
            "grid_cols": getattr(elem, "grid_min_cells", [1,1])[0],
            "style_id": getattr(elem, "style_id", -1)
        }
        results.append(item)

    # --- PRESET LOGIC: VIRTUAL ELEMENT INJECTION ---
    # 1. Create a map of ID -> Element Data for fast lookup of preset sources
    # We can use the results list we just built, but we need to index it.
    elem_map = {item['id']: item for item in results}
    
    virtual_elements = []
    
    for host_item in results:
        # Check if host uses presets
        # We need to access the Blender object to iterate the collection properly because
        # our simple dict 'host_item' doesn't contain the full collection of presets yet.
        # We need to re-access the blender element.
        # It's inefficient to assume index matches, so let's use ID or re-find.
        # Optimization: We are iterating 'results' which came from 'rzm.elements' in order.
        # So 'bpy.context.scene.rzm.elements[idx]' matches results[idx] if no deletions happened during this loop (safe).
        # Wait, 'results' has 'order' == loop index.
        
        host_elem = bpy.context.scene.rzm.elements[host_item['order']] 
        
        if getattr(host_elem, "is_preset", False):
            # Presets themselves cannot have presets (to avoid infinite recursion for now)
            continue
            
        if getattr(host_elem, "qt_preset_hide", False):
            continue
            
        if not hasattr(host_elem, "preset_ids"): continue # Safety if property not added yet
        
        # Iterate underlayers assigned to this element (UNDERNEATH)
        if hasattr(host_elem, "underlayer_preset_ids"):
            for p_ref in host_elem.underlayer_preset_ids:
                preset_id = p_ref.preset_id
                preset_source = elem_map.get(preset_id)
                if not preset_source: continue
                
                virtual_id = host_item['id'] * 100000 + preset_id + 50000 # Offset to avoid collision with standard presets
                v_item = preset_source.copy()
                v_item['id'] = virtual_id
                v_item['parent_id'] = host_item['id']
                v_item['name'] = f"{host_item['name']}::Underlayer_{preset_source['name']}"
                v_item['is_selectable'] = False
                v_item['is_underlayer'] = True # FLAG FOR VIEWPORT
                
                if not v_item['pos_is_formula']:
                    v_item['pos_x'] = 0
                    v_item['pos_y'] = 0
                if not v_item['size_is_formula']:
                    v_item['width'] = host_item['width']
                    v_item['height'] = host_item['height']
                
                v_item['is_hidden'] = False 
                virtual_elements.append(v_item)

        # Iterate standard presets assigned to this element
        for p_ref in host_elem.preset_ids:

            preset_id = p_ref.preset_id
            preset_source = elem_map.get(preset_id)
            
            if not preset_source: 
                source_bl = get_element_by_id(preset_id)
                if not source_bl: continue
                continue 
            
            # Create Virtual Element
            # ID Scheme: HostID * 100000 + PresetID (Simple collision avoidance)
            # Limit: ID < 2GB. standard IDs are small (1, 2, 3). 
            # If Host is 100, Preset is 5, ID = 10000005. Safe.
            virtual_id = host_item['id'] * 100000 + preset_id
            
            # Clone source data
            v_item = preset_source.copy()
            
            # Overwrite Identity
            v_item['id'] = virtual_id
            v_item['parent_id'] = host_item['id'] # Parent to host so they move together visually
            v_item['name'] = f"{host_item['name']}::{preset_source['name']}"
            
            # Overwrite State
            v_item['is_selectable'] = False # Non-interactive
            v_item['is_locked_pos'] = False # Hide lock icon (visual only)
            v_item['is_locked_size'] = False # Hide lock icon (visual only)
            v_item['is_hidden'] = False 
            
            # Formulas for Presets are now handled by FormulaEvaluator logic (context-aware).
            # We don't need manual string replacement here.
            
            # Positioning Logic:
            # If NOT using a formula, we snap to Host 1:1.
            
            # Positioning Logic:
            # Presets usually just stick to the parent at (0,0) relative?
            # Or do they have their own offset from the preset definition?
            # User said: "наследует 1 в 1 позицию и размер если только не прописано formula position"
            # Since standard parenting in our system adds positions (Child World = Parent World + Child Local),
            # If we want 1:1 overlap, Child Local must be (0,0).
            # The preset source has a position (e.g. 100, 100).
            # If we just copy that, the virtual element will be offset by 100, 100 from the host.
            # User requirement: "ignore position and size unless formula".
            # So default visual pos/size should match Host?
            # "визуальный дубликат который наследует свойства элемента позиции и размера" -> It looks like the host.
            # BUT "рамка_0 сможет реагировать" implies it might be slightly larger or different?
            # If Preset Source is a "Border" meant to be 10px bigger, it likely has size/pos set in its own definition?
            # NO: "Единственное что от него не будет копироваться от пресета это position и size"
            # So: Virtual Pos/Size = Host Pos/Size.
            # IN OUR SYSTEM:
            # If parent_id is set, the Viewport/Qt system calculates absolute pos.
            # To match Host exactly in World Space:
            # If Virtual is child of Host: Local Pos must be (0,0). Size must be Host Size.
            
            # Force Local Pos to 0,0
            v_item['pos_x'] = 0
            v_item['pos_y'] = 0
            
            # Force Size to Host Size (unless formula?)
            # "если только не прописано formula position" -> user implies preset logic overrides.
            # If Preset Source has a formula, we use it?
            # "Formula" in our system is usually evaluated globally or relative to parent.
            # If we keep the formula strings from the preset source, and set 'parent_id' to host,
            # the formula evaluator will see "$ParentSizeX" and work correctly!
            # So:
            # 1. If Source has Formula -> Keep Formula.
            # 2. If Source has Static -> Override with 0 (Position) and Host Size (Size).
            
            if not v_item['pos_is_formula']:
                v_item['pos_x'] = 0
                v_item['pos_y'] = 0
                
            if not v_item['size_is_formula']:
                 # Inherit Host Size
                 v_item['width'] = host_item['width']
                 v_item['height'] = host_item['height']
            
            # Ensure it is not hidden by standard logic (though host might hide it via qt_preset_hide)
            v_item['is_hidden'] = False 
            
            virtual_elements.append(v_item)

            # --- PRESET CHILDREN: Full recursive subtree rendering ---
            # Build a map of parent_id -> list of children from the base 'results'
            def collect_preset_children_recursive(source_elem_id, virtual_parent_id, depth=0):
                """Recursively collect virtual copies of all descendants of source_elem_id."""
                if depth > 20: return  # Hard safety limit
                for child_item in results:
                    if child_item['parent_id'] == source_elem_id:
                        # Give child a deterministic virtual ID:
                        # Use a prime-based hash to minimize collisions in deep trees
                        child_virtual_id = virtual_parent_id * 1000 + child_item['id'] % 1000
                        child_v = child_item.copy()
                        child_v['id'] = child_virtual_id
                        child_v['parent_id'] = virtual_parent_id
                        child_v['is_selectable'] = False
                        child_v['is_locked_pos'] = False
                        child_v['is_locked_size'] = False
                        child_v['is_hidden'] = False
                        child_v['name'] = f"{host_item['name']}::{child_item['name']}"
                        virtual_elements.append(child_v)
                        # Recurse into this child's children
                        collect_preset_children_recursive(child_item['id'], child_virtual_id, depth + 1)

            collect_preset_children_recursive(preset_id, virtual_id)

    # --- HELPER LOGIC: Virtual element injection (same as presets, but flagged as helper) ---
    for host_item in results:
        host_elem = bpy.context.scene.rzm.elements[host_item['order']]

        if getattr(host_elem, "is_preset", False) or getattr(host_elem, "is_helper", False):
            continue

        if getattr(host_elem, "qt_preset_hide", False):
            continue

        if not hasattr(host_elem, "helper_ids"): continue

        for h_ref in host_elem.helper_ids:
            helper_id = h_ref.helper_id
            helper_source = elem_map.get(helper_id)
            if not helper_source:
                continue

            # Helper virtual ID scheme: offset +70000 from preset scheme to avoid collision
            virtual_id = host_item['id'] * 100000 + helper_id + 70000

            h_item = helper_source.copy()
            h_item['id'] = virtual_id
            h_item['parent_id'] = host_item['id']
            h_item['name'] = f"{host_item['name']}::Helper_{helper_source['name']}"
            h_item['is_selectable'] = False
            h_item['is_locked_pos'] = False
            h_item['is_locked_size'] = False
            h_item['is_hidden'] = False
            h_item['is_helper_instance'] = True  # Flag for future exporter use

            if not h_item['pos_is_formula']:
                h_item['pos_x'] = 0
                h_item['pos_y'] = 0
            if not h_item['size_is_formula']:
                h_item['width'] = host_item['width']
                h_item['height'] = host_item['height']

            virtual_elements.append(h_item)

            # Recursive children for helpers (same logic as presets)
            def collect_helper_children_recursive(source_elem_id, virtual_parent_id, depth=0):
                if depth > 20: return
                for child_item in results:
                    if child_item['parent_id'] == source_elem_id:
                        child_virtual_id = virtual_parent_id * 1000 + child_item['id'] % 1000
                        child_v = child_item.copy()
                        child_v['id'] = child_virtual_id
                        child_v['parent_id'] = virtual_parent_id
                        child_v['is_selectable'] = False
                        child_v['is_locked_pos'] = False
                        child_v['is_locked_size'] = False
                        child_v['is_hidden'] = False
                        child_v['name'] = f"{host_item['name']}::HChild_{child_item['name']}"
                        child_v['is_helper_instance'] = True
                        virtual_elements.append(child_v)
                        collect_helper_children_recursive(child_item['id'], child_virtual_id, depth + 1)

            collect_helper_children_recursive(helper_id, virtual_id)

    results.extend(virtual_elements)

    return results

# Stubs for legacy calls
def get_structure_signature(): return 0
def get_element_signature(active_id): return 0
def get_viewport_signature(): return 0
def get_scene_info(): return {"count": 0, "name": ""}
def get_active_object_safe(): return None
def get_selected_objects_safe(): return []

def get_available_images() -> list[dict]:
    results = []
    if not bpy.context or not bpy.context.scene:
        return results
    
    rzm = getattr(bpy.context.scene, "rzm", None)
    if not rzm:
        return results
        
    for img in rzm.images:
        ImageCache.instance().pre_cache_image(img.id)
        img_dict = {
            'id': img.id,
            'name': img.display_name,
            'source_type': getattr(img, 'source_type', 'CUSTOM'),
            'path': getattr(img, 'anim_source_path', ''),
            'uv_coords': [img.uv_coords[0], img.uv_coords[1]],
            'uv_size': [img.uv_size[0], img.uv_size[1]],
        }
        
        # Инфо об анимации
        if img_dict['source_type'] == 'ANIMATED':
            img_dict.update({
                'anim_preset': img.anim_export_preset,
                'anim_start': img.anim_start_frame,
                'anim_end': img.anim_end_frame,
                'anim_max': img.anim_max_frames,
                'anim_speed': img.anim_speed_multiplier,
                'anim_frame_count': img.anim_frame_count,
                'anim_total_dur': img.anim_total_duration,
                'anim_paused': img.anim_paused
            })
        
        results.append(img_dict)
    return results
def get_style_properties(style_id):
    if not bpy.context or not bpy.context.scene: return None
    styles = bpy.context.scene.rzm.styles
    if style_id < 0 or style_id >= len(styles): return None
    style = styles[style_id]
    
    return {
        'style_id': style_id,
        'name': style.name,
        'use_shadow': style.use_shadow,
        'shadow_offset': list(style.shadow_offset),
        'shadow_blur': style.shadow_blur,
        'shadow_color': list(style.shadow_color),
        
        'use_glow': style.use_glow,
        'glow_radius': style.glow_radius,
        'glow_intensity': style.glow_intensity,
        'glow_color': list(style.glow_color),
        
        'use_outline': style.use_outline,
        'outline_thickness': style.outline_thickness,
        'outline_color': list(style.outline_color),
        
        'use_grayscale': style.use_grayscale,
        'grayscale_amount': style.grayscale_amount,
        
        'use_chromatic': style.use_chromatic,
        'chromatic_offset': style.chromatic_offset,
        
        'use_gradient': style.use_gradient,
        'grad_color_1': list(style.grad_color_1),
        'grad_color_2': list(style.grad_color_2),
        'grad_angle': style.grad_angle,
        
        'anim_hover_resize': style.anim_hover_resize,
        'hover_scale_factor': style.hover_scale_factor,
        
        'anim_hover_sheen': style.anim_hover_sheen,
        'sheen_speed': style.sheen_speed,
        'sheen_width': style.sheen_width,
        'sheen_color': list(style.sheen_color),
        
        'anim_rotate': style.anim_rotate,
        'rotate_speed': style.rotate_speed,
        
        'use_blur': style.use_blur,
        'blur_strength': style.blur_strength,
        'use_blur_mask': style.use_blur_mask,

        'fn_fix_ratio': style.fn_fix_ratio,
    }

def get_all_styles():
    """Returns a list of all style names and their IDs."""
    results = []
    if not bpy.context or not bpy.context.scene: return results
    styles = bpy.context.scene.rzm.styles
    for i, style in enumerate(styles):
        results.append({
            'id': i,
            'name': style.name
        })
    return results
