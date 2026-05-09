# RZMenu/qt_editor/structure.py
import bpy
from . import signals
from . import blender_bridge
from .maths import get_global_pos, get_local_pos_from_global
from ..conf import get_config

def get_next_available_id(elements):
    ids = {el.id for el in elements}
    new_id = 1
    while new_id in ids:
        new_id += 1
    return new_id

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
        
        # --- PARENTING & COORDINATES ---
        if parent_id != -1:
            new_element.parent_id = parent_id
            # Convert global pos_x, pos_y to local
            elem_map = {e.id: e for e in elements}
            lx, ly = get_local_pos_from_global(pos_x, pos_y, parent_id, elem_map)
            new_element.position = (int(lx), int(ly))
        else:
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

def reorder_elements(target_id, insert_after_id, silent=False):
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
            if not silent:
                blender_bridge.safe_undo_push("RZM: Reorder")
                signals.SIGNALS.structure_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def reparent_element(child_id, new_parent_id, silent=False):
    signals.IS_UPDATING_FROM_QT = True
    try:
        elements = bpy.context.scene.rzm.elements
        elem_map = {e.id: e for e in elements}
        
        target = elem_map.get(child_id)
        if target:
            # 1. Get Current Global Position
            curr_gx, curr_gy = get_global_pos(target, elem_map)
            
            # 2. Assign New Parent
            target.parent_id = new_parent_id
            
            # 3. Calculate Required Local Position to maintain Global Pos
            new_local_x, new_local_y = get_local_pos_from_global(curr_gx, curr_gy, new_parent_id, elem_map)
            
            # 4. Apply
            target.position[0] = int(new_local_x)
            target.position[1] = int(new_local_y)
            
            blender_bridge.safe_undo_push("RZM: Reparent")
            
            if not silent:
                signals.SIGNALS.structure_changed.emit()
                signals.SIGNALS.transform_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def duplicate_elements(target_ids, offset=20):
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
            
            # Position/Size
            # If offset is 0, it's a 1:1 duplicate
            new_elem.position = (src.position[0] + offset, src.position[1] - offset) 
            new_elem.size = src.size[:]
            new_elem.parent_id = src.parent_id
            
            # Formula Logic
            new_elem.position_is_formula = src.position_is_formula
            new_elem.size_is_formula = src.size_is_formula
            new_elem.position_formula_x = src.position_formula_x
            new_elem.position_formula_y = src.position_formula_y
            new_elem.size_formula_x = src.size_formula_x
            new_elem.size_formula_y = src.size_formula_y
            
            # Visuals & Identity
            new_elem.alignment = src.alignment
            new_elem.text_align = src.text_align
            new_elem.text_id = src.text_id
            new_elem.hover_text_id = src.hover_text_id
            new_elem.tag = src.tag
            new_elem.priority = src.priority
            new_elem.is_main_window = src.is_main_window
            
            # Appearance
            if hasattr(src, "color"): new_elem.color = src.color[:]
            new_elem.image_id = src.image_id
            new_elem.image_mode = src.image_mode
            new_elem.image_blending_mode = getattr(src, "image_blending_mode", 'NONE')
            new_elem.tile_uv = src.tile_uv[:]
            new_elem.tile_size = src.tile_size[:]
            
            # Additional Formula Logic
            new_elem.color_is_formula = src.color_is_formula
            new_elem.color_formula_r = src.color_formula_r
            new_elem.color_formula_g = src.color_formula_g
            new_elem.color_formula_b = src.color_formula_b
            new_elem.color_formula_a = src.color_formula_a
            
            new_elem.value_link_is_formula = src.value_link_is_formula
            new_elem.value_link_formula = src.value_link_formula
            
            new_elem.transform_is_formula = getattr(src, "transform_is_formula", False)
            new_elem.transform_formula = getattr(src, "transform_formula", "")
            
            # Preset Specifics
            new_elem.is_preset = getattr(src, "is_preset", False)
            new_elem.qt_preset_hide = getattr(src, "qt_preset_hide", False)
            
            # Visibility & State
            new_elem.visibility_mode = src.visibility_mode
            new_elem.visibility_condition = src.visibility_condition
            new_elem.qt_hide = getattr(src, "qt_hide", False)
            new_elem.qt_lock_pos = getattr(src, "qt_lock_pos", False)
            new_elem.qt_lock_size = getattr(src, "qt_lock_size", False)
            new_elem.qt_selectable = getattr(src, "qt_selectable", True)
            
            # Grid Specifics
            new_elem.grid_cell_size = src.grid_cell_size
            new_elem.grid_min_cells = src.grid_min_cells[:]
            new_elem.grid_max_cells = src.grid_max_cells[:]
            new_elem.grid_wrap_mode = src.grid_wrap_mode
            
            # Button Specifics
            new_elem.disable_button_nums = src.disable_button_nums
            new_elem.disable_button_popup = src.disable_button_popup
            new_elem.disable_slider_nums = getattr(src, "disable_slider_nums", False)
            new_elem.disable_slider_blur = getattr(src, "disable_slider_blur", False)
            new_elem.disable_slider_prebuild_render = getattr(src, "disable_slider_prebuild_render", False)
            
            # Events
            new_elem.hover_event_enabled = src.hover_event_enabled
            new_elem.hover_event_formula = src.hover_event_formula
            new_elem.click_event_enabled = src.click_event_enabled
            new_elem.click_event_formula = src.click_event_formula
            new_elem.hold_event_enabled = src.hold_event_enabled
            new_elem.hold_event_formula = src.hold_event_formula
            
            # Copy Collections
            if hasattr(src, "preset_ids"):
                for p in src.preset_ids:
                    new_p = new_elem.preset_ids.add()
                    new_p.preset_id = p.preset_id

            if hasattr(src, "underlayer_preset_ids"):
                for p in src.underlayer_preset_ids:
                    new_p = new_elem.underlayer_preset_ids.add()
                    new_p.preset_id = p.preset_id


            for ci in src.conditional_images:
                new_ci = new_elem.conditional_images.add()
                new_ci.condition = ci.condition
                new_ci.image_id = ci.image_id
                
            for vl in src.value_link:
                new_vl = new_elem.value_link.add()
                new_vl.value_name = vl.value_name
                new_vl.value_min = vl.value_min
                new_vl.value_max = vl.value_max
                
            for fx_item in src.fx:
                new_fx = new_elem.fx.add()
                new_fx.value = fx_item.value

            new_elem.text_mode = src.text_mode
            for ct in src.conditional_texts:
                new_ct = new_elem.conditional_texts.add()
                new_ct.condition = ct.condition
                new_ct.text_id = ct.text_id

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
        
        # Choose the right operator based on file extension
        ext = os.path.splitext(filepath)[1].lower()
        if ext in ['.gif', '.mp4', '.webm', '.avi']:
            op_name = "add_animated_image"
        else:
            op_name = "add_image"
            
        if hasattr(bpy.ops.rzm, op_name):
            with bpy.context.temp_override(window=bpy.context.window_manager.windows[0]):
                op_callable = getattr(bpy.ops.rzm, op_name)
                res = op_callable(filepath=filepath)
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
