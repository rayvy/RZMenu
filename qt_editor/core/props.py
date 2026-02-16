import bpy
from . import signals
from . import blender_bridge

# Centralized property mapping to reduce duplication (DRY)
# Format: "qt_prop_name": ("blender_prop_meta", sub_index, signal_type)
# signals: 'T' for transform, 'S' for structure, 'D' for data (always sent)
PROP_MAP = {
    # Geometry
    "pos_x": ("position", 0, 'T'),
    "pos_y": ("position", 1, 'T'),
    "width": ("size", 0, 'T'),
    "height": ("size", 1, 'T'),
    "alignment": ("alignment", None, 'D'),
    
    # Formulas
    "position_is_formula": ("position_is_formula", None, 'T'),
    "size_is_formula": ("size_is_formula", None, 'T'),
    "position_formula_x": ("position_formula_x", None, 'T'),
    "position_formula_y": ("position_formula_y", None, 'T'),
    "size_formula_x": ("size_formula_x", None, 'T'),
    "size_formula_y": ("size_formula_y", None, 'T'),
    "transform_is_formula": ("transform_is_formula", None, 'T'),
    "transform_formula": ("transform_formula", None, 'T'),

    # Presets
    "is_preset": ("is_preset", None, 'T'),
    "qt_preset_hide": ("qt_preset_hide", None, 'T'),
    # Flags
    "qt_hide": ("qt_hide", None, 'S'),
    "is_hidden": ("qt_hide", None, 'S'), # Alias
    "qt_lock_pos": ("qt_lock_pos", None, 'S'),
    "is_locked_pos": ("qt_lock_pos", None, 'S'), # Alias
    "qt_lock_size": ("qt_lock_size", None, 'S'),
    "is_locked_size": ("qt_lock_size", None, 'S'), # Alias
    
    "qt_selectable": ("qt_selectable", None, 'D'),
    "is_selectable": ("qt_selectable", None, 'D'), # Alias

    # Grid
    "grid_rows": ("grid_rows", None, 'D'),
    "grid_cols": ("grid_cols", None, 'D'),
    "grid_gap": ("grid_gap", None, 'D'),
    "grid_padding": ("grid_padding", None, 'D'),
    "grid_cell_size": ("grid_cell_size", None, 'D'),
    "grid_min_cells": ("grid_min_cells", None, 'D'),
    "grid_max_cells": ("grid_max_cells", None, 'D'),
    "grid_wrap_mode": ("grid_wrap_mode", None, 'D'),
    
    # Appearance & Content
    "element_name": ("element_name", None, 'S'),
    "color": ("color", None, 'D'),
    "tag": ("tag", None, 'D'),
    "priority": ("priority", None, 'D'),
    "is_main_window": ("is_main_window", None, 'D'),
    "visibility_mode": ("visibility_mode", None, 'D'),
    "visibility_condition": ("visibility_condition", None, 'D'),
    "text_id": ("text_id", None, 'D'),
    "hover_text_id": ("hover_text_id", None, 'D'),
    "text_align": ("text_align", None, 'D'),
    "image_id": ("image_id", None, 'D'),
    "image_mode": ("image_mode", None, 'D'),
    "image_blending_mode": ("image_blending_mode", None, 'D'),
    "tile_uv": ("tile_uv", None, 'D'),
    "tile_size": ("tile_size", None, 'D'),
    "disable_button_nums": ("disable_button_nums", None, 'D'),
    "disable_button_popup": ("disable_button_popup", None, 'D'),
    "text_mode": ("text_mode", None, 'D'),
    
    # Events
    "hover_event_enabled": ("hover_event_enabled", None, 'D'),
    "hover_event_formula": ("hover_event_formula", None, 'D'),
    "click_event_enabled": ("click_event_enabled", None, 'D'),
    "click_event_formula": ("click_event_formula", None, 'D'),

    # Color Formula
    "color_is_formula": ("color_is_formula", None, 'D'),
    "color_formula_r": ("color_formula_r", None, 'D'),
    "color_formula_g": ("color_formula_g", None, 'D'),
    "color_formula_b": ("color_formula_b", None, 'D'),
    "color_formula_a": ("color_formula_a", None, 'D'),

    # Value Link Formula
    "value_link_is_formula": ("value_link_is_formula", None, 'D'),
    "value_link_formula": ("value_link_formula", None, 'D'),
    "class_type": ("elem_class", None, 'S'),
}

from ..utils import logger

def update_property_multi(target_ids, prop_name, value, sub_index=None, fast_mode=False):
    if not target_ids: return
    
    # Resolve Mapping
    mapping = PROP_MAP.get(prop_name)
    if mapping is None:
        logger.warn(f"Property '{prop_name}' not found in PROP_MAP, skipping update")
        return

    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        targets = [e for e in elements if e.id in target_ids]
        if not targets: return

        bl_prop = mapping[0]
        bl_idx = mapping[1] if mapping[1] is not None else sub_index
        sig_type = mapping[2] 

        changed = False
        for elem in targets:
            if not hasattr(elem, bl_prop):
                continue
            
            raw_val = getattr(elem, bl_prop)
            
            # Type-specific handling
            if bl_prop == "color":
                try: 
                    setattr(elem, bl_prop, value[:len(raw_val)])
                    changed = True
                except: pass
            elif bl_idx is not None:
                if raw_val[bl_idx] != value:
                    raw_val[bl_idx] = value
                    setattr(elem, bl_prop, raw_val)
                    changed = True
            else:
                if raw_val != value:
                    setattr(elem, bl_prop, value)
                    changed = True

        if changed:
            if not fast_mode: 
                blender_bridge.safe_undo_push(f"RZM: Change {prop_name}")
            
            # Emit Signals based on type
            signals.SIGNALS.data_changed.emit()
            if sig_type == 'T':
                signals.SIGNALS.transform_changed.emit()
            elif sig_type == 'S':
                signals.SIGNALS.structure_changed.emit()
                signals.SIGNALS.transform_changed.emit() # Often needed too

def toggle_editor_flag(target_ids, flag_name):
    """Simplified toggle using centralized mapping."""
    if not target_ids: return
    mapping = PROP_MAP.get(flag_name)
    if not mapping: return
    
    bl_prop = mapping[0]
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids:
                curr = getattr(elem, bl_prop, False)
                setattr(elem, bl_prop, not curr)
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push(f"RZM: Toggle {flag_name}")
            signals.SIGNALS.data_changed.emit()
            signals.SIGNALS.structure_changed.emit()
            signals.SIGNALS.transform_changed.emit()

def add_conditional_image(target_ids):
    if not target_ids: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids:
                elem.conditional_images.add()
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Add Conditional Image")
            signals.SIGNALS.data_changed.emit()

def remove_conditional_image(target_ids, index):
    if not target_ids or index < 0: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and index < len(elem.conditional_images):
                elem.conditional_images.remove(index)
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Remove Conditional Image")
            signals.SIGNALS.data_changed.emit()

def update_conditional_image(target_ids, index, field, value):
    if not target_ids or index < 0: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and index < len(elem.conditional_images):
                item = elem.conditional_images[index]
                if hasattr(item, field):
                    curr = getattr(item, field)
                    if curr != value:
                        setattr(item, field, value)
                        changed = True
        
        if changed:
            # We don't always want undo push for every keystroke if it's text
            # But for simplicity here we do it.
            blender_bridge.safe_undo_push(f"RZM: Update CI {field}")
            signals.SIGNALS.data_changed.emit()

def add_conditional_text(target_ids):
    if not target_ids: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids:
                elem.conditional_texts.add()
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Add Conditional Text")
            signals.SIGNALS.data_changed.emit()

def remove_conditional_text(target_ids, index):
    if not target_ids or index < 0: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and index < len(elem.conditional_texts):
                elem.conditional_texts.remove(index)
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Remove Conditional Text")
            signals.SIGNALS.data_changed.emit()

def update_conditional_text(target_ids, index, field, value):
    if not target_ids or index < 0: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and index < len(elem.conditional_texts):
                item = elem.conditional_texts[index]
                if hasattr(item, field):
                    curr = getattr(item, field)
                    if curr != value:
                        setattr(item, field, value)
                        changed = True
        
        if changed:
            blender_bridge.safe_undo_push(f"RZM: Update CT {field}")
            signals.SIGNALS.data_changed.emit()

def add_value_link(target_ids):
    if not target_ids: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids:
                elem.value_link.add()
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Add Value Link")
            signals.SIGNALS.data_changed.emit()

def remove_value_link(target_ids, index):
    if not target_ids or index < 0: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and index < len(elem.value_link):
                elem.value_link.remove(index)
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Remove Value Link")
            signals.SIGNALS.data_changed.emit()

def update_value_link(target_ids, index, field, value):
    if not target_ids or index < 0: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and index < len(elem.value_link):
                item = elem.value_link[index]
                if hasattr(item, field):
                    curr = getattr(item, field)
                    if curr != value:
                        setattr(item, field, value)
                        changed = True
        
        if changed:
            blender_bridge.safe_undo_push(f"RZM: Update VL {field}")
            signals.SIGNALS.data_changed.emit()

def add_fx(target_ids):
    if not target_ids: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids:
                elem.fx.add()
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Add FX")
            signals.SIGNALS.data_changed.emit()

def remove_fx(target_ids, index):
    if not target_ids or index < 0: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and index < len(elem.fx):
                elem.fx.remove(index)
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Remove FX")
            signals.SIGNALS.data_changed.emit()

def update_fx(target_ids, index, value):
    if not target_ids or index < 0: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and index < len(elem.fx):
                item = elem.fx[index]
                if item.value != value:
                    item.value = value
                    changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Update FX")
            signals.SIGNALS.data_changed.emit()

def add_preset_id(target_ids, preset_id):
    if not target_ids: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and hasattr(elem, "preset_ids"):
                # Check if already exists
                exists = False
                for p in elem.preset_ids:
                    if p.preset_id == preset_id:
                        exists = True
                        break
                if not exists:
                    new_p = elem.preset_ids.add()
                    new_p.preset_id = preset_id
                    changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Add Preset")
            signals.SIGNALS.data_changed.emit()

def remove_preset_id(target_ids, index):
    if not target_ids or index < 0: return
    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and hasattr(elem, "preset_ids") and index < len(elem.preset_ids):
                elem.preset_ids.remove(index)
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Remove Preset")
            signals.SIGNALS.data_changed.emit()

def perform_math_operation(target_ids, prop_name, op_str, sub_index=None):
    if not target_ids: return

    mapping = PROP_MAP.get(prop_name)
    bl_prop = mapping[0] if mapping else prop_name
    bl_idx = mapping[1] if mapping and mapping[1] is not None else sub_index
    
    op = op_str[:2]
    try: val = float(op_str[2:])
    except ValueError: return

    with signals.qt_update_guard():
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids and hasattr(elem, bl_prop):
                current_obj = getattr(elem, bl_prop)
                try:
                    curr_val = current_obj[bl_idx] if bl_idx is not None else float(current_obj)
                except: continue

                if op == "+=": new_val = curr_val + val
                elif op == "-=": new_val = curr_val - val
                elif op == "*=": new_val = curr_val * val
                elif op == "/=": new_val = curr_val / val if val != 0 else curr_val
                else: continue

                if bl_idx is not None:
                    current_obj[bl_idx] = int(new_val) if isinstance(curr_val, int) else new_val
                    setattr(elem, bl_prop, current_obj)
                else:
                    setattr(elem, bl_prop, int(new_val) if isinstance(current_obj, int) else new_val)
                changed = True

        if changed:
            blender_bridge.safe_undo_push(f"RZM: Math {op_str} on {prop_name}")
            signals.SIGNALS.transform_changed.emit()
            signals.SIGNALS.data_changed.emit()

def unhide_all_elements():
    with signals.qt_update_guard():
        if not bpy.context or not bpy.context.scene: return
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if getattr(elem, "qt_hide", False):
                elem.qt_hide = False
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push("RZM: Unhide All")
            signals.SIGNALS.structure_changed.emit()
            signals.SIGNALS.transform_changed.emit()
