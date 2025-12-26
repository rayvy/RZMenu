# RZMenu/operators/history_ops.py
import bpy
from ..rzm_serialization import rzm_to_dict, dict_to_rzm
from ..rzm_history import history_manager

# --- Система Истории (Undo/Redo) ---
class RZM_OT_RecordHistoryState(bpy.types.Operator):
    """Внутренний оператор: делает слепок rzm и сохраняет в историю."""
    bl_idname = "rzm.record_history_state"
    bl_label = "RZM Record History"
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        current_state = rzm_to_dict(context.scene.rzm)
        history_manager.push_state(current_state)
        return {'FINISHED'}

class RZM_OT_Undo(bpy.types.Operator):
    bl_idname = "rzm.undo"
    bl_label = "RZM Undo"
    
    @classmethod
    def poll(cls, context):
        return history_manager.can_undo()
        
    def execute(self, context):
        state_to_restore = history_manager.undo()
        if state_to_restore:
            dict_to_rzm(state_to_restore, context.scene.rzm)
        return {'FINISHED'}

class RZM_OT_Redo(bpy.types.Operator):
    bl_idname = "rzm.redo"
    bl_label = "RZM Redo"

    @classmethod
    def poll(cls, context):
        return history_manager.can_redo()

    def execute(self, context):
        state_to_restore = history_manager.redo()
        if state_to_restore:
            dict_to_rzm(state_to_restore, context.scene.rzm)
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_RecordHistoryState,
    RZM_OT_Undo,
    RZM_OT_Redo,
]
