# RZMenu/operators/toggle_ops.py
import bpy
import string
from ..core.utils import find_toggle_def


def resize_toggle_definition_and_assignments(context, full_toggle_key, new_len):
    """Resize project toggle definition and every object assignment for this toggle."""
    if not full_toggle_key.startswith("rzm.Toggle."):
        return False, 0, 0

    new_len = max(1, min(32, int(new_len)))
    toggle_name = full_toggle_key.replace("rzm.Toggle.", "", 1)
    toggle_def = find_toggle_def(context, toggle_name)
    if not toggle_def:
        return False, 0, 0

    old_len = int(toggle_def.toggle_length)
    toggle_def.toggle_length = new_len

    changed_objects = 0
    for obj in context.scene.objects:
        if full_toggle_key not in obj:
            continue

        arr = list(obj[full_toggle_key])
        if len(arr) < new_len:
            arr.extend([0] * (new_len - len(arr)))
        elif len(arr) > new_len:
            arr = arr[:new_len]
        else:
            continue

        obj[full_toggle_key] = arr
        changed_objects += 1

    return True, old_len, changed_objects

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
                
                return {'FINISHED'}
        
        # Fallback if all letters are used
        i = 1
        while True:
            name = f"Toggle_{i}"
            if name not in existing_names:
                new_toggle = toggle_defs.add()
                new_toggle.toggle_name = name
                context.scene.rzm_active_toggle_def_index = len(toggle_defs) - 1
                
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
            
        return {'FINISHED'}

class RZM_OT_UpdateProjectToggle(bpy.types.Operator):
    bl_idname = "rzm.update_project_toggle"
    bl_label = "Update Project Toggle"
    bl_options = {'REGISTER', 'UNDO'}

    index: bpy.props.IntProperty()
    prop_name: bpy.props.StringProperty()
    val_str: bpy.props.StringProperty()

    def execute(self, context):
        toggles = context.scene.rzm.toggle_definitions
        if self.index < 0 or self.index >= len(toggles): return {'CANCELLED'}

        t = toggles[self.index]
        if hasattr(t, self.prop_name):
            try:
                target_type = type(getattr(t, self.prop_name))
                if target_type is int:
                    setattr(t, self.prop_name, int(self.val_str))
                elif target_type is bool:
                    setattr(t, self.prop_name, self.val_str == "True")
                else:
                    setattr(t, self.prop_name, self.val_str)
            except: pass
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
            
        return {'FINISHED'}

class RZM_OT_ToggleObjectBit(bpy.types.Operator):
    bl_idname = "rzm.toggle_object_bit"
    bl_label = "Toggle Bit"
    bl_options = {'REGISTER', 'UNDO'}

    toggle_name: bpy.props.StringProperty() 
    bit_index: bpy.props.IntProperty()

    def invoke(self, context, event):
        if event.alt:
            return self.trim_to_clicked_bit(context)
        return self.execute(context)

    def trim_to_clicked_bit(self, context):
        target_obj = context.active_object
        if not target_obj or self.toggle_name not in target_obj:
            return {'CANCELLED'}

        target_len = max(1, min(self.bit_index + 1, 32))
        ok, old_len, changed_objects = resize_toggle_definition_and_assignments(
            context,
            self.toggle_name,
            target_len,
        )
        if not ok:
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Resized toggle definition: {old_len} -> {target_len}; synced {changed_objects} object(s)."
        )
        return {'FINISHED'}
    
    def execute(self, context):
        target_obj = context.active_object
        if not target_obj or self.toggle_name not in target_obj:
            return {'CANCELLED'}
        
        # IDPropertyArray has to be converted to a list for modification
        arr = list(target_obj[self.toggle_name])
        if self.bit_index < 0 or self.bit_index >= len(arr):
            return {'CANCELLED'}

        arr[self.bit_index] = 1 - arr[self.bit_index]
        target_obj[self.toggle_name] = arr # Assign back
        
        # This operation is frequent, maybe don't record history for every bit toggle
        # to avoid flooding the undo stack. This is a design choice.
        # For now, we will record it.
        
        return {'FINISHED'}

class RZM_OT_ResizeObjectToggleBitmask(bpy.types.Operator):
    bl_idname = "rzm.resize_object_toggle_bitmask"
    bl_label = "Resize Toggle Bitmask"
    bl_description = "Increase or decrease assigned toggle bitmask length on the active object"
    bl_options = {'REGISTER', 'UNDO'}

    toggle_name: bpy.props.StringProperty()
    delta: bpy.props.IntProperty(default=1)

    def execute(self, context):
        target_obj = context.active_object
        if not target_obj or not self.toggle_name or self.toggle_name not in target_obj:
            return {'CANCELLED'}

        toggle_name = self.toggle_name.replace("rzm.Toggle.", "", 1)
        toggle_def = find_toggle_def(context, toggle_name)
        if not toggle_def:
            return {'CANCELLED'}

        old_len = int(toggle_def.toggle_length)
        new_len = max(1, min(32, old_len + self.delta))

        if new_len == old_len:
            self.report({'INFO'}, f"Toggle length already at {old_len} slot(s).")
            return {'CANCELLED'}

        ok, old_len, changed_objects = resize_toggle_definition_and_assignments(
            context,
            self.toggle_name,
            new_len,
        )
        if not ok:
            return {'CANCELLED'}

        self.report(
            {'INFO'},
            f"Resized toggle definition: {old_len} -> {new_len}; synced {changed_objects} object(s)."
        )
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

class RZM_OT_ApplyActiveTogglesToSelected(bpy.types.Operator):
    """Apply all assigned toggles from the active object to all selected objects."""
    bl_idname = "rzm.apply_toggles_to_selected"
    bl_label = "Apply to Selected"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        active_obj = context.active_object
        selected_objs = [obj for obj in context.selected_objects if obj != active_obj]

        if not active_obj:
            self.report({'WARNING'}, "No active object")
            return {'CANCELLED'}

        toggle_keys = [k for k in active_obj.keys() if k.startswith("rzm.Toggle.")]
        if not toggle_keys:
            self.report({'INFO'}, "No toggles to copy")
            return {'CANCELLED'}

        for obj in selected_objs:
            for key in toggle_keys:
                obj[key] = list(active_obj[key])

        self.report({'INFO'}, f"Applied {len(toggle_keys)} toggles to {len(selected_objs)} objects")
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_AddProjectToggle,
    RZM_OT_RemoveProjectToggle,
    RZM_OT_UpdateProjectToggle,
    RZM_OT_AssignObjectToggle,
    RZM_OT_RemoveObjectToggle,
    RZM_OT_ToggleObjectBit,
    RZM_OT_ResizeObjectToggleBitmask,
    RZM_OT_SelectOccupyingObjects,
    RZM_OT_SelectObjectsWithToggle,
    RZM_OT_ApplyActiveTogglesToSelected,
]
