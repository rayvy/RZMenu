# RZMenu/operators/validation_ops.py
import bpy

class RZM_OT_SelectProblematicObjects(bpy.types.Operator):
    bl_idname = "rzm.select_problematic_objects"
    bl_label = "Select All Problematic Objects"
    bl_description = "Select all mesh objects that have missing UV or Color attributes"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        from ..utils.xxmi_data_predictor import get_export_issues
        issues = get_export_issues(context)
        if not issues:
            self.report({'INFO'}, "No problematic objects found!")
            return {'FINISHED'}
            
        # Снимаем выделение со всех
        bpy.ops.object.select_all(action='DESELECT')
        
        count = 0
        for obj, _ in issues:
            try:
                obj.select_set(True)
                count += 1
            except Exception:
                pass
            
        # Устанавливаем первый активным
        if issues:
            try:
                context.view_layer.objects.active = issues[0][0]
            except Exception:
                pass
            
        self.report({'INFO'}, f"Selected {count} problematic objects.")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_SelectProblematicObjects
]
