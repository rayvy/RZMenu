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
    
    # Пути для вложенных коллекций (blocks -> components -> slots)
    block_index: bpy.props.IntProperty(default=-1)
    comp_index: bpy.props.IntProperty(default=-1)
    slot_index: bpy.props.IntProperty(default=-1)
    
    def execute(self, context):
        rzm = context.scene.rzm
        
        try:
            # Определение целевой коллекции
            if self.collection_name == "resources":
                coll = rzm.tw_resources
            elif self.collection_name == "overrides":
                coll = rzm.tw_overrides
            elif self.collection_name == "materials":
                coll = rzm.tw_materials
            elif self.collection_name == "blocks":
                coll = rzm.tw_blocks
            elif self.collection_name == "components":
                if self.block_index == -1: return {'CANCELLED'}
                coll = rzm.tw_blocks[self.block_index].components
            elif self.collection_name == "slots":
                if self.block_index == -1 or self.comp_index == -1: return {'CANCELLED'}
                coll = rzm.tw_blocks[self.block_index].components[self.comp_index].slots
            elif self.collection_name == "decal_layers":
                if self.block_index == -1 or self.comp_index == -1 or self.slot_index == -1: return {'CANCELLED'}
                coll = rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index].decal_layers
            else:
                return {'CANCELLED'}
            
            if coll is None or self.index >= len(coll): return {'CANCELLED'}
            
            item = coll[self.index]
            target = item
            bits = self.prop_name.split('.')
            for bit in bits[:-1]:
                target = getattr(target, bit)
            
            final_prop = bits[-1]
            
            if "[" in final_prop and final_prop.endswith("]"):
                prop_name, idx_str = final_prop[:-1].split("[")
                v_idx = int(idx_str)
                vector = getattr(target, prop_name)
                # Попробуем float для универсальности, потом в int если надо
                vector[v_idx] = float(self.value_str)
            elif hasattr(target, final_prop):
                prop_type = type(getattr(target, final_prop))
                if prop_type == bool:
                    setattr(target, final_prop, self.value_str.lower() in ("true", "1"))
                elif prop_type == int:
                    setattr(target, final_prop, int(float(self.value_str)))
                elif prop_type == float:
                    setattr(target, final_prop, float(self.value_str))
                else:
                    setattr(target, final_prop, self.value_str)
            
        except (AttributeError, IndexError, ValueError) as e:
            print(f"UpdateTwItem Error: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

# --- Базовые операции (Add/Remove) ---

class RZM_OT_AddTwResource(bpy.types.Operator):
    bl_idname = "rzm.add_tw_resource"
    bl_label = "Add Resource"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.tw_resources.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwResource(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_resource"
    bl_label = "Remove Resource"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.tw_resources
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll): coll.remove(idx)
        return {'FINISHED'}

class RZM_OT_AddTwOverride(bpy.types.Operator):
    bl_idname = "rzm.add_tw_override"
    bl_label = "Add Override"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.tw_overrides.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwOverride(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_override"
    bl_label = "Remove Override"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.tw_overrides
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll): coll.remove(idx)
        return {'FINISHED'}

class RZM_OT_AddTwMaterial(bpy.types.Operator):
    bl_idname = "rzm.add_tw_material"
    bl_label = "Add Material"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.tw_materials.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwMaterial(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_material"
    bl_label = "Remove Material"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.tw_materials
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll): coll.remove(idx)
        return {'FINISHED'}

# --- Hierarchical Operations (Blocks -> Components -> Slots) ---

class RZM_OT_AddTwBlock(bpy.types.Operator):
    bl_idname = "rzm.add_tw_block"
    bl_label = "Add Block"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.tw_blocks.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwBlock(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_block"
    bl_label = "Remove Block"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.tw_blocks
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll): coll.remove(idx)
        return {'FINISHED'}

class RZM_OT_AddTwComponent(bpy.types.Operator):
    bl_idname = "rzm.add_tw_component"
    bl_label = "Add Component"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.tw_blocks[self.block_index].components.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwComponent(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_component"
    bl_label = "Remove Component"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.tw_blocks[self.block_index].components
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll): coll.remove(idx)
        return {'FINISHED'}

class RZM_OT_AddTwSlot(bpy.types.Operator):
    bl_idname = "rzm.add_tw_slot"
    bl_label = "Add Slot"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index].slots.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwSlot(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_slot"
    bl_label = "Remove Slot"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index].slots
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll): coll.remove(idx)
        return {'FINISHED'}

class RZM_OT_AddTwDecalLayer(bpy.types.Operator):
    bl_idname = "rzm.add_tw_decal_layer"
    bl_label = "Add Decal Layer"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index].decal_layers.add()
        return {'FINISHED'}

class RZM_OT_RemoveTwDecalLayer(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_decal_layer"
    bl_label = "Remove Decal Layer"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        coll = context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index].decal_layers
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll): coll.remove(idx)
        return {'FINISHED'}

class RZM_OT_MoveTwDecalLayer(bpy.types.Operator):
    bl_idname = "rzm.move_tw_decal_layer"
    bl_label = "Move Decal Layer"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()
    index: bpy.props.IntProperty()
    direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    def execute(self, context):
        coll = context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index].decal_layers
        target_idx = self.index - 1 if self.direction == 'UP' else self.index + 1
        if 0 <= target_idx < len(coll):
            coll.move(self.index, target_idx)
        return {'FINISHED'}

classes_to_register = [
    RZM_OT_UpdateTwItem,
    RZM_OT_AddTwResource, RZM_OT_RemoveTwResource,
    RZM_OT_AddTwOverride, RZM_OT_RemoveTwOverride,
    RZM_OT_AddTwMaterial, RZM_OT_RemoveTwMaterial,
    RZM_OT_AddTwBlock, RZM_OT_RemoveTwBlock,
    RZM_OT_AddTwComponent, RZM_OT_RemoveTwComponent,
    RZM_OT_AddTwSlot, RZM_OT_RemoveTwSlot,
    RZM_OT_AddTwDecalLayer, RZM_OT_RemoveTwDecalLayer, RZM_OT_MoveTwDecalLayer,
]
