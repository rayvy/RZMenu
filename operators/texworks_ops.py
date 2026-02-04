# RZMenu/operators/texworks_ops.py
import bpy

# --- ОПЕРАТОРЫ ДЛЯ TEXWORKS ---

class RZM_OT_UpdateTwItem(bpy.types.Operator):
    """Generic operator to update property of a TexWorks collection item."""
    bl_idname = "rzm.update_tw_item"
    bl_label = "Update TexWorks Item"
    bl_options = {'REGISTER', 'UNDO'}
    
    collection_name: bpy.props.StringProperty()
    index: bpy.props.IntProperty()
    prop_name: bpy.props.StringProperty()
    value_str: bpy.props.StringProperty()
    parent_index: bpy.props.IntProperty(default=-1) # For nested collections like alternatives
    
    def execute(self, context):
        rzm = context.scene.rzm
        addons = rzm.addons
        
        try:
            # 1. Path to collection
            if self.collection_name == "alternatives":
                if self.parent_index == -1: return {'CANCELLED'}
                parent_tex = addons.tw_textures[self.parent_index]
                coll = parent_tex.tw_alternatives
            else:
                coll = getattr(addons, self.collection_name, None)
            
            if coll is None: return {'CANCELLED'}
            
            # 2. Get item
            item = coll[self.index]
            
            # 3. Update property (Support nested attributes like 'tw_atlas_settings.tw_width')
            target = item
            bits = self.prop_name.split('.')
            for bit in bits[:-1]:
                target = getattr(target, bit)
            
            final_prop = bits[-1]
            
            # Handle vector/array indexing like "tw_position[0]"
            if "[" in final_prop and final_prop.endswith("]"):
                prop_name, idx_str = final_prop[:-1].split("[")
                v_idx = int(idx_str)
                vector = getattr(target, prop_name)
                vector[v_idx] = int(float(self.value_str))
            elif hasattr(target, final_prop):
                # Try to convert types
                prop_type = type(getattr(target, final_prop))
                if prop_type == bool:
                    setattr(target, final_prop, self.value_str.lower() in ("true", "1"))
                elif prop_type == int:
                    setattr(target, final_prop, int(float(self.value_str))) # Allow int(2.0)
                elif prop_type == float:
                    setattr(target, final_prop, float(self.value_str))
                else:
                    setattr(target, final_prop, self.value_str)
            
        except (AttributeError, IndexError, ValueError) as e:
            print(f"UpdateTwItem Error: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

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
        return {'FINISHED'}

class RZM_OT_RemoveTwResource(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_resource"
    bl_label = "Remove TexWorks Resource"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_resources
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll):
            coll.remove(idx)
        return {'FINISHED'}

class RZM_OT_AddTwOverride(bpy.types.Operator):
    bl_idname = "rzm.add_tw_override"
    bl_label = "Add TexWorks Override"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_overrides.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwOverride(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_override"
    bl_label = "Remove TexWorks Override"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_overrides
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll):
            coll.remove(idx)
        return {'FINISHED'}

class RZM_OT_AddTwConfig(bpy.types.Operator):
    bl_idname = "rzm.add_tw_config"
    bl_label = "Add TexWorks Config"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_texture_configs.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwConfig(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_config"
    bl_label = "Remove TexWorks Config"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_texture_configs
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll):
            coll.remove(idx)
        return {'FINISHED'}

class RZM_OT_AddTwTexture(bpy.types.Operator):
    bl_idname = "rzm.add_tw_texture"
    bl_label = "Add TexWorks Texture"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.addons.tw_textures.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwTexture(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_texture"
    bl_label = "Remove TexWorks Texture"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_textures
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll):
            coll.remove(idx)
        return {'FINISHED'}

class RZM_OT_AddTwAlternative(bpy.types.Operator):
    bl_idname = "rzm.add_tw_alternative"
    bl_label = "Add TexWorks Alternative"
    bl_options = {'REGISTER', 'UNDO'}
    texture_index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.addons.tw_textures[self.texture_index].tw_alternatives.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwAlternative(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_alternative"
    bl_label = "Remove TexWorks Alternative"
    bl_options = {'REGISTER', 'UNDO'}
    texture_index: bpy.props.IntProperty()
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.addons.tw_textures[self.texture_index].tw_alternatives
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll):
            coll.remove(idx)
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_UpdateTwItem,
    RZM_OT_SetTwFormat,
    RZM_OT_AddTwResource, RZM_OT_RemoveTwResource,
    RZM_OT_AddTwOverride, RZM_OT_RemoveTwOverride,
    RZM_OT_AddTwConfig, RZM_OT_RemoveTwConfig,
    RZM_OT_AddTwTexture, RZM_OT_RemoveTwTexture,
    RZM_OT_AddTwAlternative, RZM_OT_RemoveTwAlternative,
]
