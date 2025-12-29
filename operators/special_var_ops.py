# RZMenu/operators/special_var_ops.py
import bpy

# --- ОПЕРАТОРЫ ДЛЯ SPECIAL VARIABLES ---
class RZM_OT_AddCondition(bpy.types.Operator):
    bl_idname = "rzm.add_condition"
    bl_label = "Add Condition"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.conditions.add()
        
        return {'FINISHED'}

class RZM_OT_RemoveCondition(bpy.types.Operator):
    bl_idname = "rzm.remove_condition"
    bl_label = "Remove Condition"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.conditions
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
            
        return {'FINISHED'}

class RZM_OT_AddShape(bpy.types.Operator):
    bl_idname = "rzm.add_shape"
    bl_label = "Add Shape"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.shapes.add()
        
        return {'FINISHED'}

class RZM_OT_RemoveShape(bpy.types.Operator):
    bl_idname = "rzm.remove_shape"
    bl_label = "Remove Shape"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.shapes
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
            
        return {'FINISHED'}

class RZM_OT_AddShapeKey(bpy.types.Operator):
    bl_idname = "rzm.add_shape_key"
    bl_label = "Add Shape Key"
    bl_options = {'REGISTER', 'UNDO'}
    shape_index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.shapes[self.shape_index].shape_keys.add()
        
        return {'FINISHED'}

class RZM_OT_RemoveShapeKey(bpy.types.Operator):
    bl_idname = "rzm.remove_shape_key"
    bl_label = "Remove Shape Key"
    bl_options = {'REGISTER', 'UNDO'}
    shape_index: bpy.props.IntProperty()
    def execute(self, context):
        coll = context.scene.rzm.shapes[self.shape_index].shape_keys
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
            
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AddCondition, RZM_OT_RemoveCondition,
    RZM_OT_AddShape, RZM_OT_RemoveShape,
    RZM_OT_AddShapeKey, RZM_OT_RemoveShapeKey,
]
