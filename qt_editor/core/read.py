# RZMenu/qt_editor/core/read.py
import bpy
import re
from ..utils.image_cache import ImageCache

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
            "is_hidden": getattr(elem, "qt_hide", False),
            "is_selectable": getattr(elem, "qt_selectable", True)
        })
    return results

def get_variable_suggestions():
    """
    Returns a list of suggestion strings for formula autocomplete.
    Includes element names prefixed with $.
    """
    suggestions = []
    if not bpy.context or not bpy.context.scene: return suggestions
    
    # 1. Elements
    for elem in bpy.context.scene.rzm.elements:
        # Sanitize name for usage in variables (alphanumeric + underscore)
        safe_name = re.sub(r'[^a-zA-Z0-9_]', '', elem.element_name)
        if safe_name:
            suggestions.append(f"${safe_name}")
            
            # Optional: Add common properties for help
            # suggestions.append(f"${safe_name}.x")
            # suggestions.append(f"${safe_name}.width")
            
    # 2. Global Toggles/Values (Future proofing based on p_ui.py)
    # for toggle in bpy.context.scene.rzm.toggles:
    #     suggestions.append(f"@{toggle.name}")

    return sorted(suggestions)

def get_selection_details(selected_ids, active_id):
    if not bpy.context or not bpy.context.scene: return None
    elements = bpy.context.scene.rzm.elements
    selection = [e for e in elements if e.id in selected_ids]
    
    # Reference element for active values
    target = next((e for e in elements if e.id == active_id), None)
    if not target and selection:
        target = selection[0]

    if target:
        # Check if parent is a grid container
        is_grid_child = False
        pid = getattr(target, "parent_id", -1)
        if pid != -1:
            parent = next((e for e in elements if e.id == pid), None)
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
            "class_type": get_uniform("elem_class"),
            
            # Identity & Meta
            "tag": get_uniform("tag", default=""),
            "priority": get_uniform("priority", default=0),
            "is_main_window": get_uniform("is_main_window", default=False),
            
            # Visibility
            "visibility_mode": get_uniform("visibility_mode", default="ALWAYS"),
            "visibility_condition": get_uniform("visibility_condition", default=""),
            
            # Transform - Logic (Formula vs Static)
            "position_is_formula": get_uniform("position_is_formula", default=False),
            "size_is_formula": get_uniform("size_is_formula", default=False),
            
            # Transform - Static Values
            "pos_x": get_uniform("position", 0),
            "pos_y": get_uniform("position", 1), 
            "width": get_uniform("size", 0),
            "height": get_uniform("size", 1), 
            
            # Transform - Formulas
            "position_formula_x": get_uniform("position_formula_x", default=""),
            "position_formula_y": get_uniform("position_formula_y", default=""),
            "size_formula_x": get_uniform("size_formula_x", default=""),
            "size_formula_y": get_uniform("size_formula_y", default=""),

            # Anchor & Align
            "alignment": get_uniform("alignment"),
            "text_align": get_uniform("text_align"),
            
            # Style & Content
            "color": color_vals,
            "text_id": get_uniform("text_id", default=""),
            "hover_text_id": get_uniform("hover_text_id", default=""),
            
            # Images
            "image_mode": get_uniform("image_mode", default="SINGLE"),
            "image_id": get_uniform("image_id", default=-1),
            "tile_uv_x": get_uniform("tile_uv", 0),
            "tile_uv_y": get_uniform("tile_uv", 1),
            "tile_size_x": get_uniform("tile_size", 0),
            "tile_size_y": get_uniform("tile_size", 1),

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
            
            # Button Specifics
            "disable_button_nums": get_uniform("disable_button_nums", default=False),
            "disable_button_popup": get_uniform("disable_button_popup", default=False),

            # Editor Flags
            "is_hidden": get_uniform("qt_hide"),
            "is_locked_pos": get_uniform("qt_lock_pos"),
            "is_locked_size": get_uniform("qt_lock_size"),
            
            # Computed Helpers
            "is_multi": len(selected_ids) > 1,
            "is_grid_child": is_grid_child,
        }
        return data
    return None

def get_viewport_data():
    results = []
    if not bpy.context or not bpy.context.scene: return results
    for elem in bpy.context.scene.rzm.elements:
        color_list = None
        if hasattr(elem, "color"):
            color_list = list(elem.color)
            if len(color_list) == 3: color_list.append(1.0)
        
        results.append({
            "id": elem.id, "name": elem.element_name, "class_type": elem.elem_class,
            "pos_x": elem.position[0], "pos_y": elem.position[1],
            "width": elem.size[0], "height": elem.size[1],
            "image_id": getattr(elem, "image_id", -1), "parent_id": getattr(elem, "parent_id", -1),
            "text_content": getattr(elem, "text_string", elem.element_name),
            "color": color_list, "is_hidden": getattr(elem, "qt_hide", False),
            "is_selectable": getattr(elem, "qt_selectable", True),
            "is_locked_pos": getattr(elem, "qt_lock_pos", False),
            "is_locked_size": getattr(elem, "qt_lock_size", False),
            "alignment": getattr(elem, "alignment", "BOTTOM_LEFT"),
            "grid_cell_size": getattr(elem, "grid_cell_size", 50),
        })
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
        results.append({
            'id': img.id,
            'name': img.display_name,
            'source_type': getattr(img, 'source_type', 'CUSTOM')
        })
    return results