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
    target = next((e for e in elements if e.id == active_id), None)
    
    if not target and selected_ids:
        first_id = list(selected_ids)[0]
        target = next((e for e in elements if e.id == first_id), None)

    if target:
        color_vals = [1.0, 1.0, 1.0, 1.0]
        if hasattr(target, "color"):
            color_vals = list(target.color)
            if len(color_vals) == 3: color_vals.append(1.0)

        data = {
            "exists": True, "id": target.id, "active_id": active_id,
            "selected_ids": list(selected_ids), "name": target.element_name,
            "class_type": target.elem_class, "pos_x": target.position[0],
            "pos_y": target.position[1], "width": target.size[0],
            "height": target.size[1], "image_id": getattr(target, "image_id", -1),
            "color": color_vals, "is_hidden": getattr(target, "qt_hide", False),
            "is_locked": getattr(target, "qt_locked", False),
            "is_multi": len(selected_ids) > 1,
            "grid_cell_size": getattr(target, "grid_cell_size", 20),
            "grid_rows": getattr(target, "grid_rows", 2),
            "grid_cols": getattr(target, "grid_cols", 2),
            "grid_gap": getattr(target, "grid_gap", 5),
            "grid_padding": getattr(target, "grid_padding", 5)
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
            "is_locked": getattr(elem, "qt_locked", False)
        })
    return results

# Stubs for legacy calls
def get_structure_signature(): return 0
def get_element_signature(active_id): return 0
def get_viewport_signature(): return 0
def get_scene_info(): return {"count": 0, "name": ""}
def get_active_object_safe(): return None
def get_selected_objects_safe(): return []