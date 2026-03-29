# RZMenu/operators/texslot_ops.py
import bpy

class RZM_OT_AssignObjectTexSlot(bpy.types.Operator):
    """Assign a TexSlot to the active object."""
    bl_idname = "rzm.assign_object_tex_slot"
    bl_label = "Assign TexSlot"
    bl_options = {'REGISTER', 'UNDO'}
    
    slot_name: bpy.props.StringProperty() # Diffuse, LightMap, etc.
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj:
            self.report({'WARNING'}, "No active object selected")
            return {'CANCELLED'}
        
        prop_name = f"rzm.TexSlot.{self.slot_name}"
        # Only set if it doesn't exist, to prevent overwriting existing resource names
        if prop_name not in target_obj:
            target_obj[prop_name] = ""
        
        # Trigger redraw
        context.area.tag_redraw()
        return {'FINISHED'}


class RZM_OT_RemoveObjectTexSlot(bpy.types.Operator):
    """Remove a TexSlot from the active object."""
    bl_idname = "rzm.remove_object_tex_slot"
    bl_label = "Remove TexSlot"
    bl_options = {'REGISTER', 'UNDO'}

    prop_key: bpy.props.StringProperty() # Full key like rzm.TexSlot.Diffuse
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj:
            return {'CANCELLED'}
        
        if self.prop_key in target_obj:
            del target_obj[self.prop_key]
            
        # Trigger redraw
        context.area.tag_redraw()
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AssignObjectTexSlot,
    RZM_OT_RemoveObjectTexSlot,
]
