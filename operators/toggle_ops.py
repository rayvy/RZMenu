# RZMenu/operators/toggle_ops.py
import bpy
import string
from ..helpers import find_toggle_def

class RZM_OT_AddProjectToggle(bpy.types.Operator):
    bl_idname = "rzm.add_project_toggle"
    bl_label = "Add Project Toggle"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        toggle_defs = context.scene.rzm.toggle_definitions
        existing_names = {t.toggle_name for t in toggle_defs}
        
        # Find the next available default name (e.g., ToggleA, ToggleB)
        for char in string.ascii_uppercase:
            name = f"Toggle{char}"
            if name not in existing_names:
                new_toggle = toggle_defs.add()
                new_toggle.toggle_name = name
                context.scene.rzm_active_toggle_def_index = len(toggle_defs) - 1
                bpy.ops.rzm.record_history_state()
                return {'FINISHED'}
        
        # Fallback if all letters are used
        i = 1
        while True:
            name = f"Toggle_{i}"
            if name not in existing_names:
                new_toggle = toggle_defs.add()
                new_toggle.toggle_name = name
                context.scene.rzm_active_toggle_def_index = len(toggle_defs) - 1
                bpy.ops.rzm.record_history_state()
                return {'FINISHED'}
            i += 1

class RZM_OT_RemoveProjectToggle(bpy.types.Operator):
    bl_idname = "rzm.remove_project_toggle"
    bl_label = "Remove Project Toggle"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        toggle_defs = context.scene.rzm.toggle_definitions
        index = context.scene.rzm_active_toggle_def_index
        if 0 <= index < len(toggle_defs):
            toggle_defs.remove(index)
            if index > 0:
                context.scene.rzm_active_toggle_def_index = index - 1
            bpy.ops.rzm.record_history_state()
        return {'FINISHED'}
    
class RZM_OT_AssignObjectToggle(bpy.types.Operator):
    bl_idname = "rzm.assign_object_toggle"
    bl_label = "Assign Toggle"
    bl_options = {'REGISTER', 'UNDO'}
    
    toggle_name: bpy.props.StringProperty() 
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj:
            self.report({'WARNING'}, "No active object selected")
            return {'CANCELLED'}
        
        toggle_def = find_toggle_def(context, self.toggle_name)
        if not toggle_def:
            return {'CANCELLED'}
        
        prop_name = f"rzm.Toggle.{self.toggle_name}"
        target_obj[prop_name] = [0] * toggle_def.toggle_length
        bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_RemoveObjectToggle(bpy.types.Operator):
    bl_idname = "rzm.remove_object_toggle"
    bl_label = "Remove Assigned Toggle"
    bl_options = {'REGISTER', 'UNDO'}

    toggle_name: bpy.props.StringProperty() 
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj:
            return {'CANCELLED'}
        
        # The toggle_name passed from the UI is the full property key
        if self.toggle_name in target_obj:
            del target_obj[self.toggle_name]
            bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_ToggleObjectBit(bpy.types.Operator):
    bl_idname = "rzm.toggle_object_bit"
    bl_label = "Toggle Bit"
    bl_options = {'REGISTER', 'UNDO'}

    toggle_name: bpy.props.StringProperty() 
    bit_index: bpy.props.IntProperty()
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj or self.toggle_name not in target_obj:
            return {'CANCELLED'}
        
        # IDPropertyArray has to be converted to a list for modification
        arr = list(target_obj[self.toggle_name])
        arr[self.bit_index] = 1 - arr[self.bit_index]
        target_obj[self.toggle_name] = arr # Assign back
        
        # This operation is frequent, maybe don't record history for every bit toggle
        # to avoid flooding the undo stack. This is a design choice.
        # For now, we will record it.
        bpy.ops.rzm.record_history_state()
        return {'FINISHED'}
    
class RZM_OT_SelectOccupyingObjects(bpy.types.Operator):
    """Выделяет все объекты, у которых включен конкретный бит в этом тоггле"""
    bl_idname = "rzm.select_occupying_objects"
    bl_label = "Select Objects in Slot"
    bl_options = {'REGISTER', 'UNDO'}

    toggle_name: bpy.props.StringProperty() # Имя без префикса (например "Hat")
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        
        full_key = f"rzm.Toggle.{self.toggle_name}"
        objects_to_select = []
        
        for obj in context.scene.objects:
            if full_key in obj.keys():
                value = obj[full_key]
                # Безопасное приведение к списку
                try:
                    bits = list(value)
                    if self.slot_index < len(bits) and bits[self.slot_index]:
                        objects_to_select.append(obj)
                except:
                    continue

        if not objects_to_select:
            self.report({'INFO'}, f"No objects found for {self.toggle_name} slot {self.slot_index + 1}.")
            return {'CANCELLED'}

        for obj in objects_to_select:
            obj.select_set(True)

        context.view_layer.objects.active = objects_to_select[0]
        self.report({'INFO'}, f"Selected {len(objects_to_select)} objects.")
        return {'FINISHED'}

class RZM_OT_SelectObjectsWithToggle(bpy.types.Operator):
    """Выделяет все объекты, на которые назначен этот тоггл (независимо от битов)"""
    bl_idname = "rzm.select_objects_with_toggle"
    bl_label = "Select All Objects with Toggle"
    bl_options = {'REGISTER', 'UNDO'}

    toggle_name: bpy.props.StringProperty() # Имя без префикса

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        
        full_key = f"rzm.Toggle.{self.toggle_name}"
        objects_to_select = []
        
        for obj in context.scene.objects:
            if full_key in obj.keys():
                objects_to_select.append(obj)

        if not objects_to_select:
            self.report({'INFO'}, f"No objects found with toggle '{self.toggle_name}'.")
            return {'CANCELLED'}

        for obj in objects_to_select:
            obj.select_set(True)

        context.view_layer.objects.active = objects_to_select[0]
        self.report({'INFO'}, f"Selected {len(objects_to_select)} objects.")
        return {'FINISHED'}

    
classes_to_register = [
    RZM_OT_AddProjectToggle,
    RZM_OT_RemoveProjectToggle,
    RZM_OT_AssignObjectToggle,
    RZM_OT_RemoveObjectToggle,
    RZM_OT_ToggleObjectBit,
    RZM_OT_SelectOccupyingObjects,
    RZM_OT_SelectObjectsWithToggle,
]
