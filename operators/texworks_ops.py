# RZMenu/operators/texworks_ops.py
import bpy
import os
from .export_manager import get_target_path

# --- ОПЕРАТОРЫ ДЛЯ TEXWORKS ---

def trigger_refresh():
    try:
        from ..qt_editor.core.signals import SIGNALS
        SIGNALS.structure_changed.emit()
    except Exception: pass

# --- OPERATORS ---



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
            elif self.collection_name == "override_bindings":
                if self.block_index == -1: return {'CANCELLED'}
                coll = rzm.tw_overrides[self.block_index].bindings
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
                # Ensure we handle both int and float vectors safely
                val_float = float(self.value_str)
                try:
                    vector[v_idx] = int(val_float)
                except TypeError:
                    vector[v_idx] = val_float

            elif hasattr(target, final_prop):
                prop_type = type(getattr(target, final_prop))
                
                # Check for vector types (e.g., FloatVectorProperty, IntVectorProperty)
                # Note: strings are iterable in Python, so we must explicitly exclude them
                if (hasattr(prop_type, '__iter__') and prop_type != str) or "Vector" in str(prop_type):
                    # Try parsing as comma separated string
                    vals = [x.strip() for x in self.value_str.split(",")]
                    current_vec = getattr(target, final_prop)
                    for i in range(min(len(vals), len(current_vec))):
                        try:
                            current_vec[i] = float(vals[i]) if "." in vals[i] or "e" in vals[i].lower() else int(vals[i])
                        except ValueError: pass
                
                elif prop_type == bool:
                    setattr(target, final_prop, self.value_str.lower() in ("true", "1"))
                elif prop_type == int:
                    setattr(target, final_prop, int(float(self.value_str)))
                elif prop_type == float:
                    setattr(target, final_prop, float(self.value_str))
                else:
                    setattr(target, final_prop, self.value_str)
            
        except (AttributeError, IndexError, ValueError, TypeError) as e:
            print(f"UpdateTwItem Error: {e}")
            return {'CANCELLED'}
            
        trigger_refresh()
        return {'FINISHED'}

# --- Базовые операции (Add/Remove) ---

class RZM_OT_AddTwResource(bpy.types.Operator):
    bl_idname = "rzm.add_tw_resource"
    bl_label = "Add Resource"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.tw_resources.add()
        trigger_refresh()
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
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_AddTwOverride(bpy.types.Operator):
    bl_idname = "rzm.add_tw_override"
    bl_label = "Add Override"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.tw_overrides.add()
        trigger_refresh()
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
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_AddTwMaterial(bpy.types.Operator):
    bl_idname = "rzm.add_tw_material"
    bl_label = "Add Material"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.tw_materials.add()
        trigger_refresh()
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
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_TwSelectMaterial(bpy.types.Operator):
    """Triggers blender search for material and assigns to tw_materials."""
    bl_idname = "rzm.tw_select_material"
    bl_label = "Select TexWorks Material"
    bl_property = "material_name"
    
    index: bpy.props.IntProperty()
    material_name: bpy.props.EnumProperty(
        name="Material",
        items=lambda self, context: [(m.name, m.name, "") for m in bpy.data.materials if not m.is_grease_pencil]
    )
    
    def execute(self, context):
        rzm = context.scene.rzm
        mat = bpy.data.materials.get(self.material_name)
        if mat and 0 <= self.index < len(rzm.tw_materials):
            rzm.tw_materials[self.index].material = mat
        trigger_refresh()
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}


# --- Automation Operators ---

class RZM_OT_ClearTwResources(bpy.types.Operator):
    """Remove all resources EXCEPT favorites."""
    bl_idname = "rzm.clear_tw_resources"
    bl_label = "Clear Resources (Keep Favorites)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        coll = context.scene.rzm.tw_resources
        # Iterate backwards to remove safely
        for i in range(len(coll) - 1, -1, -1):
            if not coll[i].qt_favorite:
                coll.remove(i)
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_ClearTwOverrides(bpy.types.Operator):
    """Remove all overrides EXCEPT favorites."""
    bl_idname = "rzm.clear_tw_overrides"
    bl_label = "Clear Overrides (Keep Favorites)"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        coll = context.scene.rzm.tw_overrides
        for i in range(len(coll) - 1, -1, -1):
            if not coll[i].qt_favorite:
                coll.remove(i)
        trigger_refresh()
        return {'FINISHED'}

from bpy_extras.io_utils import ImportHelper

class RZM_OT_TwResOverFill(bpy.types.Operator, ImportHelper):

    """Auto-fill Resources and Overrides from dump folder (Context-aware)."""
    bl_idname = "rzm.tw_res_over_fill"
    bl_label = "ResOver Fill (Auto-Import)"
    bl_description = "Select a folder containing dump textures or hash.json"
    
    # ImportHelper properties
    directory: bpy.props.StringProperty(subtype='DIR_PATH')
    
    def execute(self, context):
        from ..utils.texworks_importer import import_from_folder
        
        if not os.path.exists(self.directory):
            self.report({'ERROR'}, "Selected directory does not exist.")
            return {'CANCELLED'}
            
        print(f"\n[DEBUG] TexWorks Auto-Import Operator Triggered: {self.directory}")

        
        count, msg = import_from_folder(context, self.directory)
        
        if count > 0:
            self.report({'INFO'}, f"Auto-Import Complete: {msg}")
            trigger_refresh()
            return {'FINISHED'}
        else:
            self.report({'WARNING'}, f"Import skipped: {msg}")
            return {'CANCELLED'}


# --- Hierarchical Operations (Blocks -> Components -> Slots) ---

class RZM_OT_AddTwBlock(bpy.types.Operator):
    bl_idname = "rzm.add_tw_block"
    bl_label = "Add Block"
    bl_options = {'REGISTER', 'UNDO'}
    def execute(self, context):
        context.scene.rzm.tw_blocks.add()
        context.scene.rzm.active_tw_block_index = len(context.scene.rzm.tw_blocks) - 1
        trigger_refresh()
        return {'FINISHED'}

def copy_properties(src, target):
    """Recursively copies properties from one PropertyGroup to another."""
    if not src or not target: return
    
    for prop in src.bl_rna.properties:
        ident = prop.identifier
        if ident in {"rna_type"}: continue
        
        # Collection handling: add then recurse
        if prop.type == 'COLLECTION':
            src_coll = getattr(src, ident)
            target_coll = getattr(target, ident)
            # We don't clear() because it's a new item, but if it were an update, clear() would be needed.
            # In duplicate mode, target_coll is usually empty if it's a fresh .add()
            target_coll.clear()
            for src_item in src_coll:
                target_item = target_coll.add()
                copy_properties(src_item, target_item)
            continue
            
        if prop.is_readonly: continue
        
        try:
            setattr(target, ident, getattr(src, ident))
        except Exception as e:
            print(f"Error copying property {ident}: {e}")

class RZM_OT_DuplicateTwBlock(bpy.types.Operator):
    bl_idname = "rzm.duplicate_tw_block"
    bl_label = "Duplicate Block"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(default=-1)
    
    def execute(self, context):
        rzm = context.scene.rzm
        try:
            idx = self.index if self.index >= 0 else rzm.active_tw_block_index
            if idx < 0 or idx >= len(rzm.tw_blocks): return {'CANCELLED'}
            
            src_block = rzm.tw_blocks[idx]
            new_block = rzm.tw_blocks.add()
            
            # Copy all props
            copy_properties(src_block, new_block)
            
            # Override name with copy suffix
            new_block.name = src_block.name + "_copy"
            
            # Select new block
            rzm.active_tw_block_index = len(rzm.tw_blocks) - 1
            
        except (IndexError, AttributeError):
            return {'CANCELLED'}
        
        return {'FINISHED'}

class RZM_OT_RemoveTwBlock(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_block"
    bl_label = "Remove Block"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        rzm = context.scene.rzm
        coll = rzm.tw_blocks
        idx = self.index if self.index >= 0 else rzm.active_tw_block_index
        if idx < 0 or idx >= len(coll):
            return {'CANCELLED'}

        coll.remove(idx)
        if len(coll) == 0:
            rzm.active_tw_block_index = 0
        else:
            rzm.active_tw_block_index = min(idx, len(coll) - 1)
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_AddTwOverrideBinding(bpy.types.Operator):
    bl_idname = "rzm.add_tw_override_binding"
    bl_label = "Add Override Binding"
    bl_options = {'REGISTER', 'UNDO'}
    override_index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        coll = context.scene.rzm.tw_overrides
        if not (0 <= self.override_index < len(coll)):
            return {'CANCELLED'}

        over = coll[self.override_index]
        if not over.bindings and over.resource_name:
            binding = over.bindings.add()
            binding.tex_type = over.slot_target or "Diffuse"
            binding.resource_name = over.resource_name
            binding.custom_target = (binding.tex_type or "").strip().lower().startswith("ps-t")

        binding = over.bindings.add()
        binding.tex_type = "Diffuse"
        binding.resource_name = ""
        binding.custom_target = False
        over.active_binding_index = len(over.bindings) - 1
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_RemoveTwOverrideBinding(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_override_binding"
    bl_label = "Remove Override Binding"
    bl_options = {'REGISTER', 'UNDO'}
    override_index: bpy.props.IntProperty(default=-1)
    index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        coll = context.scene.rzm.tw_overrides
        if not (0 <= self.override_index < len(coll)):
            return {'CANCELLED'}
        bindings = coll[self.override_index].bindings
        if 0 <= self.index < len(bindings):
            bindings.remove(self.index)
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_AddTwComponent(bpy.types.Operator):
    bl_idname = "rzm.add_tw_component"
    bl_label = "Add Component"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    def execute(self, context):
        b = context.scene.rzm.tw_blocks[self.block_index]
        b.components.add()
        b.active_component_index = len(b.components) - 1
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_RemoveTwComponent(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_component"
    bl_label = "Remove Component"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        b = context.scene.rzm.tw_blocks[self.block_index]
        coll = b.components
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll): coll.remove(idx)
        b.active_component_index = max(0, min(b.active_component_index, len(coll) - 1))
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_AddTwSlot(bpy.types.Operator):
    bl_idname = "rzm.add_tw_slot"
    bl_label = "Add Slot"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    def execute(self, context):
        c = context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index]
        c.slots.add()
        c.active_slot_index = len(c.slots) - 1
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_RemoveTwSlot(bpy.types.Operator):
    bl_idname = "rzm.remove_tw_slot"
    bl_label = "Remove Slot"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        c = context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index]
        coll = c.slots
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll): coll.remove(idx)
        c.active_slot_index = max(0, min(c.active_slot_index, len(coll) - 1))
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_AddTwDecalLayer(bpy.types.Operator):
    bl_idname = "rzm.add_tw_decal_layer"
    bl_label = "Add Decal Layer"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()
    def execute(self, context):
        s = context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index]
        s.decal_layers.add()
        s.active_layer_index = len(s.decal_layers) - 1
        trigger_refresh()
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
        s = context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index]
        coll = s.decal_layers
        idx = self.index if self.index >= 0 else len(coll) - 1
        if 0 <= idx < len(coll): coll.remove(idx)
        s.active_layer_index = max(0, min(s.active_layer_index, len(coll) - 1))
        trigger_refresh()
        return {'FINISHED'}


class RZM_OT_SetActiveBlock(bpy.types.Operator):
    bl_idname = "rzm.set_active_block"
    bl_label = "Set Active Block"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty()
    def execute(self, context):
        rzm = context.scene.rzm
        if self.index < 0 or self.index >= len(rzm.tw_blocks):
            return {'CANCELLED'}
        rzm.active_tw_block_index = self.index
        trigger_refresh()
        return {'FINISHED'}

class RZM_OT_SetActiveComponent(bpy.types.Operator):
    bl_idname = "rzm.set_active_component"
    bl_label = "Set Active Component"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.tw_blocks[self.block_index].active_component_index = self.index
        return {'FINISHED'}

class RZM_OT_SetActiveSlot(bpy.types.Operator):
    bl_idname = "rzm.set_active_slot"
    bl_label = "Set Active Slot"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index].active_slot_index = self.index
        return {'FINISHED'}

class RZM_OT_SetTwActiveLayer(bpy.types.Operator):
    bl_idname = "rzm.set_tw_active_layer"
    bl_label = "Set Active Layer"
    bl_options = {'REGISTER', 'UNDO'}
    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()
    index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index].active_layer_index = self.index
        return {'FINISHED'}

class RZM_OT_MoveTwItem(bpy.types.Operator):
    """Generic operator to move a TexWorks collection item up or down."""
    bl_idname = "rzm.move_tw_item"
    bl_label = "Move TexWorks Item"
    bl_options = {'REGISTER', 'UNDO'}
    
    collection_name: bpy.props.StringProperty()
    index: bpy.props.IntProperty()
    direction: bpy.props.EnumProperty(items=[('UP', "Up", ""), ('DOWN', "Down", "")])
    
    # Hierarchy path
    block_index: bpy.props.IntProperty(default=-1)
    comp_index: bpy.props.IntProperty(default=-1)
    slot_index: bpy.props.IntProperty(default=-1)
    
    def execute(self, context):
        rzm = context.scene.rzm
        try:
            if self.collection_name == "resources":
                coll = rzm.tw_resources
            elif self.collection_name == "overrides":
                coll = rzm.tw_overrides
            elif self.collection_name == "override_bindings":
                coll = rzm.tw_overrides[self.block_index].bindings
            elif self.collection_name == "materials":
                coll = rzm.tw_materials
            elif self.collection_name == "blocks":
                coll = rzm.tw_blocks
            elif self.collection_name == "components":
                coll = rzm.tw_blocks[self.block_index].components
            elif self.collection_name == "slots":
                coll = rzm.tw_blocks[self.block_index].components[self.comp_index].slots
            elif self.collection_name == "decal_layers":
                coll = rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index].decal_layers
            else:
                return {'CANCELLED'}
            
            target_idx = self.index - 1 if self.direction == 'UP' else self.index + 1
            if 0 <= target_idx < len(coll):
                coll.move(self.index, target_idx)
                
        except (AttributeError, IndexError) as e:
            print(f"MoveTwItem Error: {e}")
            return {'CANCELLED'}
            
        return {'FINISHED'}

def create_dummy_png(path, width=1, height=1, color=(255, 0, 0, 128)):
    """Creates an empty PNG file of the requested size and color."""
    import struct
    import zlib

    # PNG Signature
    png_sig = b'\x89PNG\r\n\x1a\n'
    
    # IHDR chunk
    ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff)
    
    # IDAT chunk
    # Row filter + pixels
    r, g, b, a = color
    pixel = struct.pack('BBBB', r, g, b, a)
    row = b'\x00' + (pixel * width)
    pixel_data = row * height
    compressed_data = zlib.compress(pixel_data)
    idat_chunk = struct.pack('>I', len(compressed_data)) + b'IDAT' + compressed_data + struct.pack('>I', zlib.crc32(b'IDAT' + compressed_data) & 0xffffffff)
    
    # IEND chunk
    iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', zlib.crc32(b'IEND') & 0xffffffff)
    
    try:
        with open(path, 'wb') as f:
            f.write(png_sig + ihdr_chunk + idat_chunk + iend_chunk)
        return True
    except Exception as e:
        print(f"Error creating dummy PNG: {e}")
        return False

class RZ_OT_TexWorksExportHierarchy(bpy.types.Operator):
    """Exports the folder hierarchy and generates PNG placeholders for TexWorks."""
    bl_idname = "rzm.tw_export_hierarchy"
    bl_label = "Export TexWorks Hierarchy"
    bl_description = "Creates a folder structure and PNG files from TexWorks settings"

    def execute(self, context):
        rzm = context.scene.rzm
        target_path = get_target_path(context)
        
        if not target_path:
            self.report({'ERROR'}, "Mod path not set! Check Export Manager settings.")
            return {'CANCELLED'}

        base_dir = os.path.join(target_path, "TexWorks")
        if not os.path.exists(base_dir):
            os.makedirs(base_dir, exist_ok=True)
            
        created_folders = 0
        created_files = 0
        created_masks = 0

        for block in rzm.tw_blocks:
            # RZM_TW_EXPORT_OPT: Skip blocks that use shared textures
            if block.use_shared_textures:
                continue

            block_dir = os.path.join(base_dir, block.name)
            
            for comp in block.components:
                comp_dir = os.path.join(block_dir, comp.name)
                
                # RZM_TW_EXPORT_OPT: Create mask.png ONLY if mask_enabled or hsv_mask_enabled
                if comp.mask_enabled or comp.hsv_mask_enabled:
                    if not os.path.exists(comp_dir):
                        os.makedirs(comp_dir, exist_ok=True)
                        created_folders += 1
                    
                    mask_path = os.path.join(comp_dir, "mask.png")
                    if not os.path.exists(mask_path):
                        # Use component rect for mask size
                        if create_dummy_png(mask_path, comp.rect[2], comp.rect[3]):
                            created_masks += 1

                for slot in comp.slots:
                    slot_dir = os.path.join(comp_dir, slot.name)
                    
                    # RZM_TW_EXPORT_OPT: Check if slot needs a mask or has layers
                    has_layers = any(l.active for l in slot.decal_layers)
                    
                    if slot.mask_enabled or slot.hsv_mask_enabled or has_layers:
                        if not os.path.exists(slot_dir):
                            os.makedirs(slot_dir, exist_ok=True)
                            created_folders += 1

                    if slot.mask_enabled or slot.hsv_mask_enabled:
                        clean_comp = comp.name.replace(" ","")
                        clean_slot = slot.name.replace(" ","")
                        mask_name = f"{clean_comp}{clean_slot}.MASK.png"
                        mask_path = os.path.join(slot_dir, mask_name)
                        
                        if not os.path.exists(mask_path):
                            if create_dummy_png(mask_path, slot.rect[2], slot.rect[3]):
                                created_masks += 1

                    for layer in slot.decal_layers:
                        if not layer.active: continue
                        
                        layer_dir = os.path.join(slot_dir, layer.name)
                        if not os.path.exists(layer_dir):
                            os.makedirs(layer_dir, exist_ok=True)
                            created_folders += 1
                        
                        for i in range(layer.count):
                            file_path = os.path.join(layer_dir, f"{i}.png")
                            if not os.path.exists(file_path):
                                if create_dummy_png(file_path, slot.rect[2], slot.rect[3]):
                                    created_files += 1

        self.report({'INFO'}, f"TexWorks Export: {created_folders} folders, {created_files} files, {created_masks} masks created.")
        return {'FINISHED'}

class RZM_OT_TwCreateEasyMask(bpy.types.Operator):
    """Generates a mask (red on black) from the selected UVs."""
    bl_idname = "rzm.tw_create_easy_mask"
    bl_label = "Easy Mask"
    bl_options = {'REGISTER', 'UNDO'}

    block_idx: bpy.props.IntProperty()
    comp_idx: bpy.props.IntProperty()
    slot_idx: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        import numpy as np
        import gpu
        from gpu_extras.batch import batch_for_shader
        from ..utils.texworks_calc import calculate_slot_config


        rzm = context.scene.rzm
        try:
            block = rzm.tw_blocks[self.block_idx]
            comp = block.components[self.comp_idx]
            item = comp if self.slot_idx == -1 else comp.slots[self.slot_idx]
        except IndexError:
            return {'CANCELLED'}

        # Находим путь для сохранения
        target_path = get_target_path(context)
        if not target_path:
            self.report({'ERROR'}, "Mod path not set!")
            return {'CANCELLED'}

        comp_dir = os.path.join(target_path, "TexWorks", block.name, comp.name)
        if self.slot_idx == -1:
            filepath = os.path.join(comp_dir, "mask.png")
        else:
            slot_name = item.name
            clean_comp = comp.name.replace(" ", "")
            clean_slot = slot_name.replace(" ", "")
            filepath = os.path.join(comp_dir, slot_name, f"{clean_comp}{clean_slot}.MASK.png")

        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        # Размеры для экспорта (всегда на основе компонента)
        comp_width, comp_height = int(comp.rect[2]), int(comp.rect[3])
        if comp_width <= 0 or comp_height <= 0:
            comp_width, comp_height = 2048, 2048

        # Для слотов вычисляем область автоматически (игнорируя враппинг)
        if self.slot_idx != -1:
            obj = context.active_object
            if not obj or obj.type != 'MESH':
                self.report({'ERROR'}, "Select the target mesh for Slot UV calculation")
                return {'CANCELLED'}
            
            result = calculate_slot_config(obj, comp_width, comp_height, padding=0)
            if not result:
                self.report({'ERROR'}, "Failed to calculate the UV zone for the slot (no selection?)")
                return {'CANCELLED'}
            
            # Обновляем rect слота (игнорируем lattice)
            item.rect = result[0]
        
        # Временный файл для экспорта UV
        import tempfile
        temp_dir = tempfile.gettempdir()
        temp_export = os.path.join(temp_dir, "rzm_uv_export.png")

        try:
            bpy.ops.uv.export_layout(
                filepath=temp_export,
                export_all=False,
                mode='PNG',
                size=(comp_width, comp_height),
                opacity=1.0
            )
        except Exception as e:
            self.report({'ERROR'}, f"Failed to export UV layout: {e}")
            return {'CANCELLED'}

        # Пост-процессинг через Blender Image + NumPy (R8 Mask + Crop)
        try:
            # Загружаем временный файл
            tmp_img = bpy.data.images.load(temp_export, check_existing=True)
            tmp_img.colorspace_settings.name = 'Non-Color'
            
            # Работаем с пикселями (RGBA Float)
            w, h = tmp_img.size
            pixels = np.array(tmp_img.pixels)
            pixels = pixels.reshape((h, w, 4))
            
            # RZM_R8_LOGIC: Alpha -> Red, G=0, B=0, A=1.0
            # У свежего экспорта Blender UV: фон прозрачный (Alpha=0), линии непрозрачные (Alpha>0)
            alpha_channel = pixels[:, :, 3].copy()
            new_pixels = np.zeros_like(pixels)
            new_pixels[:, :, 0] = alpha_channel # Red = Alpha
            new_pixels[:, :, 3] = 1.0           # Alpha = 1.0 (Solid Black background)
            
            # Если это слот - обрезаем
            if self.slot_idx != -1:
                sx, sy, sw, sh = item.rect
                # Blender Image координаты Y идут снизу вверх
                # item.rect Y идет сверху вниз
                y_start = h - (sy + sh)
                y_end = h - sy
                x_start = sx
                x_end = sx + sw
                
                # Защита от выхода за границы
                y_start = max(0, min(h, int(y_start)))
                y_end = max(0, min(h, int(y_end)))
                x_start = max(0, min(w, int(x_start)))
                x_end = max(0, min(w, int(x_end)))
                
                new_pixels = new_pixels[y_start:y_end, x_start:x_end]
                final_w, final_h = x_end - x_start, y_end - y_start
            else:
                final_w, final_h = w, h

            # Создаем/Обновляем результирующее изображение
            img_name = os.path.basename(filepath)
            img = bpy.data.images.get(img_name)
            if img: bpy.data.images.remove(img)
            
            img = bpy.data.images.new(img_name, final_w, final_h, alpha=True)
            img.pixels = new_pixels.flatten()
            img.filepath_raw = filepath
            img.file_format = 'PNG'
            img.save()
            
            # Очистка
            bpy.data.images.remove(tmp_img)
            if os.path.exists(temp_export): os.remove(temp_export)
            
        except Exception as e:
            self.report({'ERROR'}, f"Failed to post-process mask: {e}")
            import traceback
            traceback.print_exc()
            return {'CANCELLED'}

        # Копирование в буфер обмена (Windows Only 64-bit safe method)

        # Копирование в буфер обмена (Windows Only 64-bit safe method from UvTEX(2048).py)
        try:
             import ctypes
             from ctypes import wintypes
             
             CF_PNG = ctypes.windll.user32.RegisterClipboardFormatW("PNG")
             with open(filepath, "rb") as f:
                 png_bytes = f.read()
             
             user32 = ctypes.windll.user32
             kernel32 = ctypes.windll.kernel32
             
             # Явное определение типов для 64-битной совместимости
             kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
             kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
             kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
             kernel32.GlobalLock.restype = wintypes.LPVOID
             kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
             kernel32.GlobalFree.argtypes = [wintypes.HGLOBAL]
             user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
             user32.SetClipboardData.restype = wintypes.HANDLE
             
             GMEM_MOVEABLE = 0x0002
             GMEM_ZEROINIT = 0x0040
             
             hCd = kernel32.GlobalAlloc(GMEM_MOVEABLE | GMEM_ZEROINIT, len(png_bytes))
             if not hCd:
                 raise Exception("GlobalAlloc failed")
             
             pBuf = kernel32.GlobalLock(hCd)
             if not pBuf:
                 kernel32.GlobalFree(hCd)
                 raise Exception("GlobalLock failed")
             
             try:
                 ctypes.memmove(pBuf, png_bytes, len(png_bytes))
             finally:
                 kernel32.GlobalUnlock(hCd)
             
             if not user32.OpenClipboard(None):
                 kernel32.GlobalFree(hCd)
                 raise Exception("OpenClipboard failed")
             
             try:
                 user32.EmptyClipboard()
                 if not user32.SetClipboardData(CF_PNG, hCd):
                     kernel32.GlobalFree(hCd)
                     raise Exception("SetClipboardData failed")
                 hCd = None # Sysem now owns the memory
             finally:
                 user32.CloseClipboard()
             
             if hCd:
                 kernel32.GlobalFree(hCd)

             self.report({'INFO'}, f"Mask saved to {filepath} and copied to clipboard!")
        except Exception as e:
             self.report({'INFO'}, f"Mask saved to {filepath} (Clipboard failed: {e})")

        return {'FINISHED'}

class RZ_OT_TexWorksDebugSync(bpy.types.Operator):
    """Prints the TexWorks hierarchy to the console."""
    bl_idname = "rzm.tw_debug_sync"
    bl_label = "Debug TexWorks Sync"
    bl_description = "Prints TexWorks data to the console for debugging"

    def execute(self, context):
        rzm = context.scene.rzm
        target_path = get_target_path(context)
        
        print("\n" + "="*50)
        print("TEXWORKS DATA SYNC DEBUG (BLENDER DATA)")
        print("="*50)

        for b_idx, block in enumerate(rzm.tw_blocks):
            print(f"Block [{b_idx}]: {block.name} (Shader: {block.shader_type}, Resource: {block.resource_name})")
            for c_idx, comp in enumerate(block.components):
                print(f"  Component [{c_idx}]: {comp.name}")
                for s_idx, slot in enumerate(comp.slots):
                    print(f"    Slot [{s_idx}]: {slot.name} (Active: {slot.active}, Rect: {list(slot.rect)})")
                    for l_idx, layer in enumerate(slot.decal_layers):
                        print(f"      Layer [{l_idx}]: {layer.name} (Index: {layer.index}, Count: {layer.count})")
        
        if target_path:
            base_dir = os.path.join(target_path, "TexWorks")
            if os.path.exists(base_dir):
                print("\n" + "="*50)
                print("TEXWORKS DATA SYNC DEBUG (PHYSICAL DATA)")
                print("="*50)
                
                # Scan and group
                theoretical_structure = {} # {Block: {Component: {Slot: [Layers]}}}
                
                # First level: Masks in root
                masks = [f for f in os.listdir(base_dir) if f.endswith("Mask.png")]
                if masks:
                    print("Root Masks found:")
                    for m in masks: print(f"  - {m}")
                
                # Walk blocks
                for block_name in [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]:
                    block_path = os.path.join(base_dir, block_name)
                    theoretical_structure[block_name] = {}
                    
                    for comp_name in [d for d in os.listdir(block_path) if os.path.isdir(os.path.join(block_path, d))]:
                        comp_path = os.path.join(block_path, comp_name)
                        theoretical_structure[block_name][comp_name] = {}
                        
                        for slot_name in [d for d in os.listdir(comp_path) if os.path.isdir(os.path.join(comp_path, d))]:
                            slot_path = os.path.join(comp_path, slot_name)
                            theoretical_structure[block_name][comp_name][slot_name] = {}
                            
                            for layer_name in [d for d in os.listdir(slot_path) if os.path.isdir(os.path.join(slot_path, d))]:
                                layer_path = os.path.join(slot_path, layer_name)
                                files = os.listdir(layer_path)
                                theoretical_structure[block_name][comp_name][slot_name][layer_name] = files

                # Print grouped structure
                for b_name, comps in theoretical_structure.items():
                    print(f"Block: {b_name}")
                    for c_name, slots in comps.items():
                        print(f"  Component: {c_name}")
                        for s_name, layers in slots.items():
                            print(f"    Slot: {s_name}")
                            for l_name, files in layers.items():
                                print(f"      Folder/Layer: {l_name} ({len(files)} files)")
                            # Optimization: just count files to avoid console spam if there are many
        
        print("="*50 + "\n")
        self.report({'INFO'}, "TexWorks data printed to console.")
        return {'FINISHED'}

class RZM_OT_CalcSlotConfig(bpy.types.Operator):
    bl_idname = "rzm.calc_slot_config"
    bl_label = "Calculate Slot Config"
    bl_options = {'REGISTER', 'UNDO'}

    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()
    target_pass: bpy.props.IntProperty(default=0) # 0 = Pass 0, 1 = Pass 1

    def execute(self, context):
        from ..utils.texworks_calc import calculate_slot_config
        rzm = context.scene.rzm
        try:
            slot = rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index]
        except IndexError:
            self.report({'ERROR'}, "Invalid Slot selection")
            return {'CANCELLED'}

        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a Mesh object")
            return {'CANCELLED'}

        res_x = slot.calc_res_x
        res_y = slot.calc_res_y
        padding = slot.calc_padding
        
        result = calculate_slot_config(obj, res_x, res_y, padding)
        
        if not result:
            self.report({'ERROR'}, "Calculation failed (check selection)")
            return {'CANCELLED'}

        rect, lattice = result
        
        if self.target_pass == 0:
            slot.rect = rect
            slot.warp_p0_enabled = True
            slot.warp_p0_grid = lattice
        else:
            slot.multi_pass_rect = rect
            slot.warp_p1_enabled = True
            slot.warp_p1_grid = lattice

        self.report({'INFO'}, f"Calculated Pass {self.target_pass} for {slot.name}")
        return {'FINISHED'}

class RZM_OT_SetSlotCalcRes(bpy.types.Operator):
    bl_idname = "rzm.set_slot_calc_res"
    bl_label = "Set Calc Resolution"
    bl_options = {'REGISTER', 'UNDO'}

    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()
    res: bpy.props.IntProperty()

    def execute(self, context):
        rzm = context.scene.rzm
        try:
            slot = rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index]
            slot.calc_res_x = self.res
            slot.calc_res_y = self.res
        except IndexError:
            pass
        return {'FINISHED'}

class RZM_OT_CalcSplittedIslandConfig(bpy.types.Operator):
    bl_idname = "rzm.calc_splitted_island_config"
    bl_label = "Calculate Splitted Island (Exp)"
    bl_options = {'REGISTER', 'UNDO'}

    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        from ..utils.texworks_calc import calculate_seamless_split_config
        rzm = context.scene.rzm
        try:
            slot = rzm.tw_blocks[self.block_index].components[self.comp_index].slots[self.slot_index]
        except IndexError:
            self.report({'ERROR'}, "Invalid Slot selection")
            return {'CANCELLED'}

        obj = context.active_object
        if not obj or obj.type != 'MESH':
            self.report({'ERROR'}, "Select a Mesh object")
            return {'CANCELLED'}

        # Параметры слота
        res_x = slot.calc_res_x
        res_y = slot.calc_res_y
        padding = slot.calc_padding

        # Вызываем новый умный алгоритм
        # Он вернет данные сразу для ДВУХ проходов
        result = calculate_seamless_split_config(obj, res_x, res_y, padding)

        if not result:
            self.report({'ERROR'}, "Error: Select exactly 2 UV Islands/Linked Faces")
            return {'CANCELLED'}

        pass0_data, pass1_data = result

        # Применяем данные
        # PASS 0 (Левая/Первая часть)
        slot.rect = pass0_data['rect']
        slot.warp_p0_enabled = True
        slot.warp_p0_grid = pass0_data['lattice']

        # PASS 1 (Правая/Вторая часть)
        slot.multi_pass_rect = pass1_data['rect']
        slot.warp_p1_enabled = True
        slot.warp_p1_grid = pass1_data['lattice']

        self.report({'INFO'}, f"Calculated Seamless Split: Ratio {pass0_data['ratio']:.2f} / {pass1_data['ratio']:.2f}")
        return {'FINISHED'}

class RZM_OT_RescaleActiveTwBlock(bpy.types.Operator):
    bl_idname = "rzm.rescale_active_tw_block"
    bl_label = "Rescale Active Block Rects"
    bl_description = "Rescale all TexWorks pixel rects in the active block from old texture resolution to new resolution"
    bl_options = {'REGISTER', 'UNDO'}

    old_resolution: bpy.props.IntProperty(name="Old Resolution", default=1024, min=1)
    new_resolution: bpy.props.IntProperty(name="New Resolution", default=2048, min=1)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        rzm = context.scene.rzm
        b_idx = rzm.active_tw_block_index
        if b_idx < 0 or b_idx >= len(rzm.tw_blocks):
            self.report({'ERROR'}, "No active TexWorks block")
            return {'CANCELLED'}

        scale = self.new_resolution / self.old_resolution
        block = rzm.tw_blocks[b_idx]
        changed = 0

        def scale_rect(owner, prop_name):
            nonlocal changed
            rect = list(getattr(owner, prop_name))
            scaled = [int(round(v * scale)) for v in rect]
            if rect != scaled:
                setattr(owner, prop_name, scaled)
                changed += 1

        scale_rect(block, "backdrop_rect")
        for comp in block.components:
            scale_rect(comp, "base_rect")
            scale_rect(comp, "rect")
            for slot in comp.slots:
                if slot.stencil_mode == 'RECT':
                    scale_rect(slot, "rect")
                    scale_rect(slot, "multi_pass_rect")
                else:
                    slot.sparse_has_baked = False
                slot.calc_res_x = self.new_resolution
                slot.calc_res_y = self.new_resolution

        trigger_refresh()
        self.report(
            {'INFO'},
            f"Rescaled active TexWorks block '{block.name}' {self.old_resolution}->{self.new_resolution}; rects changed: {changed}"
        )
        return {'FINISHED'}

class RZM_OT_BakeSparseStencil(bpy.types.Operator):
    bl_idname = "rzm.bake_sparse_stencil"
    bl_label = "Bake Sparse Decal Stencil"
    bl_description = "Bake selected mesh faces into a packed structured CS buffer using evaluated geometry"
    bl_options = {"REGISTER", "UNDO"}

    block_index: bpy.props.IntProperty()
    comp_index: bpy.props.IntProperty()
    slot_index: bpy.props.IntProperty()

    def execute(self, context):
        rzm = context.scene.rzm
        try:
            block = rzm.tw_blocks[self.block_index]
            comp = block.components[self.comp_index]
            slot = comp.slots[self.slot_index]
        except IndexError:
            self.report({"ERROR"}, "Invalid Slot selection")
            return {"CANCELLED"}

        source_object = context.active_object
        if source_object is None or source_object.type != "MESH":
            self.report({"ERROR"}, "Select an active mesh object")
            return {"CANCELLED"}

        # Get original mesh and check face selection
        orig_mesh = source_object.data
        if source_object.mode == "EDIT":
            source_object.update_from_editmode()

        orig_selected = {p.index for p in orig_mesh.polygons if p.select}
        if not orig_selected:
            self.report({"ERROR"}, "Select at least one mesh face on the active object")
            return {"CANCELLED"}

        try:
            # 1. Setup target paths
            target_path = get_target_path(context)
            if not target_path:
                self.report({"ERROR"}, "Active mod target path not set. Check XXMI settings.")
                return {"CANCELLED"}

            destination = os.path.join(target_path, "TexWorks", "DecalStencils")
            os.makedirs(destination, exist_ok=True)

            from ..utils.sparse_baker import (
                _safe_export_name,
                _make_uv_reader,
                _selection_diagnostics,
                _build_virtual_decal_uv,
                _build_occupancy,
                _build_core_records,
                _add_padding_records,
                _write_buffer,
            )

            export_name = _safe_export_name(slot.name)

            buffer_filename = f"{export_name}.buf"
            json_filename = f"{export_name}.json"
            buffer_path = os.path.join(destination, buffer_filename)
            json_path = os.path.join(destination, json_filename)

            # 2. Extract evaluated mesh using depsgraph
            depsgraph = context.evaluated_depsgraph_get()
            eval_obj = source_object.evaluated_get(depsgraph)
            source_mesh = eval_obj.to_mesh()

            # Map original face selection to evaluated mesh faces using original_index
            selected_faces = []
            for p in source_mesh.polygons:
                orig_idx = getattr(p, "original_index", -1)
                if orig_idx == -1 or orig_idx >= len(orig_mesh.polygons):
                    orig_idx = p.index
                if orig_idx in orig_selected:
                    selected_faces.append(p.index)

            if not selected_faces:
                # Fallback: check evaluated face selections
                selected_faces = [p.index for p in source_mesh.polygons if p.select]

            if not selected_faces:
                raise RuntimeError("No faces found on the evaluated mesh. Try modifying selection or modifiers.")

            # 3. Read target UV Map
            uv_name = orig_mesh.uv_layers.active.name if orig_mesh.uv_layers.active else ""
            if not uv_name:
                raise RuntimeError("Mesh has no active UV Map")

            read_target_uv, uv_reader_metadata = _make_uv_reader(source_mesh, uv_name)

            diagnostics = _selection_diagnostics(source_mesh, selected_faces)
            virtual_uv_by_loop, unwrap_metadata = _build_virtual_decal_uv(
                source_mesh,
                selected_faces,
                slot.sparse_mapping_method,
            )

            # Use slot.calc_res_x / calc_res_y as atlas dimensions
            width = slot.calc_res_x
            height = slot.calc_res_y

            occupancy, all_degenerate_triangles, clipped_triangles = _build_occupancy(
                source_mesh,
                read_target_uv,
                width,
                height,
                slot.sparse_flip_target_v,
            )

            core_records, core_metadata = _build_core_records(
                source_mesh,
                read_target_uv,
                virtual_uv_by_loop,
                selected_faces,
                width,
                height,
                slot.sparse_flip_target_v,
                slot.sparse_flip_decal_v,
            )

            if not core_records:
                raise RuntimeError("Selected faces produced zero atlas texels. Check resolution and target UV Map.")

            padding_records = _add_padding_records(
                core_records,
                occupancy,
                width,
                height,
                slot.sparse_padding_pixels,
            )

            all_records = dict(core_records)
            all_records.update(padding_records)

            # 4. Write binary buffer
            _write_buffer(buffer_path, all_records, width, height)

            # 5. Build warnings
            warnings = []
            if diagnostics["connected_components"] > 1:
                warnings.append("Selection has multiple disconnected components.")
            if diagnostics["closed_components"] > 0:
                warnings.append("Selection contains a closed component without a boundary.")
            if clipped_triangles > 0:
                warnings.append("Some target UV triangles leave the 0..1 atlas range and were clipped.")
            if core_metadata["conflicting_target_texels"] > 0:
                warnings.append("Target UV overlap detected inside the stencil.")

            # 6. Write JSON metadata
            metadata = {
                "format_version": 1,
                "algorithm": "selected_faces_virtual_unwrap_to_sparse_atlas_texels",
                "record_layout": ["target_x_float", "target_y_float", "decal_u", "decal_v"],
                "record_stride_bytes": 16,
                "shader_resource_format": "R32G32B32A32_FLOAT",
                "object": source_object.name,
                "target_uv": uv_name,
                "atlas_size": [width, height],
                "flip_target_v": slot.sparse_flip_target_v,
                "flip_decal_v": slot.sparse_flip_decal_v,
                "unwrap_method": slot.sparse_mapping_method,
                "selected_face_count": len(selected_faces),
                "core_record_count": len(core_records),
                "padding_record_count": len(padding_records),
                "record_count": len(all_records),
                "selection_diagnostics": diagnostics,
                "warnings": warnings,
            }
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            # 7. Update slot stats cached properties
            slot.sparse_record_count = len(all_records)
            slot.sparse_file_size = os.path.getsize(buffer_path) / 1024.0
            
            # Find bounds
            min_x, min_y = width, height
            max_x, max_y = -1, -1
            for index in all_records.keys():
                x = index % width
                y = index // width
                if x < min_x: min_x = x
                if y < min_y: min_y = y
                if x > max_x: max_x = x
                if y > max_y: max_y = y

            slot.sparse_bbox_min = (min_x, min_y)
            slot.sparse_bbox_max = (max_x, max_y)
            slot.sparse_has_baked = True

            # Clean up the evaluated mesh
            eval_obj.to_mesh_clear()

            trigger_refresh()
            self.report({"INFO"}, f"Baked {len(all_records)} sparse records successfully.")
            return {"FINISHED"}

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.report({"ERROR"}, f"Bake failed: {e}")
            return {"CANCELLED"}

classes_to_register = [
    RZM_OT_UpdateTwItem,
    RZM_OT_AddTwResource, RZM_OT_RemoveTwResource,
    RZM_OT_AddTwOverride, RZM_OT_RemoveTwOverride,
    RZM_OT_AddTwOverrideBinding, RZM_OT_RemoveTwOverrideBinding,
    RZM_OT_AddTwMaterial, RZM_OT_RemoveTwMaterial, RZM_OT_TwSelectMaterial,

    RZM_OT_AddTwBlock, RZM_OT_RemoveTwBlock, RZM_OT_DuplicateTwBlock, RZM_OT_SetActiveBlock,
    RZM_OT_AddTwComponent, RZM_OT_RemoveTwComponent, RZM_OT_SetActiveComponent,
    RZM_OT_AddTwSlot, RZM_OT_RemoveTwSlot, RZM_OT_SetActiveSlot,
    RZM_OT_AddTwDecalLayer, RZM_OT_RemoveTwDecalLayer, RZM_OT_SetTwActiveLayer, RZM_OT_MoveTwItem,
    RZM_OT_CalcSlotConfig,
    RZM_OT_SetSlotCalcRes,
    RZM_OT_CalcSplittedIslandConfig,
    RZM_OT_RescaleActiveTwBlock,
    RZM_OT_BakeSparseStencil,
    RZM_OT_TwCreateEasyMask,
    RZM_OT_ClearTwResources, RZM_OT_ClearTwOverrides, RZM_OT_TwResOverFill,
    RZ_OT_TexWorksExportHierarchy, RZ_OT_TexWorksDebugSync
]
