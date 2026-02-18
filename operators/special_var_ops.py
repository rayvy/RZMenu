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
        new_shape = context.scene.rzm.shapes.add()
        # Auto-naming
        base_name = "#Shape"
        cnt = 0
        new_name = f"{base_name}_{cnt}"
        existing = {s.shape_name for s in context.scene.rzm.shapes}
        while new_name in existing:
            cnt += 1
            new_name = f"{base_name}_{cnt}"
        new_shape.shape_name = new_name
        
        return {'FINISHED'}

class RZM_OT_RemoveShape(bpy.types.Operator):
    bl_idname = "rzm.remove_shape"
    bl_label = "Remove Shape"
    bl_options = {'REGISTER', 'UNDO'}
    
    index: bpy.props.IntProperty(default=-1)
    
    def execute(self, context):
        coll = context.scene.rzm.shapes
        idx = self.index if self.index >= 0 else len(coll) - 1
        
        if 0 <= idx < len(coll):
            coll.remove(idx)
            return {'FINISHED'}
        return {'CANCELLED'}

class RZM_OT_UpdateShape(bpy.types.Operator):
    """Update a property of a Shape variable."""
    bl_idname = "rzm.update_shape"
    bl_label = "Update Shape"
    bl_options = {'REGISTER', 'UNDO'}
    
    shape_index: bpy.props.IntProperty()
    prop_name: bpy.props.StringProperty()
    val_str: bpy.props.StringProperty()
    val_int: bpy.props.IntProperty()
    # No float/bool separate needed if we just parse or use specific args, 
    # but strictly typed args are safer for Blender ops.
    # Let's use string for generic/enum and specific for numbers if needed.
    # Actually, simplistic approach: pass string and cast based on target prop type.
    
    def execute(self, context):
        shapes = context.scene.rzm.shapes
        if self.shape_index < 0 or self.shape_index >= len(shapes):
            return {'CANCELLED'}
        
        shape = shapes[self.shape_index]
        
        # Safe attribute set
        if hasattr(shape, self.prop_name):
            attr = getattr(shape, self.prop_name)
            target_type = type(attr)
            
            try:
                if target_type is int:
                    setattr(shape, self.prop_name, int(self.val_str))
                elif target_type is float:
                    setattr(shape, self.prop_name, float(self.val_str))
                elif target_type is bool:
                    setattr(shape, self.prop_name, self.val_str == "True")
                else:
                    setattr(shape, self.prop_name, self.val_str)
            except ValueError:
                self.report({'ERROR'}, f"Invalid value for {self.prop_name}")
                return {'CANCELLED'}
                
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
    key_index: bpy.props.IntProperty(default=-1)
    
    def execute(self, context):
        shapes = context.scene.rzm.shapes
        if self.shape_index < 0 or self.shape_index >= len(shapes):
            return {'CANCELLED'}

        coll = shapes[self.shape_index].shape_keys
        idx = self.key_index if self.key_index >= 0 else len(coll) - 1

        if 0 <= idx < len(coll):
            coll.remove(idx)
            return {'FINISHED'}
        return {'CANCELLED'}

class RZM_OT_UpdateShapeKey(bpy.types.Operator):
    bl_idname = "rzm.update_shape_key"
    bl_label = "Update Shape Key"
    bl_options = {'REGISTER', 'UNDO'}
    
    shape_index: bpy.props.IntProperty()
    key_index: bpy.props.IntProperty()
    prop_name: bpy.props.StringProperty()
    val_str: bpy.props.StringProperty()
    
    def execute(self, context):
        shapes = context.scene.rzm.shapes
        if self.shape_index < 0 or self.shape_index >= len(shapes):
            return {'CANCELLED'}
            
        keys = shapes[self.shape_index].shape_keys
        if self.key_index < 0 or self.key_index >= len(keys):
            return {'CANCELLED'}
            
        key = keys[self.key_index]
        
        if hasattr(key, self.prop_name):
            attr = getattr(key, self.prop_name)
            target_type = type(attr)
            try:
                if target_type is int:
                    setattr(key, self.prop_name, int(float(self.val_str))) # float->int to be safe
                elif target_type is float:
                    setattr(key, self.prop_name, float(self.val_str))
                else:
                    setattr(key, self.prop_name, self.val_str)
            except:
                pass

        return {'FINISHED'}

class RZM_OT_UpdateValue(bpy.types.Operator):
    bl_idname = "rzm.update_value"
    bl_label = "Update Value"
    bl_options = {'REGISTER', 'UNDO'}
    
    index: bpy.props.IntProperty()
    prop_name: bpy.props.StringProperty()
    val_str: bpy.props.StringProperty()
    
    def execute(self, context):
        values = context.scene.rzm.rzm_values
        if self.index < 0 or self.index >= len(values): return {'CANCELLED'}
        
        val_item = values[self.index]
        target = val_item
        prop_path = self.prop_name.split('.')
        for bit in prop_path[:-1]:
            target = getattr(target, bit)
        
        final_prop = prop_path[-1]
        
        try:
            if "[" in final_prop and final_prop.endswith("]"):
                prop_name, idx_str = final_prop[:-1].split("[")
                v_idx = int(idx_str)
                vector = getattr(target, prop_name)
                vector[v_idx] = float(self.val_str)
            elif hasattr(target, final_prop):
                attr = getattr(target, final_prop)
                target_type = type(attr)
                if target_type is int:
                     setattr(target, final_prop, int(float(self.val_str)))
                elif target_type is float:
                     setattr(target, final_prop, float(self.val_str))
                else:
                     setattr(target, final_prop, self.val_str)
        except Exception as e:
            print(f"RZM_OT_UpdateValue Error: {e}")
            
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AddCondition, RZM_OT_RemoveCondition,
    RZM_OT_AddShape, RZM_OT_RemoveShape, RZM_OT_UpdateShape,
    RZM_OT_AddShapeKey, RZM_OT_RemoveShapeKey, RZM_OT_UpdateShapeKey,
    RZM_OT_UpdateValue,
]
