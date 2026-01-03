# RZMenu/qt_editor/structure.py
import bpy
from . import signals
from . import blender_bridge

def get_next_available_id(elements):
    if len(elements) == 0: return 1
    return max(el.id for el in elements) + 1

def create_element(class_type, pos_x, pos_y, parent_id=-1):
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not bpy.context or not bpy.context.scene: return None
        rzm = bpy.context.scene.rzm
        elements = rzm.elements
        
        new_id = get_next_available_id(elements)
        new_element = elements.add()
        new_element.id = new_id
        new_element.elem_class = class_type
        new_element.element_name = f"{class_type.capitalize()}_{new_id}"
        new_element.position = (int(pos_x), int(pos_y))
        
        if class_type == 'BUTTON': new_element.size = (120, 30)
        elif class_type == 'TEXT': new_element.size = (100, 25)
        elif class_type == 'SLIDER': new_element.size = (150, 20)
        elif class_type == 'ANCHOR': new_element.size = (30, 30)
        else: new_element.size = (150, 100)
        
        if parent_id != -1: new_element.parent_id = parent_id
            
        blender_bridge.safe_undo_push(f"RZM: Create {class_type}")
        
        signals.SIGNALS.structure_changed.emit()
        signals.SIGNALS.transform_changed.emit()
        return new_id
    finally:
        signals.IS_UPDATING_FROM_QT = False

def delete_elements(target_ids):
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return
        elements = bpy.context.scene.rzm.elements
        to_del = [i for i, e in enumerate(elements) if e.id in target_ids]
        for idx in sorted(to_del, reverse=True):
            elements.remove(idx)
            
        blender_bridge.safe_undo_push("RZM: Delete Elements")
        signals.SIGNALS.structure_changed.emit()
        signals.SIGNALS.transform_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def reorder_elements(target_id, insert_after_id):
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not bpy.context or not bpy.context.scene: return
        elements = bpy.context.scene.rzm.elements
        
        target_idx = -1
        anchor_idx = -1
        for i, elem in enumerate(elements):
            if elem.id == target_id: target_idx = i
            if insert_after_id is not None and elem.id == insert_after_id: anchor_idx = i
        
        if target_idx == -1: return

        to_index = 0
        if insert_after_id is None: to_index = 0
        else:
            if anchor_idx == -1: return 
            if target_idx == anchor_idx: return
            to_index = anchor_idx if target_idx < anchor_idx else anchor_idx + 1 
        
        max_idx = len(elements) - 1
        if to_index > max_idx: to_index = max_idx
        
        if target_idx != to_index:
            elements.move(target_idx, to_index)
            blender_bridge.safe_undo_push("RZM: Reorder")
            signals.SIGNALS.structure_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def reparent_element(child_id, new_parent_id):
    signals.IS_UPDATING_FROM_QT = True
    try:
        elements = bpy.context.scene.rzm.elements
        target = next((e for e in elements if e.id == child_id), None)
        if target:
            target.parent_id = new_parent_id
            blender_bridge.safe_undo_push("RZM: Reparent")
            signals.SIGNALS.structure_changed.emit()
            signals.SIGNALS.transform_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def duplicate_elements(target_ids):
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return []
        elements = bpy.context.scene.rzm.elements
        sources = [e for e in elements if e.id in target_ids]
        if not sources: return []

        new_ids = []
        for src in sources:
            new_id = get_next_available_id(elements)
            new_elem = elements.add()
            new_elem.id = new_id
            new_elem.element_name = src.element_name + "_copy"
            new_elem.elem_class = src.elem_class
            new_elem.position = (src.position[0] + 20, src.position[1] - 20) 
            new_elem.size = src.size[:]
            new_elem.parent_id = src.parent_id 
            
            if hasattr(src, "qt_hide"): new_elem.qt_hide = src.qt_hide
            if hasattr(src, "qt_locked"): new_elem.qt_locked = src.qt_locked
            if hasattr(src, "color"): new_elem.color = src.color[:]
            new_ids.append(new_id)

        blender_bridge.safe_undo_push("RZM: Duplicate")
        signals.SIGNALS.structure_changed.emit()
        signals.SIGNALS.transform_changed.emit()
        return new_ids
    finally:
        signals.IS_UPDATING_FROM_QT = False

def commit_history(msg):
    blender_bridge.safe_undo_push(msg)

def import_image_from_path(filepath):
    """Import image into Blender scene.rzm.images."""
    signals.IS_UPDATING_FROM_QT = True
    try:
        # Assuming RZMenu has an operator to add images
        if hasattr(bpy.ops.rzm, "add_image"):
            bpy.ops.rzm.add_image(filepath=filepath)
        else:
            print(f"Core: rzm.add_image operator not found. Path: {filepath}")
            
        signals.SIGNALS.structure_changed.emit()
    except Exception as e:
        print(f"Core: Failed to import image: {e}")
    finally:
        signals.IS_UPDATING_FROM_QT = False

def create_element_with_image(image_id, x, y):
    """Create a new element with an image at a specific position."""
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not bpy.context or not bpy.context.scene: return
        rzm = bpy.context.scene.rzm
        elements = rzm.elements
        images = rzm.images
        
        new_id = get_next_available_id(elements)
        new_element = elements.add()
        new_element.id = new_id
        new_element.elem_class = 'BUTTON'
        
        # Try to find image to get name and size
        img_meta = next((img for img in images if img.id == image_id), None)
        if img_meta:
            new_element.element_name = f"Img_{img_meta.display_name}_{new_id}"
            
            # Default size
            w, h = 100, 100
            
            # If image pointer exists, try to get real size
            if hasattr(img_meta, 'image_pointer') and img_meta.image_pointer:
                real_w, real_h = img_meta.image_pointer.size
                if real_w > 0 and real_h > 0:
                    # Scale to fit max 100x100 but keep aspect ratio
                    scale = min(100 / real_w, 100 / real_h)
                    w, h = int(real_w * scale), int(real_h * scale)
            
            new_element.size = (w, h)
        else:
            new_element.element_name = f"Button_Img_{new_id}"
            new_element.size = (100, 100)
            
        new_element.image_id = image_id
        new_element.position = (int(x), int(y))
        
        blender_bridge.safe_undo_push(f"RZM: Create Image Element")
        signals.SIGNALS.structure_changed.emit()
        signals.SIGNALS.transform_changed.emit()
        return new_id
    finally:
        signals.IS_UPDATING_FROM_QT = False
