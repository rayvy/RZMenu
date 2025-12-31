# RZMenu/qt_editor/systems/operators.py
import bpy
from .. import core

# --- CONTEXT HELPER ---
class RZContext:
    """Прослойка для удобного доступа к данным из оператора"""
    def __init__(self, window):
        self.window = window
        self.selected_ids = getattr(window, 'selected_ids', set())
        self.active_id = getattr(window, 'active_id', -1)

# --- BASE OPERATOR ---
class RZOperator:
    id = ""          
    label = ""
    # Если True, кнопка будет неактивна без выделения
    requires_selection = False 

    def poll(self, context: RZContext) -> bool:
        if self.requires_selection and not context.selected_ids:
            return False
        return True

    def execute(self, context: RZContext, **kwargs):
        raise NotImplementedError

# --- OPERATORS (Тупые обертки над Core) ---

class RZ_OT_Undo(RZOperator):
    id = "rzm.undo"
    label = "Undo"
    def execute(self, context, **kwargs):
        # Undo сам вызовет обновление через Blender Monitor, нам не нужно пинать UI
        core.exec_in_context(bpy.ops.ed.undo)

class RZ_OT_Redo(RZOperator):
    id = "rzm.redo"
    label = "Redo"
    def execute(self, context, **kwargs):
        try: core.exec_in_context(bpy.ops.ed.redo)
        except: pass

class RZ_OT_Delete(RZOperator):
    id = "rzm.delete"
    label = "Delete"
    requires_selection = True
    def execute(self, context, **kwargs):
        core.delete_elements(context.selected_ids)
        context.window.clear_selection()

class RZ_OT_Refresh(RZOperator):
    id = "rzm.refresh"
    label = "Force Refresh"
    def execute(self, context, **kwargs):
        # Единственное место, где мы явно просим окно обновиться
        context.window.full_refresh()

class RZ_OT_SelectAll(RZOperator):
    id = "rzm.select_all"
    label = "Select All"
    def execute(self, context, **kwargs):
        # Это UI логика, поэтому можно оставить вызов окна, 
        # либо перенести get_all_ids в core.read
        all_data = core.get_all_elements_list()
        all_ids = {item['id'] for item in all_data}
        context.window.set_selection_multi(all_ids, active_id=-1)

class RZ_OT_Nudge(RZOperator):
    id = "rzm.nudge"
    label = "Nudge"
    requires_selection = True
    def execute(self, context, **kwargs):
        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        if x == 0 and y == 0: return
        # silent=False потому что это одиночное нажатие, нужен рефреш
        core.move_elements_delta(context.selected_ids, x, y, silent=False)
        core.commit_history("Nudge")

class RZ_OT_ViewportArrow(RZOperator):
    id = "rzm.viewport_arrow"
    label = "Nav/Nudge"
    def execute(self, context, **kwargs):
        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        # Если есть выделение - двигаем объекты
        if context.selected_ids:
            core.move_elements_delta(context.selected_ids, x, y, silent=False)
            core.commit_history("Nudge")
        # Если нет - двигаем камеру (панорамирование)
        else:
            context.window.panel_viewport.pan_view(x, y)

class RZ_OT_ViewReset(RZOperator):
    id = "rzm.view_reset"
    label = "Reset View"
    def execute(self, context, **kwargs):
        view = context.window.panel_viewport
        view.resetTransform() 
        view.centerOn(0, 0)   

class RZ_OT_CreateElement(RZOperator):
    id = "rzm.create"
    label = "Create"
    def execute(self, context, **kwargs):
        class_type = kwargs.get('class_type', 'CONTAINER')
        x = kwargs.get('x', 0)
        y = kwargs.get('y', 0)
        parent_id = context.active_id if context.active_id != -1 else -1
        
        new_id = core.create_element(class_type, x, y, parent_id)
        if new_id:
            context.window.set_selection_multi({new_id}, active_id=new_id)

class RZ_OT_ToggleHide(RZOperator):
    id = "rzm.toggle_hide"
    label = "Hide/Show"
    # Poll сложнее: или выделение, или override
    def poll(self, context): 
        return bool(context.selected_ids) # Упростим для KISS
    def execute(self, context, **kwargs):
        # Поддержка override_ids для кликов по иконкам в аутлайнере
        ids = kwargs.get("override_ids", context.selected_ids)
        core.toggle_editor_flag(ids, "is_hidden")

class RZ_OT_ToggleLock(RZOperator):
    id = "rzm.toggle_lock"
    label = "Lock"
    requires_selection = True
    def execute(self, context, **kwargs):
        core.toggle_editor_flag(context.selected_ids, "is_locked")

class RZ_OT_ToggleSelectable(RZOperator):
    id = "rzm.toggle_selectable"
    label = "Selectable"
    def poll(self, context): return bool(context.selected_ids)
    def execute(self, context, **kwargs):
        ids = kwargs.get("override_ids", context.selected_ids)
        core.toggle_editor_flag(ids, "is_selectable")

class RZ_OT_UnhideAll(RZOperator):
    id = "rzm.unhide_all"
    label = "Unhide All"
    def execute(self, context, **kwargs):
        core.unhide_all_elements()

class RZ_OT_Duplicate(RZOperator):
    id = "rzm.duplicate"
    label = "Duplicate"
    requires_selection = True
    def execute(self, context, **kwargs):
        new_ids = core.duplicate_elements(context.selected_ids)
        if new_ids:
            context.window.set_selection_multi(new_ids, active_id=-1)

class RZ_OT_Copy(RZOperator):
    id = "rzm.copy"
    label = "Copy"
    requires_selection = True
    def execute(self, context, **kwargs):
        core.copy_elements(context.selected_ids)

class RZ_OT_Paste(RZOperator):
    id = "rzm.paste"
    label = "Paste"
    def execute(self, context, **kwargs):
        target_x = None
        target_y = None
        # Если вызвано мышкой (через контекстное меню), берем координаты мыши
        if kwargs.get('use_mouse', False):
            viewport = context.window.panel_viewport
            global_pos = QtGui.QCursor.pos()
            view_pos = viewport.mapFromGlobal(global_pos)
            scene_pos = viewport.mapToScene(view_pos)
            target_x = int(scene_pos.x())
            target_y = int(-scene_pos.y())
            
        new_ids = core.paste_elements(target_x, target_y)
        if new_ids:
            context.window.set_selection_multi(new_ids, active_id=-1)

class RZ_OT_Align(RZOperator):
    id = "rzm.align"
    label = "Align"
    def poll(self, context): return len(context.selected_ids) > 1
    def execute(self, context, **kwargs):
        mode = kwargs.get('mode', 'LEFT')
        core.align_elements(context.selected_ids, mode)

# --- REGISTRY ---

_CLASSES = [
    RZ_OT_Delete, RZ_OT_Refresh, RZ_OT_Undo, RZ_OT_Redo,
    RZ_OT_SelectAll, RZ_OT_Nudge, RZ_OT_ViewportArrow, RZ_OT_ViewReset,
    RZ_OT_CreateElement,
    RZ_OT_ToggleHide, RZ_OT_ToggleLock, RZ_OT_ToggleSelectable,
    RZ_OT_UnhideAll,
    RZ_OT_Duplicate, RZ_OT_Copy, RZ_OT_Paste,
    RZ_OT_Align
]

OPERATOR_REGISTRY = {}

def register_operators():
    OPERATOR_REGISTRY.clear()
    for cls in _CLASSES:
        if cls.id: OPERATOR_REGISTRY[cls.id] = cls

def get_operator_class(op_id):
    return OPERATOR_REGISTRY.get(op_id)

register_operators()