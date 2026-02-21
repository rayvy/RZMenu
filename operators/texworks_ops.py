# RZMenu/operators/texworks_ops.py
import bpy
import os
from .export_manager import get_target_path

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

from ..utils.texworks_calc import calculate_slot_config, calculate_seamless_split_config

class RZM_OT_SetActiveBlock(bpy.types.Operator):
    bl_idname = "rzm.set_active_block"
    bl_label = "Set Active Block"
    bl_options = {'REGISTER', 'UNDO'}
    index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.active_tw_block_index = self.index
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
    """Создает пустой PNG файл заданного размера и цвета."""
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
    """Экспортирует иерархию папок и генерирует PNG заглушки для TexWorks."""
    bl_idname = "rzm.tw_export_hierarchy"
    bl_label = "Export TexWorks Hierarchy"
    bl_description = "Создает структуру папок и PNG файлы на основе настроек TexWorks"

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
            block_dir = os.path.join(base_dir, block.name)
            block_res_name = block.resource_name or block.name

            for comp in block.components:
                comp_dir = os.path.join(block_dir, comp.name)
                
                for slot in comp.slots:
                    slot_dir = os.path.join(comp_dir, slot.name)
                    if not os.path.exists(slot_dir):
                        os.makedirs(slot_dir, exist_ok=True)
                        created_folders += 1

                    # Create mask in slot folder
                    # Naming: [CompName][SlotName].MASK.png (compressed)
                    clean_comp = comp.name.replace(" ","")
                    clean_slot = slot.name.replace(" ","")
                    mask_name = f"{clean_comp}{clean_slot}.MASK.png"
                    mask_path = os.path.join(slot_dir, mask_name)
                    
                    if not os.path.exists(mask_path):
                        # Mask size matches component rect
                        if create_dummy_png(mask_path, comp.rect[2], comp.rect[3]):
                            created_masks += 1

                    for layer in slot.decal_layers:
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

class RZ_OT_TexWorksDebugSync(bpy.types.Operator):
    """Выводит иерархию TexWorks в консоль."""
    bl_idname = "rzm.tw_debug_sync"
    bl_label = "Debug TexWorks Sync"
    bl_description = "Выводит данные TexWorks в консоль для отладки"

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

classes_to_register = [
    RZM_OT_UpdateTwItem,
    RZM_OT_AddTwResource, RZM_OT_RemoveTwResource,
    RZM_OT_AddTwOverride, RZM_OT_RemoveTwOverride,
    RZM_OT_AddTwMaterial, RZM_OT_RemoveTwMaterial,
    RZM_OT_AddTwBlock, RZM_OT_RemoveTwBlock, RZM_OT_SetActiveBlock,
    RZM_OT_AddTwComponent, RZM_OT_RemoveTwComponent, RZM_OT_SetActiveComponent,
    RZM_OT_AddTwSlot, RZM_OT_RemoveTwSlot, RZM_OT_SetActiveSlot,
    RZM_OT_AddTwDecalLayer, RZM_OT_RemoveTwDecalLayer, RZM_OT_SetTwActiveLayer, RZM_OT_MoveTwItem,
    RZM_OT_CalcSlotConfig,
    RZM_OT_SetSlotCalcRes,
    RZM_OT_CalcSplittedIslandConfig,
    RZ_OT_TexWorksExportHierarchy, RZ_OT_TexWorksDebugSync
]
