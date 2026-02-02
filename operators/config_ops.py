# RZMenu/operators/config_ops.py
import bpy

# --- CONFIGURATION OPERATORS ---

class RZM_OT_UpdateConfigSetting(bpy.types.Operator):
    """Update a general configuration setting."""
    bl_idname = "rzm.update_config_setting"
    bl_label = "Update Config Setting"
    bl_options = {'REGISTER', 'UNDO'}
    
    prop_name: bpy.props.StringProperty()
    val_str: bpy.props.StringProperty()
    is_int: bpy.props.BoolProperty(default=False)
    index: bpy.props.IntProperty(default=-1) # For vector props like canvas size
    
    def execute(self, context):
        config = context.scene.rzm.config
        if not hasattr(config, self.prop_name):
            return {'CANCELLED'}
            
        attr = getattr(config, self.prop_name)
        
        try:
            if self.index >= 0:
                # Assuming vector property
                arr = list(attr)
                if self.is_int:
                    arr[self.index] = int(self.val_str)
                else:
                    arr[self.index] = float(self.val_str)
                setattr(config, self.prop_name, arr)
            else:
                if self.is_int:
                    setattr(config, self.prop_name, int(self.val_str))
                else:
                    # String or Enum
                    setattr(config, self.prop_name, self.val_str)
        except Exception as e:
            self.report({'ERROR'}, f"Failed to update {self.prop_name}: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

class RZM_OT_UpdateExportSetting(bpy.types.Operator):
    """Update an export setting."""
    bl_idname = "rzm.update_export_setting"
    bl_label = "Update Export Setting"
    bl_options = {'REGISTER', 'UNDO'}
    
    prop_name: bpy.props.StringProperty()
    val_str: bpy.props.StringProperty()
    val_bool: bpy.props.BoolProperty()
    use_bool: bpy.props.BoolProperty(default=False)
    
    def execute(self, context):
        settings = context.scene.rzm.export_settings
        if not hasattr(settings, self.prop_name):
             # Try root properties if not in export_settings?
             # User prompt showed some props on root RZMenuProperties (export_texture_slots)
             # Let's check root if not in settings
             settings = context.scene.rzm
             if not hasattr(settings, self.prop_name):
                 return {'CANCELLED'}

        try:
            if self.use_bool:
                setattr(settings, self.prop_name, self.val_bool)
            else:
                setattr(settings, self.prop_name, self.val_str)
        except Exception as e:
            self.report({'ERROR'}, f"Failed: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}

class RZM_OT_UpdateAddonSetting(bpy.types.Operator):
    """Update an addon boolean flag."""
    bl_idname = "rzm.update_addon_setting"
    bl_label = "Update Addon Setting"
    bl_options = {'REGISTER', 'UNDO'}
    
    prop_name: bpy.props.StringProperty()
    val_bool: bpy.props.BoolProperty()
    
    def execute(self, context):
        addons = context.scene.rzm.addons
        if hasattr(addons, self.prop_name):
            setattr(addons, self.prop_name, self.val_bool)
            return {'FINISHED'}
        return {'CANCELLED'}

classes_to_register = [
    RZM_OT_UpdateConfigSetting,
    RZM_OT_UpdateExportSetting,
    RZM_OT_UpdateAddonSetting,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
