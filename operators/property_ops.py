# RZMenu/operators/property_ops.py
import bpy

class RZM_OT_ListAction(bpy.types.Operator):
    """Generic operator to add/remove items from a named collection on an element."""
    bl_idname = "rzm.list_action"
    bl_label = "RZMenu List Action"
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(items=(('ADD', 'Add', ''), ('REMOVE', 'Remove', '')))
    collection: bpy.props.StringProperty()
    
    def execute(self, context):
        active_idx = context.scene.rzm_active_element_index
        elements = context.scene.rzm.elements
        if not (0 <= active_idx < len(elements)):
            return {'CANCELLED'}
            
        elem = elements[active_idx]
        
        if not hasattr(elem, self.collection):
            return {'CANCELLED'}
            
        prop_collection = getattr(elem, self.collection)
        
        if self.action == 'ADD':
            prop_collection.add()
        elif self.action == 'REMOVE' and len(prop_collection) > 0:
            prop_collection.remove(len(prop_collection) - 1)
            
        
        return {'FINISHED'}
    
class RZM_OT_AddConditionalImage(bpy.types.Operator):
    """Adds an item to the conditional images list."""
    bl_idname = "rzm.add_conditional_image"
    bl_label = "Add Conditional Image"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_idx = context.scene.rzm_active_element_index
        elements = context.scene.rzm.elements
        if 0 <= active_idx < len(elements):
            elements[active_idx].conditional_images.add()
            
        return {'FINISHED'}

class RZM_OT_RemoveConditionalImage(bpy.types.Operator):
    """Removes the last item from the conditional images list."""
    bl_idname = "rzm.remove_conditional_image"
    bl_label = "Remove Conditional Image"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_idx = context.scene.rzm_active_element_index
        elements = context.scene.rzm.elements
        if 0 <= active_idx < len(elements):
            cond_images = elements[active_idx].conditional_images
            if len(cond_images) > 0:
                cond_images.remove(len(cond_images) - 1)
                
        return {'FINISHED'}

class RZM_OT_AddValue(bpy.types.Operator):
    """Adds a new global value to the project."""
    bl_idname = "rzm.add_value"
    bl_label = "Add Value"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        values = context.scene.rzm.rzm_values
        new_val = values.add()
        new_val.value_name = f"$NewValue_{len(values)}"
        context.scene.rzm_active_value_index = len(values) - 1
        
        return {'FINISHED'}

class RZM_OT_RemoveValue(bpy.types.Operator):
    """Removes the selected global value from the project."""
    bl_idname = "rzm.remove_value"
    bl_label = "Remove Value"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        values = context.scene.rzm.rzm_values
        index = context.scene.rzm_active_value_index
        if 0 <= index < len(values):
            values.remove(index)
            if index > 0:
                context.scene.rzm_active_value_index = index - 1
            
        return {'FINISHED'}

class RZM_OT_SetValueLink(bpy.types.Operator):
    """Adds a value link to the active UI element."""
    bl_idname = "rzm.set_value_link"
    bl_label = "Add Value Link"
    bl_options = {'REGISTER', 'UNDO'}

    link_target: bpy.props.StringProperty()

    def execute(self, context):
        active_idx = context.scene.rzm_active_element_index
        elements = context.scene.rzm.elements
        if 0 <= active_idx < len(elements):
            elem = elements[active_idx]
            new_link = elem.value_link.add()
            new_link.value_name = self.link_target
            
        else:
            self.report({'WARNING'}, "No active UI element selected.")
            return {'CANCELLED'}
        return {'FINISHED'}

class RZM_OT_RemoveValueLink(bpy.types.Operator):
    """Removes an item from the value_link list by index."""
    bl_idname = "rzm.remove_value_link"
    bl_label = "Remove Value Link"
    bl_options = {'REGISTER', 'UNDO'}
    
    index_to_remove: bpy.props.IntProperty()

    def execute(self, context):
        active_idx = context.scene.rzm_active_element_index
        elements = context.scene.rzm.elements
        if 0 <= active_idx < len(elements):
            links = elements[active_idx].value_link
            if 0 <= self.index_to_remove < len(links):
                links.remove(self.index_to_remove)
                
        return {'FINISHED'}

class RZM_OT_UpdateProfileSlot(bpy.types.Operator):
    """Updates a specific slot in the in_game_profiles collection."""
    bl_idname = "rzm.update_profile_slot"
    bl_label = "Update Profile Slot"
    bl_options = {'REGISTER', 'UNDO'}

    var_type: bpy.props.EnumProperty(items=(
        ('VALUE', 'Value', ''),
        ('TOGGLE', 'Toggle', ''),
        ('SHAPE', 'Shape', '')
    ))
    var_index: bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()
    val_str: bpy.props.StringProperty()
    is_bool: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        rzm = context.scene.rzm
        
        # 1. Resolve Parent Variable
        parent = None
        if self.var_type == 'VALUE':
            if 0 <= self.var_index < len(rzm.rzm_values):
                parent = rzm.rzm_values[self.var_index]
        elif self.var_type == 'TOGGLE':
            if 0 <= self.var_index < len(rzm.toggle_definitions):
                parent = rzm.toggle_definitions[self.var_index]
        elif self.var_type == 'SHAPE':
            if 0 <= self.var_index < len(rzm.shapes):
                parent = rzm.shapes[self.var_index]
        
        if not parent:
            return {'CANCELLED'}
            
        # 2. Resolve Profile Slot
        if self.slot_index < 0 or self.slot_index >= len(parent.in_game_profiles):
            # Try to sync if missing? (Should be handled by sync button, but let's be safe)
            return {'CANCELLED'}
            
        slot = parent.in_game_profiles[self.slot_index]
        
        # 3. Apply Value
        try:
            if self.is_bool:
                slot.int_value = 1 if self.val_str == "True" else 0
            else:
                # Store as int or float based on what's provided
                if "." in self.val_str:
                    slot.float_value = float(self.val_str)
                    slot.int_value = int(slot.float_value)
                else:
                    slot.int_value = int(self.val_str)
                    slot.float_value = float(slot.int_value)
        except Exception as e:
            print(f"UpdateProfileSlot Error: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_ListAction,
    RZM_OT_AddConditionalImage,
    RZM_OT_RemoveConditionalImage,
    RZM_OT_AddValue,
    RZM_OT_RemoveValue,
    RZM_OT_SetValueLink,
    RZM_OT_RemoveValueLink,
    RZM_OT_UpdateProfileSlot,
]
