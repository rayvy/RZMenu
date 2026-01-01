# RZMenu/qt_editor/transform.py
import bpy
from . import signals
from . import blender_bridge

def resize_element(elem_id, x, y, w, h, silent=False):
    signals.IS_UPDATING_FROM_QT = True
    try:
        elements = bpy.context.scene.rzm.elements
        target = next((e for e in elements if e.id == elem_id), None)
        if target:
            target.position[0] = int(x)
            target.position[1] = int(y)
            target.size[0] = int(w)
            target.size[1] = int(h)
            
            if not silent:
                signals.SIGNALS.transform_changed.emit()
                signals.SIGNALS.data_changed.emit()
    finally:
        signals.IS_UPDATING_FROM_QT = False

def move_elements_delta(target_ids, delta_x, delta_y, silent=False):
    signals.IS_UPDATING_FROM_QT = True
    try:
        if not target_ids: return
        elements = bpy.context.scene.rzm.elements
        changed = False
        for elem in elements:
            if elem.id in target_ids:
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