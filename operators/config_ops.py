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
            
        # Emit signal for UI refresh
        from ..qt_editor.core.signals import SIGNALS
        SIGNALS.data_changed.emit()
            
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
             # Try root properties if not in export_settings
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

class RZM_OT_UpdateMetadataSetting(bpy.types.Operator):
    """Update a metadata setting."""
    bl_idname = "rzm.update_metadata_setting"
    bl_label = "Update Metadata"
    bl_options = {'REGISTER', 'UNDO'}
    
    prop_name: bpy.props.StringProperty()
    val_str: bpy.props.StringProperty()
    val_bool: bpy.props.BoolProperty()
    use_bool: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        meta = context.scene.rzm.meta_data
        if hasattr(meta, self.prop_name):
            if self.use_bool:
                setattr(meta, self.prop_name, self.val_bool)
            else:
                setattr(meta, self.prop_name, self.val_str)
            
            # Emit signal for UI refresh
            from ..qt_editor.core.signals import SIGNALS
            SIGNALS.data_changed.emit()
            
            return {'FINISHED'}
        return {'CANCELLED'}

class RZM_OT_UpdateFontSetting(bpy.types.Operator):
    bl_idname = "rzm.update_font_setting"
    bl_label = "Update Font Config"
    bl_options = {'UNDO'}
    
    slot_index: bpy.props.IntProperty(default=0)
    prop_name: bpy.props.StringProperty()
    val_str: bpy.props.StringProperty()
    val_float: bpy.props.FloatProperty()
    val_int: bpy.props.IntProperty()
    val_bool: bpy.props.BoolProperty(default=False)
    use_float: bpy.props.BoolProperty(default=False)
    use_int: bpy.props.BoolProperty(default=False)
    use_bool: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        if len(context.scene.rzm.fonts) == 0:
            for i in range(4):
                context.scene.rzm.fonts.add()
        
        fonts = context.scene.rzm.fonts
        if 0 <= self.slot_index < len(fonts):
            slot = fonts[self.slot_index]
            if hasattr(slot, self.prop_name):
                if self.use_float:
                    setattr(slot, self.prop_name, self.val_float)
                elif self.use_int:
                    setattr(slot, self.prop_name, self.val_int)
                elif self.use_bool:
                    setattr(slot, self.prop_name, self.val_bool)
                else:
                    setattr(slot, self.prop_name, self.val_str)
                    
                from ..qt_editor.core.signals import SIGNALS
                SIGNALS.data_changed.emit()
                return {'FINISHED'}
        return {'CANCELLED'}

class RZM_OT_UpdateGlobalSetting(bpy.types.Operator):
    """Update a global addon preference setting."""
    bl_idname = "rzm.update_global_setting"
    bl_label = "Update Global Setting"
    bl_options = {'REGISTER', 'UNDO'}
    
    prop_name: bpy.props.StringProperty()
    val_str: bpy.props.StringProperty()
    
    def execute(self, context):
        from .tier_ops import get_prefs
        prefs = get_prefs(context)
        if prefs and hasattr(prefs, self.prop_name):
            setattr(prefs, self.prop_name, self.val_str)
            
            from ..qt_editor.core.signals import SIGNALS
            SIGNALS.data_changed.emit()
            return {'FINISHED'}
        return {'CANCELLED'}

class RZM_OT_UpdateAddonSettingInt(bpy.types.Operator):
    """Update an addon integer property (e.g. in_game_profile_count)."""
    bl_idname = "rzm.update_addon_setting_int"
    bl_label = "Update Addon Setting (Int)"
    bl_options = {'REGISTER', 'UNDO'}

    prop_name: bpy.props.StringProperty()
    val_int: bpy.props.IntProperty()

    def execute(self, context):
        addons = context.scene.rzm.addons
        if hasattr(addons, self.prop_name):
            setattr(addons, self.prop_name, self.val_int)
            from ..qt_editor.core.signals import SIGNALS
            SIGNALS.data_changed.emit()
            return {'FINISHED'}
        return {'CANCELLED'}

classes_to_register = [
    RZM_OT_UpdateConfigSetting,
    RZM_OT_UpdateExportSetting,
    RZM_OT_UpdateAddonSetting,
    RZM_OT_UpdateAddonSettingInt,
    RZM_OT_UpdateMetadataSetting,
    RZM_OT_UpdateFontSetting,
    RZM_OT_UpdateGlobalSetting,
]

def register():
    for cls in classes_to_register:
        bpy.utils.register_class(cls)

def unregister():
    for cls in reversed(classes_to_register):
        bpy.utils.unregister_class(cls)
