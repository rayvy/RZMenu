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
                "hide": getattr(elem, "qt_hide", False),
                "lock": getattr(elem, "qt_locked", False),
                "grid_cell": getattr(elem, "grid_cell_size", 20)
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
            offset_x = 5
            offset_y = 5

        for item in _INTERNAL_CLIPBOARD:
            new_id = structure.get_next_available_id(elements)
            new_elem = elements.add()
            new_elem.id = new_id
            new_elem.element_name = item["name"]
            new_elem.elem_class = item["class"]
            
            px = int(item["pos"][0] + offset_x)
            py = int(item["pos"][1] + offset_y)
            
            new_elem.position = (px, py)
            new_elem.size = item["size"]
            new_elem.parent_id = -1 
            
            if "color" in item: new_elem.color = item["color"]
            if "hide" in item: new_elem.qt_hide = item["hide"]
            if "lock" in item: new_elem.qt_locked = item["lock"]
            if "grid_cell" in item and hasattr(new_elem, "grid_cell_size"):
                 new_elem.grid_cell_size = item["grid_cell"]
            
            new_ids.append(new_id)
            
        blender_bridge.safe_undo_push("RZM: Paste")
        signals.SIGNALS.structure_changed.emit()
        signals.SIGNALS.transform_changed.emit()
        return new_ids

    finally:
        signals.IS_UPDATING_FROM_QT = False