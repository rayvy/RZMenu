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

class RZM_OT_CopyTexSlotsToSelected(bpy.types.Operator):
    """Copy all texture slot settings from the active object to all selected objects."""
    bl_idname = "rzm.copy_tex_slots_to_selected"
    bl_label = "Apply to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_obj = context.active_object
        selected_objs = [obj for obj in context.selected_objects if obj != active_obj]

        if not active_obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        tex_keys = [k for k in active_obj.keys() if k.startswith("rzm.TexSlot.")]
        if not tex_keys:
            self.report({'INFO'}, "No texture slots to copy")
            return {'CANCELLED'}

        for obj in selected_objs:
            for key in tex_keys:
                obj[key] = active_obj[key]

        self.report({'INFO'}, f"Applied {len(tex_keys)} slots to {len(selected_objs)} objects")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AssignObjectTexSlot,
    RZM_OT_RemoveObjectTexSlot,
    RZM_OT_CopyTexSlotsToSelected,
]
