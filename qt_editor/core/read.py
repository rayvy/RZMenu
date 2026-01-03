# RZMenu/qt_editor/read.py
import bpy

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

def get_selection_details(selected_ids, active_id):
    if not bpy.context or not bpy.context.scene: return None
    elements = bpy.context.scene.rzm.elements
    selection = [e for e in elements if e.id in selected_ids]
    
    # Reference element for active values
    target = next((e for e in elements if e.id == active_id), None)
    if not target and selection:
        target = selection[0]

    if target:
        # Helper to get "mixed" status: returns value if uniform, else None
        def get_uniform(prop_name, sub_idx=None):
            if not selection: return None
            vals = []
            for e in selection:
                if not hasattr(e, prop_name): continue
                raw = getattr(e, prop_name)
                val = raw[sub_idx] if sub_idx is not None else raw
                # Handle special types like color
                if prop_name == "color": val = tuple(val)
                vals.append(val)
            
            if not vals: return None
            return vals[0] if all(v == vals[0] for v in vals) else None

        color_uniform = get_uniform("color")
        color_vals = list(color_uniform) if color_uniform else [1.0, 1.0, 1.0, 1.0]
        if len(color_vals) == 3: color_vals.append(1.0)

        data = {
            "exists": True, "id": target.id, "active_id": active_id,
            "selected_ids": list(selected_ids), "name": target.element_name if len(selection) <= 1 else "Multiple Elements",
            "class_type": get_uniform("elem_class"), 
            "pos_x": get_uniform("position", 0),
            "pos_y": get_uniform("position", 1), 
            "width": get_uniform("size", 0),
            "height": get_uniform("size", 1), 
            "image_id": get_uniform("image_id"),
            "color": color_vals, 
            "is_hidden": get_uniform("qt_hide"),
            "is_locked_pos": get_uniform("qt_lock_pos"),
            "is_locked_size": get_uniform("qt_lock_size"),
            "alignment": get_uniform("alignment"),
            "text_align": get_uniform("text_align"),
            "is_multi": len(selected_ids) > 1,
            "grid_cell_size": get_uniform("grid_cell_size"),
            "grid_rows": get_uniform("grid_rows"),
            "grid_cols": get_uniform("grid_cols"),
            "grid_gap": get_uniform("grid_gap"),
            "grid_padding": get_uniform("grid_padding")
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
            "alignment": getattr(elem, "alignment", "BOTTOM_LEFT")
        })
    return results

# Stubs for legacy calls
def get_structure_signature(): return 0
def get_element_signature(active_id): return 0
def get_viewport_signature(): return 0
def get_scene_info(): return {"count": 0, "name": ""}
def get_active_object_safe(): return None
def get_selected_objects_safe(): return []