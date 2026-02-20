# RZMenu/qt_editor/transform.py
import bpy
from . import signals
from . import blender_bridge
from .maths import get_local_pos_from_global

def resize_element(elem_id, x, y, w, h, silent=False):
    signals.IS_UPDATING_FROM_QT = True
    try:
        elements = bpy.context.scene.rzm.elements
        target = next((e for e in elements if e.id == elem_id), None)
        # ARCHITECT FIX: Check for split lock flag (size)
        if target and not getattr(target, "qt_lock_size", False):
            # (red) Манипуляции и Трансформации: Teleportation / No Matrix.
            # Direct modification of local coord without considering parent transform stack.
            target.position[0] = int(x)
            target.position[1] = int(y)
            target.size[0] = int(w)
            target.size[1] = int(h)
            
            if not silent:
                signals.SIGNALS.transform_changed.emit()
                signals.SIGNALS.data_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def set_element_position(elem_id, x, y, mode='GLOBAL', silent=False):
    """
    Unified entry point for setting element position.
    :param mode: 'GLOBAL' (Scene Coords) or 'LOCAL' (Parent Coords)
    """
    signals.IS_UPDATING_FROM_QT = True
    try:
        elements = bpy.context.scene.rzm.elements
        target = next((e for e in elements if e.id == elem_id), None)
        
        if target and not getattr(target, "qt_lock_pos", False):
            if mode == 'GLOBAL':
                # Convert Global -> Local
                elem_map = {e.id: e for e in elements}
                parent_id = getattr(target, "parent_id", -1)
                
                lx, ly = get_local_pos_from_global(x, y, parent_id, elem_map)
                target.position[0] = int(lx)
                target.position[1] = int(ly)
            else:
                # Direct Local Set
                target.position[0] = int(x)
                target.position[1] = int(y)
            
            if not silent:
                signals.SIGNALS.transform_changed.emit()
                signals.SIGNALS.data_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def update_element_pos(elem_id, x, y, silent=False):
    """Legacy/Convenience wrapper for set_element_position(..., mode='LOCAL')."""
    set_element_position(elem_id, x, y, mode='LOCAL', silent=silent)

def set_multiple_element_positions(pos_data, mode='GLOBAL', silent=False):
    """
    Batch update element positions.
    :param pos_data: dict {elem_id: (x, y)}
    :param mode: 'GLOBAL' or 'LOCAL'
    """
    signals.IS_UPDATING_FROM_QT = True
    try:
        elements = bpy.context.scene.rzm.elements
        elem_map = {e.id: e for e in elements}
        
        changed = False
        for eid, (x, y) in pos_data.items():
            target = elem_map.get(eid)
            if target and not getattr(target, "qt_lock_pos", False):
                if mode == 'GLOBAL':
                    parent_id = getattr(target, "parent_id", -1)
                    lx, ly = get_local_pos_from_global(x, y, parent_id, elem_map)
                    target.position[0] = int(lx)
                    target.position[1] = int(ly)
                else:
                    target.position[0] = int(x)
                    target.position[1] = int(y)
                changed = True
                
        if changed and not silent:
            signals.SIGNALS.transform_changed.emit()
            signals.SIGNALS.data_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def move_elements_delta(target_ids, delta_x, delta_y, silent=False):
    """
    Apply delta to local position.
    WARNING: This logic is strictly LOCAL. 
    If used on a child element, it moves relative to parent.
    Use set_element_position(mode='GLOBAL') for interaction where visual position matters most.
    """
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return
        elements = bpy.context.scene.rzm.elements
        
        # Determine roots of the selection to avoid double-movement
        id_to_parent = {e.id: e.parent_id for e in elements}
        root_target_ids = []
        for tid in target_ids:
            curr = id_to_parent.get(tid, -1)
            is_root = True
            while curr != -1:
                if curr in target_ids:
                    is_root = False; break
                curr = id_to_parent.get(curr, -1)
            if is_root:
                root_target_ids.append(tid)

        changed = False
        for elem in elements:
            if elem.id in root_target_ids and not getattr(elem, "qt_lock_pos", False):
                elem.position[0] += int(delta_x)
                elem.position[1] += int(delta_y)
                changed = True
        
        if changed and not silent:
             signals.SIGNALS.transform_changed.emit()
             signals.SIGNALS.data_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def align_elements(target_ids, mode):
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not target_ids or len(target_ids) < 2: return
        elements = bpy.context.scene.rzm.elements
        selection = [e for e in elements if e.id in target_ids]
        if not selection: return
        
        if mode == 'LEFT':
            val = min(e.position[0] for e in selection)
            for e in selection: e.position[0] = val
        elif mode == 'RIGHT':
            val = max(e.position[0] + e.size[0] for e in selection)
            for e in selection: e.position[0] = val - e.size[0]
        elif mode == 'TOP':
            val = max(e.position[1] for e in selection)
            for e in selection: e.position[1] = val
        elif mode == 'BOTTOM':
            val = min(e.position[1] - e.size[1] for e in selection)
            for e in selection: e.position[1] = val + e.size[1]
        elif mode == 'CENTER_X':
            min_x = min(e.position[0] for e in selection)
            max_r = max(e.position[0] + e.size[0] for e in selection)
            center = (min_x + max_r) / 2
            for e in selection: e.position[0] = int(center - e.size[0] / 2)
        elif mode == 'CENTER_Y':
            max_y = max(e.position[1] for e in selection)
            min_b = min(e.position[1] - e.size[1] for e in selection)
            center = (max_y + min_b) / 2
            for e in selection: e.position[1] = int(center + e.size[1] / 2)

        blender_bridge.safe_undo_push(f"RZM: Align {mode}")
        signals.SIGNALS.transform_changed.emit()
        signals.SIGNALS.data_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False