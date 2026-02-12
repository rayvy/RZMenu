# RZMenu/qt_editor/clipboard.py
import bpy
from . import structure
from . import signals
from . import blender_bridge

_INTERNAL_CLIPBOARD = []

def copy_elements(target_ids):
    global _INTERNAL_CLIPBOARD
    _INTERNAL_CLIPBOARD.clear()
    
    if not target_ids: return
    if not bpy.context or not bpy.context.scene: return
    elements = bpy.context.scene.rzm.elements
    
    for elem in elements:
        if elem.id in target_ids:
            data = {
                "name": elem.element_name,
                "class": elem.elem_class,
                "pos": list(elem.position),
                "size": list(elem.size),
                "color": list(elem.color) if hasattr(elem, "color") else [1,1,1,1],
                "alignment": elem.alignment,
                "text_align": elem.text_align,
                "text_id": elem.text_id,
                "hover_text_id": elem.hover_text_id,
                "tag": elem.tag,
                "priority": elem.priority,
                "is_main_window": elem.is_main_window,
                
                "pos_is_formula": elem.position_is_formula,
                "size_is_formula": elem.size_is_formula,
                "pos_formula_x": elem.position_formula_x,
                "pos_formula_y": elem.position_formula_y,
                "size_formula_x": elem.size_formula_x,
                "size_formula_y": elem.size_formula_y,
                
                "image_id": elem.image_id,
                "image_mode": elem.image_mode,
                "tile_uv": list(elem.tile_uv),
                "tile_size": list(elem.tile_size),
                
                "visibility_mode": elem.visibility_mode,
                "visibility_condition": elem.visibility_condition,
                "hide": getattr(elem, "qt_hide", False),
                "lock_pos": getattr(elem, "qt_lock_pos", False),
                "lock_size": getattr(elem, "qt_lock_size", False),
                "selectable": getattr(elem, "qt_selectable", True),
                
                "grid_cell_size": elem.grid_cell_size,
                "grid_min_cells": list(elem.grid_min_cells),
                "grid_max_cells": list(elem.grid_max_cells),
                "grid_wrap_mode": elem.grid_wrap_mode,
                
                "disable_button_nums": elem.disable_button_nums,
                "disable_button_popup": elem.disable_button_popup,
                
                "conditional_images": [{"condition": ci.condition, "image_id": ci.image_id} for ci in elem.conditional_images],
                "value_links": [{"name": vl.value_name, "min": vl.value_min, "max": vl.value_max} for vl in elem.value_link],
                "fx": [fx.value for fx in elem.fx]
            }
            _INTERNAL_CLIPBOARD.append(data)

def paste_elements(target_x=None, target_y=None):
    global _INTERNAL_CLIPBOARD
    if not _INTERNAL_CLIPBOARD: return []
    
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not bpy.context or not bpy.context.scene: return []
        elements = bpy.context.scene.rzm.elements
        new_ids = []

        offset_x = 0
        offset_y = 0
        
        if target_x is not None and target_y is not None:
            min_x = min(item["pos"][0] for item in _INTERNAL_CLIPBOARD)
            min_y = min(item["pos"][1] for item in _INTERNAL_CLIPBOARD)
            offset_x = target_x - min_x
            offset_y = target_y - min_y
        else:
            offset_x = 20
            offset_y = -20

        for item in _INTERNAL_CLIPBOARD:
            new_id = structure.get_next_available_id(elements)
            new_elem = elements.add()
            new_elem.id = new_id
            new_elem.element_name = item["name"] + "_copy"
            new_elem.elem_class = item["class"]
            
            px = int(item["pos"][0] + offset_x)
            py = int(item["pos"][1] + offset_y)
            
            new_elem.position = (px, py)
            new_elem.size = item["size"]
            new_elem.parent_id = -1 
            
            # Simple Props
            new_elem.color = item.get("color", [1,1,1,1])
            new_elem.alignment = item.get("alignment", "BOTTOM_LEFT")
            new_elem.text_align = item.get("text_align", "LEFT")
            new_elem.text_id = item.get("text_id", "")
            new_elem.hover_text_id = item.get("hover_text_id", "")
            new_elem.tag = item.get("tag", "")
            new_elem.priority = item.get("priority", 0)
            new_elem.is_main_window = item.get("is_main_window", False)
            
            new_elem.position_is_formula = item.get("pos_is_formula", False)
            new_elem.size_is_formula = item.get("size_is_formula", False)
            new_elem.position_formula_x = item.get("pos_formula_x", "")
            new_elem.position_formula_y = item.get("pos_formula_y", "")
            new_elem.size_formula_x = item.get("size_formula_x", "")
            new_elem.size_formula_y = item.get("size_formula_y", "")
            
            new_elem.image_id = item.get("image_id", -1)
            new_elem.image_mode = item.get("image_mode", "SINGLE")
            new_elem.tile_uv = item.get("tile_uv", [0,0])
            new_elem.tile_size = item.get("tile_size", [1,1])
            
            new_elem.visibility_mode = item.get("visibility_mode", "ALWAYS")
            new_elem.visibility_condition = item.get("visibility_condition", "")
            new_elem.qt_hide = item.get("hide", False)
            new_elem.qt_lock_pos = item.get("lock_pos", False)
            new_elem.qt_lock_size = item.get("lock_size", False)
            new_elem.qt_selectable = item.get("selectable", True)
            
            new_elem.grid_cell_size = item.get("grid_cell_size", 50)
            new_elem.grid_min_cells = item.get("grid_min_cells", [1,1])
            new_elem.grid_max_cells = item.get("grid_max_cells", [1,1])
            new_elem.grid_wrap_mode = item.get("grid_wrap_mode", "SCROLL")
            
            new_elem.disable_button_nums = item.get("disable_button_nums", False)
            new_elem.disable_button_popup = item.get("disable_button_popup", False)

            # Collections
            for ci in item.get("conditional_images", []):
                new_ci = new_elem.conditional_images.add()
                new_ci.condition = ci["condition"]
                new_ci.image_id = ci["image_id"]
                
            for vl in item.get("value_links", []):
                new_vl = new_elem.value_link.add()
                new_vl.value_name = vl["name"]
                new_vl.value_min = vl["min"]
                new_vl.value_max = vl["max"]
                
            for fx_val in item.get("fx", []):
                new_fx = new_elem.fx.add()
                new_fx.value = fx_val
            
            new_ids.append(new_id)
            
        blender_bridge.safe_undo_push("RZM: Paste")
        signals.SIGNALS.structure_changed.emit()
        signals.SIGNALS.transform_changed.emit()
        return new_ids

    finally:
        signals.IS_UPDATING_FROM_QT = False