# RZMenu/qt_editor/structure.py
import bpy
from . import signals
from . import blender_bridge
from ..conf import get_config

def get_next_available_id(elements):
    if len(elements) == 0: return 1
    return max(el.id for el in elements) + 1

def create_element(class_type, pos_x, pos_y, parent_id=-1):
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not bpy.context or not bpy.context.scene: return None
        rzm = bpy.context.scene.rzm
        elements = rzm.elements
        
        # --- LOAD DEFAULTS FROM CONFIG ---
        config = get_config()
        defaults = config.get("element_defaults", {}).get(class_type, {})
        
        new_id = get_next_available_id(elements)
        new_element = elements.add()
        new_element.id = new_id
        new_element.elem_class = class_type
        new_element.element_name = f"{class_type.capitalize()}_{new_id}"
        new_element.position = (int(pos_x), int(pos_y))
        
        # Apply Size
        width = defaults.get("width", 150)
        height = defaults.get("height", 100)
        new_element.size = (width, height)
        
        # Apply Color
        if "color" in defaults and hasattr(new_element, "color"):
             new_element.color = defaults["color"][:] # Copy list
        
        # Apply Text Align (if applicable)
        # Note: Need to check if your blender property is exactly 'text_align' or 'align'
        # Assuming defaults.py keys match blender property names roughly
        if "text_align" in defaults and hasattr(new_element, "text_align"):
             new_element.text_align = defaults["text_align"]

        # Apply specific Grid props if Grid
        if class_type == "GRID_CONTAINER":
            if "grid_cell_size" in defaults and hasattr(new_element, "grid_cell_size"):
                new_element.grid_cell_size = defaults["grid_cell_size"]
            if "grid_cols" in defaults and hasattr(new_element, "grid_cols"):
                new_element.grid_cols = defaults["grid_cols"]

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
    """
    Import image from filepath into RZMenu.
    Returns (image_id, image_name) if successful, else (None, None).
    """
    signals.IS_UPDATING_FROM_QT = True
    import os
    if not os.path.exists(filepath):
        print(f"Core: File not found: {filepath}")
        return None, None

    try:
        from . import read
        # Snapshot existing IDs to find the new one
        pre_images = {img['id'] for img in read.get_available_images()}
        
        # Execute operator
        if hasattr(bpy.ops.rzm, "add_image"):
            with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
                res = bpy.ops.rzm.add_image(filepath=filepath)
        else:
            print(f"Core: rzm.add_image operator not found. Path: {filepath}")
            return None, None
            
        if 'FINISHED' not in res:
             print("Core: Failed to add image operator.")
             return None, None

        # Find new ID
        post_images = read.get_available_images()
        new_img = None
        for img in post_images:
            if img['id'] not in pre_images:
                new_img = img
                break
        
        if new_img:
            signals.SIGNALS.structure_changed.emit()
            return new_img['id'], new_img['name']
            
    except Exception as e:
        print(f"Core: Failed to import image: {e}")
    finally:
        signals.IS_UPDATING_FROM_QT = False
    
    return None, None

def create_element_with_image(image_id, x, y):
    """Create a new element with an image at a specific position."""
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not bpy.context or not bpy.context.scene: return
        rzm = bpy.context.scene.rzm
        elements = rzm.elements
        images = rzm.images
        
        # --- LOAD DEFAULTS ---
        config = get_config()
        defaults = config.get("element_defaults", {}).get("CONTAINER", {})

        new_id = get_next_available_id(elements)
        new_element = elements.add()
        new_element.id = new_id
        new_element.elem_class = 'CONTAINER'
        
        # Apply Config Defaults First
        if "color" in defaults and hasattr(new_element, "color"):
             new_element.color = defaults["color"][:]
        if "text_align" in defaults and hasattr(new_element, "text_align"):
             new_element.text_align = defaults["text_align"]

        # Try to find image to get name and size
        img_meta = next((img for img in images if img.id == image_id), None)
        target_w, target_h = defaults.get("width", 100), defaults.get("height", 100) # Default from config or 100
        
        if img_meta:
            new_element.element_name = f"Img_{img_meta.display_name}_{new_id}"
            
            # If image pointer exists, try to get real size and Aspect Ratio
            if hasattr(img_meta, 'image_pointer') and img_meta.image_pointer:
                real_w, real_h = img_meta.image_pointer.size
                if real_w > 0 and real_h > 0:
                    # Scale to fit max size but keep aspect ratio
                    # We use the default width/height as the "box" to fit into
                    scale = min(target_w / real_w, target_h / real_h)
                    target_w, target_h = int(real_w * scale), int(real_h * scale)
            
            new_element.size = (target_w, target_h)
        else:
            new_element.element_name = f"Button_Img_{new_id}"
            new_element.size = (target_w, target_h)
            
        new_element.image_id = image_id
        new_element.position = (int(x), int(y))
        
        blender_bridge.safe_undo_push(f"RZM: Create Image Element")
        signals.SIGNALS.structure_changed.emit()
        signals.SIGNALS.transform_changed.emit()
        return new_id
    finally:
        signals.IS_UPDATING_FROM_QT = False
