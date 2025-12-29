# RZMenu/qt_editor/systems/operators.py
import bpy
from PySide6 import QtWidgets
from .. import core
from ..utils import logger

# --- CONTEXT ---

class RZContext:
    def __init__(self, window):
        self.window = window
        self.selected_ids = getattr(window, 'selected_ids', set())
        self.active_id = getattr(window, 'active_id', -1)
        if hasattr(window, 'panel_viewport'):
            self.scene = window.panel_viewport.rz_scene
        else:
            self.scene = None

# --- BASE OPERATOR ---

class RZOperator:
    id = ""          
    label = ""       
    flags = set() 

    def poll(self, context: RZContext) -> bool:
        return True

    def execute(self, context: RZContext, **kwargs):
        raise NotImplementedError

# --- CONCRETE OPERATORS ---

class RZ_OT_Undo(RZOperator):
    id = "rzm.undo"
    label = "Undo"
    
    def execute(self, context, **kwargs):
        core.exec_in_context(bpy.ops.ed.undo)
        context.window.brute_force_refresh()

class RZ_OT_Redo(RZOperator):
    id = "rzm.redo"
    label = "Redo"
    
    def execute(self, context, **kwargs):
        try:
            core.exec_in_context(bpy.ops.ed.redo)
        except:
            pass
        context.window.brute_force_refresh()

class RZ_OT_Delete(RZOperator):
    id = "rzm.delete"
    label = "Delete Selected"
    flags = {"REQUIRES_SELECTION"}

    def poll(self, context):
        return bool(context.selected_ids)

    def execute(self, context, **kwargs):
        core.delete_elements(context.selected_ids)
        context.window.clear_selection()
        context.window.brute_force_refresh()

class RZ_OT_Refresh(RZOperator):
    id = "rzm.refresh"
    label = "Force Refresh"
    
    def execute(self, context, **kwargs):
        context.window.brute_force_refresh()

class RZ_OT_SelectAll(RZOperator):
    id = "rzm.select_all"
    label = "Select All"
    
    def execute(self, context, **kwargs):
        all_data = core.get_all_elements_list()
        all_ids = {item['id'] for item in all_data}
        context.window.set_selection_multi(all_ids, active_id=-1)

class RZ_OT_Nudge(RZOperator):
    id = "rzm.nudge"
    label = "Nudge Element"
    flags = {"REQUIRES_SELECTION"}
    
    def poll(self, context):
        return bool(context.selected_ids)

    def execute(self, context, **kwargs):
        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        
        if x == 0 and y == 0: return

        core.move_elements_delta(context.selected_ids, x, y)
        core.commit_history("Nudge")
        
        context.window.refresh_viewport(force=True)
        context.window.refresh_inspector(force=True)

class RZ_OT_ViewportArrow(RZOperator):
    """
    Умная навигация стрелками:
    - Если есть выделение -> Двигает объекты (Nudge).
    - Если нет выделения -> Двигает 'камеру' (Pan View).
    """
    id = "rzm.viewport_arrow"
    label = "Viewport Navigation"
    
    def execute(self, context, **kwargs):
        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        
        # 1. Режим NUDGE (Движение объектов)
        if context.selected_ids:
            core.move_elements_delta(context.selected_ids, x, y)
            core.commit_history("Nudge")
            context.window.refresh_viewport(force=True)
            context.window.refresh_inspector(force=True)
            
        # 2. Режим PAN (Скроллинг вьюпорта)
        else:
            # --- FIX VIEWPORT ARROWS ---
            # Используем новый метод pan_view в RZViewportPanel
            context.window.panel_viewport.pan_view(x, y)

class RZ_OT_ViewReset(RZOperator):
    id = "rzm.view_reset"
    label = "Reset View"
    
    def execute(self, context, **kwargs):
        view = context.window.panel_viewport
        view.resetTransform() 
        view.centerOn(0, 0)   

_CLASSES = [
    RZ_OT_Delete,
    RZ_OT_Refresh,
    RZ_OT_Undo,
    RZ_OT_Redo,
    RZ_OT_SelectAll,
    RZ_OT_Nudge,
    RZ_OT_ViewportArrow,
    RZ_OT_ViewReset
]

OPERATOR_REGISTRY = {}

def register_operators():
    OPERATOR_REGISTRY.clear()
    for cls in _CLASSES:
        if not cls.id:
            logger.warn(f"Operator {cls.__name__} has no ID!")
            continue
        OPERATOR_REGISTRY[cls.id] = cls

def get_operator_class(op_id):
    return OPERATOR_REGISTRY.get(op_id)

register_operators()