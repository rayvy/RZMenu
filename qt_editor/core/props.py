# RZMenu/qt_editor/props.py
import bpy
from . import signals
from . import blender_bridge

def update_property_multi(target_ids, prop_name, value, sub_index=None, fast_mode=False):
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return
        changed = False
        elements = bpy.context.scene.rzm.elements
        
        map_props = {
            "pos_x": ("position", 0), "pos_y": ("position", 1),
            "width": ("size", 0), "height": ("size", 1),
            "is_hidden": ("qt_hide", None), "is_locked": ("qt_locked", None),
            "is_selectable": ("qt_selectable", None), "color": ("color", None),
            "grid_rows": ("grid_rows", None), "grid_cols": ("grid_cols", None),
            "grid_gap": ("grid_gap", None),             "grid_padding": ("grid_padding", None),
            "grid_cell_size": ("grid_cell_size", None),
            "alignment": ("alignment", None),
            "text_align": ("text_align", None),
        }

        bl_prop = prop_name
        bl_idx = sub_index
        if prop_name in map_props:
            bl_prop, fixed_idx = map_props[prop_name]
            if fixed_idx is not None: bl_idx = fixed_idx
        
        for elem in elements:
            if elem.id in target_ids:
                if hasattr(elem, bl_prop):
                    current_val = getattr(elem, bl_prop)
                    if bl_prop == "color":
                        try:
                            setattr(elem, bl_prop, value[:len(current_val)])
                            changed = True
                        except: pass
                    elif bl_idx is not None:
                        if current_val[bl_idx] != value:
                            current_val[bl_idx] = value
                            changed = True
                    else:
                        if current_val != value:
                            setattr(elem, bl_prop, value)
                            changed = True
                else:
                    try: elem[bl_prop] = value; changed = True
                    except: pass

        if changed:
            if not fast_mode: blender_bridge.safe_undo_push(f"RZM: Change {prop_name}")
            
            if prop_name in ["pos_x", "pos_y", "width", "height"]:
                signals.SIGNALS.transform_changed.emit()
                signals.SIGNALS.data_changed.emit()
            elif prop_name in ["element_name", "is_hidden", "qt_hide", "is_locked"]:
                signals.SIGNALS.structure_changed.emit()
                signals.SIGNALS.data_changed.emit()
            else:
                signals.SIGNALS.data_changed.emit()
                signals.SIGNALS.transform_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def toggle_editor_flag(target_ids, flag_name):
    map_flags = {
        "is_hidden": "qt_hide", "is_locked": "qt_locked", "is_selectable": "qt_selectable"
    }
    bl_prop = map_flags.get(flag_name)
    if not bl_prop: return

    signals.IS_UPDATING_FROM_QT = True
    try:
        changed = False
        elements = bpy.context.scene.rzm.elements
        for elem in elements:
            if elem.id in target_ids:
                curr = getattr(elem, bl_prop, False)
                setattr(elem, bl_prop, not curr)
                changed = True
        
        if changed:
            blender_bridge.safe_undo_push(f"RZM: Toggle {flag_name}")
            signals.SIGNALS.structure_changed.emit()
            signals.SIGNALS.data_changed.emit()
            signals.SIGNALS.transform_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def perform_math_operation(target_ids, prop_name, op_str, sub_index=None):
    """Parses and applies relative math operations (+=, -=, *=, /=) to multiple elements."""
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return
        elements = bpy.context.scene.rzm.elements
        changed = False
        
        # 1. Map properties
        map_props = {
            "pos_x": ("position", 0), "pos_y": ("position", 1),
            "width": ("size", 0), "height": ("size", 1),
            "grid_rows": ("grid_rows", None), "grid_cols": ("grid_cols", None),
            "grid_gap": ("grid_gap", None), "grid_padding": ("grid_padding", None),
            "grid_cell_size": ("grid_cell_size", None),
        }
        
        bl_prop = prop_name
        bl_idx = sub_index
        if prop_name in map_props:
            bl_prop, fixed_idx = map_props[prop_name]
            if fixed_idx is not None: bl_idx = fixed_idx

        # 2. Parse operation
        op = op_str[:2] # +=, -= etc
        try:
            val = float(op_str[2:])
        except ValueError:
            return

        # 3. Apply
        for elem in elements:
            if elem.id in target_ids:
                if hasattr(elem, bl_prop):
                    current_obj = getattr(elem, bl_prop)
                    
                    # Get current numeric value
                    try:
                        if bl_idx is not None:
                            curr_val = current_obj[bl_idx]
                        else:
                            curr_val = float(current_obj)
                    except: continue

                    # Calculate new
                    if op == "+=": new_val = curr_val + val
                    elif op == "-=": new_val = curr_val - val
                    elif op == "*=": new_val = curr_val * val
                    elif op == "/=": new_val = curr_val / val if val != 0 else curr_val
                    else: continue

                    # Write back
                    if bl_idx is not None:
                        current_obj[bl_idx] = int(new_val) if isinstance(curr_val, int) else new_val
                    else:
                        setattr(elem, bl_prop, int(new_val) if isinstance(current_obj, int) else new_val)
                    changed = True

        if changed:
            blender_bridge.safe_undo_push(f"RZM: Math {op_str} on {prop_name}")
            signals.SIGNALS.transform_changed.emit()
            signals.SIGNALS.data_changed.emit()
            
    finally:
        signals.IS_UPDATING_FROM_QT = False

def unhide_all_elements():
    signals.IS_UPDATING_FROM_QT = True
    try:
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
    finally:
        signals.IS_UPDATING_FROM_QT = False