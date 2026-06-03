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
        
        # Smart numbering: if Diffuse exists, try Diffuse.1, Diffuse.2, etc.
        base_slot = self.slot_name
        prop_name = f"rzm.TexSlot.{base_slot}"
        
        if prop_name in target_obj:
            counter = 1
            while f"rzm.TexSlot.{base_slot}.{counter}" in target_obj:
                counter += 1
            prop_name = f"rzm.TexSlot.{base_slot}.{counter}"
        
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
            slot_id = self.prop_key.replace("rzm.TexSlot.", "")
            cond_key = f"rzm.TexCond.{slot_id}"
            init_key = f"rzm.TexInitAttach.{slot_id}"
            
            # Remove slot
            del target_obj[self.prop_key]
            # Remove linked condition if exists
            if cond_key in target_obj:
                del target_obj[cond_key]
            if init_key in target_obj:
                del target_obj[init_key]
            
        # Trigger redraw
        context.area.tag_redraw()
        return {'FINISHED'}

class RZM_OT_AddObjectTexCond(bpy.types.Operator):
    """Add a condition to the texture slot."""
    bl_idname = "rzm.add_object_tex_cond"
    bl_label = "Add Condition"
    bl_options = {'REGISTER', 'UNDO'}

    prop_key: bpy.props.StringProperty() # Full key like rzm.TexSlot.Diffuse
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj: return {'CANCELLED'}
        
        slot_id = self.prop_key.replace("rzm.TexSlot.", "")
        cond_key = f"rzm.TexCond.{slot_id}"
        
        if cond_key not in target_obj:
            target_obj[cond_key] = ""
            
        context.area.tag_redraw()
        return {'FINISHED'}

class RZM_OT_RemoveObjectTexCond(bpy.types.Operator):
    """Remove a condition from the texture slot."""
    bl_idname = "rzm.remove_object_tex_cond"
    bl_label = "Remove Condition"
    bl_options = {'REGISTER', 'UNDO'}

    prop_key: bpy.props.StringProperty() # Full key like rzm.TexSlot.Diffuse
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj: return {'CANCELLED'}
        
        slot_id = self.prop_key.replace("rzm.TexSlot.", "")
        cond_key = f"rzm.TexCond.{slot_id}"
        
        if cond_key in target_obj:
            del target_obj[cond_key]
            
        context.area.tag_redraw()
        return {'FINISHED'}

class RZM_OT_ToggleObjectTexInitAttach(bpy.types.Operator):
    """Toggle ModInitialised attachment guard for the texture slot."""
    bl_idname = "rzm.toggle_object_tex_init_attach"
    bl_label = "Toggle InitialisedAttachment"
    bl_options = {'REGISTER', 'UNDO'}

    prop_key: bpy.props.StringProperty()

    def execute(self, context):
        target_obj = context.active_object
        if not target_obj:
            return {'CANCELLED'}

        slot_id = self.prop_key.replace("rzm.TexSlot.", "")
        init_key = f"rzm.TexInitAttach.{slot_id}"
        target_obj[init_key] = not bool(target_obj.get(init_key, False))

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
                # Copy Slot
                obj[key] = active_obj[key]
                
                # Copy Condition (if exists)
                slot_id = key.replace("rzm.TexSlot.", "")
                cond_key = f"rzm.TexCond.{slot_id}"
                if cond_key in active_obj:
                    obj[cond_key] = active_obj[cond_key]

                init_key = f"rzm.TexInitAttach.{slot_id}"
                if init_key in active_obj:
                    obj[init_key] = active_obj[init_key]

        self.report({'INFO'}, f"Applied {len(tex_keys)} slots, conditions, and init attachments to {len(selected_objs)} objects")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AssignObjectTexSlot,
    RZM_OT_RemoveObjectTexSlot,
    RZM_OT_AddObjectTexCond,
    RZM_OT_RemoveObjectTexCond,
    RZM_OT_ToggleObjectTexInitAttach,
    RZM_OT_CopyTexSlotsToSelected,
]
