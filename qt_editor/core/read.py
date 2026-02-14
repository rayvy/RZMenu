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
    Includes element names ($), rzm_values ($), toggles (@), and shapes (#).
    """
    suggestions = []
    if not bpy.context or not bpy.context.scene: return suggestions
    
    rzm = bpy.context.scene.rzm

    # 1. Elements (Standard Position/Size variables)
    for elem in rzm.elements:
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
            "color_is_formula": get_uniform("color_is_formula", default=False),
            "color_formula_r": get_uniform("color_formula_r", default="1"),
            "color_formula_g": get_uniform("color_formula_g", default="1"),
            "color_formula_b": get_uniform("color_formula_b", default="1"),
            "color_formula_a": get_uniform("color_formula_a", default="1"),
            "text_id": get_uniform("text_id", default=""),
            "hover_text_id": get_uniform("hover_text_id", default=""),
            
            # Images
            "image_mode": get_uniform("image_mode", default="SINGLE"),
            "image_id": get_uniform("image_id", default=-1),
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
                    "value_min": vl.value_min,
                    "value_max": vl.value_max
                }
                for vl in target.value_link
            ] if target else [],
            
            "fx": [
                item.value for item in target.fx
            ] if target else [],

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
            
            # Presets
            "is_preset": get_uniform("is_preset", default=False),
            "qt_preset_hide": get_uniform("qt_preset_hide", default=False),
            "preset_ids": [
                p.preset_id for p in target.preset_ids
            ] if target and hasattr(target, "preset_ids") else [],
        }
        return data
    return None

def get_viewport_data():
    results = []
    if not bpy.context or not bpy.context.scene: return results

    for idx, elem in enumerate(bpy.context.scene.rzm.elements):
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

            # Formula flags
            "pos_is_formula": getattr(elem, "position_is_formula", False),
            "size_is_formula": getattr(elem, "size_is_formula", False),

            # Formula strings (Important: sanitize/default to empty string)
            "formula_x": getattr(elem, "position_formula_x", ""),
            "formula_y": getattr(elem, "position_formula_y", ""),
            "formula_w": getattr(elem, "size_formula_x", ""),
            "formula_h": getattr(elem, "size_formula_y", ""),

            # Visuals
            "image_id": getattr(elem, "image_id", -1),
            "text_id": getattr(elem, "text_id", ""),
            "color": color_list,
            "is_hidden": getattr(elem, "qt_hide", False),
            "is_selectable": getattr(elem, "qt_selectable", True),
            "is_locked_pos": getattr(elem, "qt_lock_pos", False),
            "is_locked_size": getattr(elem, "qt_lock_size", False),
            "alignment": getattr(elem, "alignment", "BOTTOM_LEFT"),

            # Formula Logic (Color / Logic)
            "color_is_formula": getattr(elem, "color_is_formula", False),
            "color_formula_r": getattr(elem, "color_formula_r", "1"),
            "color_formula_g": getattr(elem, "color_formula_g", "1"),
            "color_formula_b": getattr(elem, "color_formula_b", "1"),
            "color_formula_a": getattr(elem, "color_formula_a", "1"),
            "value_link_is_formula": getattr(elem, "value_link_is_formula", False),
            "value_link_formula": getattr(elem, "value_link_formula", ""),

            "qt_preset_hide": getattr(elem, "qt_preset_hide", False),
            
            # Grid props
            "grid_cell_size": getattr(elem, "grid_cell_size", 50),
            "grid_cols": getattr(elem, "grid_min_cells", [1,1])[0]
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
        
        # Iterate presets assigned to this element
        for p_ref in host_elem.preset_ids:
            preset_id = p_ref.preset_id
            preset_source = elem_map.get(preset_id)
            
            if not preset_source: continue # Preset source deleted or missing
            
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
            v_item['is_locked_pos'] = True
            v_item['is_locked_size'] = True
            
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
        results.append({
            'id': img.id,
            'name': img.display_name,
            'source_type': getattr(img, 'source_type', 'CUSTOM')
        })
    return results