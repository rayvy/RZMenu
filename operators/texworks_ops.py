# RZMenu/operators/texworks_ops.py
import bpy

# --- ОПЕРАТОРЫ ДЛЯ TEXWORKS ---
class RZM_OT_SetTwFormat(bpy.types.Operator):
    """Internal operator to set the DXGI format from a menu."""
    bl_idname = "rzm.set_tw_format"
    bl_label = "Set TexWorks Format"
    bl_options = {'REGISTER', 'INTERNAL'}
    
    format_to_set: bpy.props.StringProperty()
    
    def execute(self, context):
        atlas_index = getattr(context.window_manager, 'rzm_context_atlas_index', -1)
        
        if atlas_index != -1:
            try:
                configs = context.scene.rzm.addons.tw_texture_configs
                target_config = configs[atlas_index]
                target_config.tw_atlas_settings.tw_format = self.format_to_set
            except (IndexError, AttributeError) as e:
                print(f"ERROR: Could not set TW format. Index: {atlas_index}, Error: {e}")
            finally:
                # Clean up the temporary variable
                del context.window_manager.rzm_context_atlas_index
        else:
            self.report({'WARNING'}, "Could not determine context for setting format.")

        return {'FINISHED'}

class RZM_OT_AddTwResource(bpy.types.Operator):
    bl_idname = "rzm.add_tw_resource"
    bl_label = "Add TexWorks Resource"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_resources.add()
        bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_RemoveTwResource(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_resource"
    bl_label = "Remove TexWorks Resource"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_resources
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
            bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_AddTwOverride(bpy.types.Operator):
    bl_idname = "rzm.add_tw_override"
    bl_label = "Add TexWorks Override"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_overrides.add()
        bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_RemoveTwOverride(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_override"
    bl_label = "Remove TexWorks Override"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_overrides
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
            bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_AddTwConfig(bpy.types.Operator):
    bl_idname = "rzm.add_tw_config"
    bl_label = "Add TexWorks Config"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_texture_configs.add()
        bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_RemoveTwConfig(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_config"
    bl_label = "Remove TexWorks Config"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_texture_configs
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
            bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_AddTwTexture(bpy.types.Operator):
    bl_idname = "rzm.add_tw_texture"
    bl_label = "Add TexWorks Texture"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_textures.add()
        bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_RemoveTwTexture(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_texture"
    bl_label = "Remove TexWorks Texture"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_textures
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
            bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_AddTwAlternative(bpy.types.Operator):
    bl_idname = "rzm.add_tw_alternative"
    bl_label = "Add TexWorks Alternative"
    bl_options = {'REGISTER', 'UNDO'}
    texture_index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.addons.tw_textures[self.texture_index].tw_alternatives.add()
        bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

class RZM_OT_RemoveTwAlternative(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_alternative"
    bl_label = "Remove TexWorks Alternative"
    bl_options = {'REGISTER', 'UNDO'}
    texture_index: bpy.props.IntProperty()
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_textures[self.texture_index].tw_alternatives
        if len(coll) > 0:
            coll.remove(len(coll) - 1)
            bpy.ops.rzm.record_history_state()
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_SetTwFormat,
    RZM_OT_AddTwResource, RZM_OT_RemoveTwResource,
    RZM_OT_AddTwOverride, RZM_OT_RemoveTwOverride,
    RZM_OT_AddTwConfig, RZM_OT_RemoveTwConfig,
    RZM_OT_AddTwTexture, RZM_OT_RemoveTwTexture,
    RZM_OT_AddTwAlternative, RZM_OT_RemoveTwAlternative,
]
