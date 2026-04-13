# RZMenu/operators/blend_resize_ops.py
import bpy
import os
import struct
from ..core.utils import get_next_available_id

# --- Operators for Layer/Bone UI Management ---

class RZM_OT_BRAddGroup(bpy.types.Operator):
    bl_idname = "rzm.br_add_group"
    bl_label = "Add Group"
    def execute(self, context):
        context.scene.rzm.addons.blend_resize.groups.add()
        return {'FINISHED'}

class RZM_OT_BRRemoveGroup(bpy.types.Operator):
    bl_idname = "rzm.br_remove_group"
    bl_label = "Remove Group"
    index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm.addons.blend_resize.groups.remove(self.index)
        return {'FINISHED'}

class RZM_OT_BRAddComp(bpy.types.Operator):
    bl_idname = "rzm.br_add_comp"
    bl_label = "Add Component"
    def execute(self, context):
        context.scene.rzm.addons.blend_resize.component_mappings.add()
        return {'FINISHED'}

class RZM_OT_BRRemoveComp(bpy.types.Operator):
    bl_idname = "rzm.br_remove_comp"
    bl_label = "Remove Component"
    index: bpy.props.IntProperty()
    def execute(self, context):
        br = context.scene.rzm.addons.blend_resize
        br.component_mappings.remove(self.index)
        if context.scene.rzm_active_br_comp_index >= len(br.component_mappings):
            context.scene.rzm_active_br_comp_index = len(br.component_mappings) - 1
        return {'FINISHED'}

class RZM_OT_BRSelectComp(bpy.types.Operator):
    bl_idname = "rzm.br_select_comp"
    bl_label = "Select Component"
    index: bpy.props.IntProperty()
    def execute(self, context):
        context.scene.rzm_active_br_comp_index = self.index
        return {'FINISHED'}

# --- Layer Management ---
class RZM_OT_BRAddLayer(bpy.types.Operator):
    bl_idname = "rzm.br_add_layer"
    bl_label = "Add Empty Layer"
    def execute(self, context):
        br = context.scene.rzm.addons.blend_resize
        comp = br.component_mappings[context.scene.rzm_active_br_comp_index]
        comp.layers.add()
        return {'FINISHED'}

class RZM_OT_BRRemoveLayer(bpy.types.Operator):
    bl_idname = "rzm.br_remove_layer"
    bl_label = "Remove Layer"
    comp_index: bpy.props.IntProperty(default=-1)
    layer_index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        br = context.scene.rzm.addons.blend_resize
        comp = br.component_mappings[self.comp_index]
        comp.layers.remove(self.layer_index)
        return {'FINISHED'}

class RZM_OT_BRAddLayerBone(bpy.types.Operator):
    bl_idname = "rzm.br_add_layer_bone"
    bl_label = "Add Bone to Layer"
    comp_index: bpy.props.IntProperty(default=-1)
    layer_index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        br = context.scene.rzm.addons.blend_resize
        comp = br.component_mappings[self.comp_index]
        layer = comp.layers[self.layer_index]
        layer.bones.add()
        layer.bone_count = len(layer.bones)
        return {'FINISHED'}

class RZM_OT_BRRemoveLayerBone(bpy.types.Operator):
    bl_idname = "rzm.br_remove_layer_bone"
    bl_label = "Remove Bone"
    comp_index: bpy.props.IntProperty(default=-1)
    layer_index: bpy.props.IntProperty(default=-1)
    bone_index: bpy.props.IntProperty(default=-1)
    def execute(self, context):
        br = context.scene.rzm.addons.blend_resize
        comp = br.component_mappings[self.comp_index]
        layer = comp.layers[self.layer_index]
        layer.bones.remove(self.bone_index)
        layer.bone_count = len(layer.bones)
        return {'FINISHED'}

def remap_pos(v, game):
    return (-v.x, v.z, v.y) if game in ["GenshinImpact", "ZenlessZoneZero", "HonkaiStarRail"] else (v.x, v.y, v.z)

class RZM_OT_BRBakeLayer(bpy.types.Operator):
    bl_idname = "rzm.br_bake_layer"
    bl_label = "Bake from Selected Bones"
    bl_description = "Bake selected pose bones into a new layer for the active component"
    comp_index: bpy.props.IntProperty(default=-1)

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'ARMATURE' and context.selected_pose_bones

    def execute(self, context):
        obj = context.active_object
        selected = context.selected_pose_bones
        
        active_bone = context.active_pose_bone
        if not active_bone or active_bone not in selected:
            active_bone = selected[0]

        head = active_bone.bone.head_local
        mat = active_bone.bone.matrix_local.to_3x3()
        x_axis = mat.col[0]
        y_axis = mat.col[1]

        game = context.scene.rzm.game.selection
        g_head = remap_pos(head, game)
        g_x_axis = remap_pos(x_axis, game)
        g_y_axis = remap_pos(y_axis, game)

        valid_bones = [pb for pb in selected if pb.name.isdigit()]
        count = len(valid_bones)

        if count == 0:
            self.report({'WARNING'}, "No bone names consisting only of digits found.")
            return {'CANCELLED'}

        br = context.scene.rzm.addons.blend_resize
        comp = br.component_mappings[self.comp_index]
        
        # Smart Bake Layer Look-up
        layer = None
        for l in comp.layers:
            if l.name == active_bone.name:
                layer = l
                break
                
        if layer is None:
            layer = comp.layers.add()
            layer.name = active_bone.name
            layer.slot_id = 0 # Default to 0, user can change manually in UI
            
        layer.head_mapped = g_head
        layer.bone_x_mapped = g_x_axis
        layer.bone_y_mapped = g_y_axis

        for pb in valid_bones:
            b_idx = int(pb.name)
            
            # Check if bone already exists
            bone_obj = None
            for b in layer.bones:
                if b.bone_index == b_idx:
                    bone_obj = b
                    break
                    
            if bone_obj is None:
                bone_obj = layer.bones.add()
                bone_obj.bone_index = b_idx
                
            # Apply transforms in pure local bone space (No mapping needed because axes are mapped natively in shader)
            bone_obj.scale_mapped = (pb.scale.x, pb.scale.y, pb.scale.z)
            bone_obj.offset_mapped = (pb.location.x, pb.location.y, pb.location.z)
            bone_obj.rotation_euler_mapped = (pb.rotation_euler.x, pb.rotation_euler.y, pb.rotation_euler.z)

        layer.bone_count = len(layer.bones)
        self.report({'INFO'}, f"Smart Baked/Updated {count} bones successfully.")
        return {'FINISHED'}

class RZM_OT_BlendResizeExport(bpy.types.Operator):
    bl_idname = "rzm.br_export_buffers"
    bl_label = "Export BR Buffers"
    bl_description = "Generate binary .buf files for bone configurations (stride=16)"

    def execute(self, context):
        settings = context.scene.rzm.export_settings
        mod_root = bpy.path.abspath(settings.custom_path) if not settings.use_game_path else bpy.path.abspath(settings.custom_path)
             
        if not mod_root or not os.path.exists(mod_root):
            self.report({'ERROR'}, "Invalid export path. Please set it in Export Settings.")
            return {'CANCELLED'}
            
        br = context.scene.rzm.addons.blend_resize
        output_dir = os.path.join(mod_root, "BR")
        os.makedirs(output_dir, exist_ok=True)
        
        for comp in br.component_mappings:
            if not comp.layers: continue
            
            buffer_data = bytearray()
            
            for layer in comp.layers:
                # [0] Header: 69, Count, SlotID, (0.0 padding)
                h1 = struct.pack('4f', 69.0, float(layer.bone_count), float(layer.slot_id), 0.0)
                buffer_data.extend(h1)
                
                # [1] Head XYZ, (0.0 padding)
                h2 = struct.pack('4f', layer.head_mapped[0], layer.head_mapped[1], layer.head_mapped[2], 0.0)
                buffer_data.extend(h2)
                
                # [2] Bone X XYZ, (0.0 padding)
                h3 = struct.pack('4f', layer.bone_x_mapped[0], layer.bone_x_mapped[1], layer.bone_x_mapped[2], 0.0)
                buffer_data.extend(h3)
                
                # [3] Bone Y XYZ, (0.0 padding)
                h4 = struct.pack('4f', layer.bone_y_mapped[0], layer.bone_y_mapped[1], layer.bone_y_mapped[2], 0.0)
                buffer_data.extend(h4)
                
                # [N] Bones: Scale/BoneID, Offset, Rotation (3 float4 instances)
                for bone in layer.bones:
                    # 1. Scale X/Y/Z, BoneID
                    b_data1 = struct.pack('4f', bone.scale_mapped[0], bone.scale_mapped[1], bone.scale_mapped[2], float(bone.bone_index))
                    buffer_data.extend(b_data1)
                    # 2. Offset X/Y/Z, Pad
                    b_data2 = struct.pack('4f', bone.offset_mapped[0], bone.offset_mapped[1], bone.offset_mapped[2], 0.0)
                    buffer_data.extend(b_data2)
                    # 3. Rotation Euler X/Y/Z, Pad
                    b_data3 = struct.pack('4f', bone.rotation_euler_mapped[0], bone.rotation_euler_mapped[1], bone.rotation_euler_mapped[2], 0.0)
                    buffer_data.extend(b_data3)
            
            file_name = f"{comp.name}Data.buf"
            with open(os.path.join(output_dir, file_name), 'wb') as f:
                f.write(buffer_data)
                
        self.report({'INFO'}, "BlendResize layers exported successfully to binary buffers.")
        return {'FINISHED'}

BR_CLIPBOARD = {
    "head": None,
    "x": None,
    "y": None,
    "b_scale": None,
    "b_offset": None,
    "b_rot": None
}

class RZM_OT_BRCopyCoords(bpy.types.Operator):
    bl_idname = "rzm.br_copy_coords"
    bl_label = "Copy Local Anchor"
    bl_description = "Copy spatial anchor data to clipboard to sync multiple scaling parts"
    
    comp_index: bpy.props.IntProperty(default=-1)
    layer_index: bpy.props.IntProperty(default=-1)
    
    def execute(self, context):
        comp = context.scene.rzm.addons.blend_resize.component_mappings[self.comp_index]
        layer = comp.layers[self.layer_index]
        BR_CLIPBOARD["head"] = list(layer.head_mapped)
        BR_CLIPBOARD["x"] = list(layer.bone_x_mapped)
        BR_CLIPBOARD["y"] = list(layer.bone_y_mapped)
        self.report({'INFO'}, "Coordinate Space Anchor Copied!")
        return {'FINISHED'}

class RZM_OT_BRPasteCoords(bpy.types.Operator):
    bl_idname = "rzm.br_paste_coords"
    bl_label = "Paste Local Anchor"
    bl_description = "Paste spatial anchor data to ensure contiguous deformation"
    
    comp_index: bpy.props.IntProperty(default=-1)
    layer_index: bpy.props.IntProperty(default=-1)
    
    @classmethod
    def poll(cls, context):
        return BR_CLIPBOARD["head"] is not None
        
    def execute(self, context):
        comp = context.scene.rzm.addons.blend_resize.component_mappings[self.comp_index]
        layer = comp.layers[self.layer_index]
        layer.head_mapped = BR_CLIPBOARD["head"]
        layer.bone_x_mapped = BR_CLIPBOARD["x"]
        layer.bone_y_mapped = BR_CLIPBOARD["y"]
        self.report({'INFO'}, "Coordinate Space Anchor Pasted!")
        return {'FINISHED'}

class RZM_OT_BRCopyBoneCoords(bpy.types.Operator):
    bl_idname = "rzm.br_copy_bone_coords"
    bl_label = "Copy Bone Transform"
    bl_description = "Copy bone transformation values (Scale, Offset, Rotation)"
    
    comp_index: bpy.props.IntProperty(default=-1)
    layer_index: bpy.props.IntProperty(default=-1)
    bone_index: bpy.props.IntProperty(default=-1)
    
    def execute(self, context):
        comp = context.scene.rzm.addons.blend_resize.component_mappings[self.comp_index]
        layer = comp.layers[self.layer_index]
        bone = layer.bones[self.bone_index]
        BR_CLIPBOARD["b_scale"] = list(bone.scale_mapped)
        BR_CLIPBOARD["b_offset"] = list(bone.offset_mapped)
        BR_CLIPBOARD["b_rot"] = list(bone.rotation_euler_mapped)
        self.report({'INFO'}, "Bone Transformations Copied!")
        return {'FINISHED'}

class RZM_OT_BRPasteBoneCoords(bpy.types.Operator):
    bl_idname = "rzm.br_paste_bone_coords"
    bl_label = "Paste Bone Transform"
    bl_description = "Paste bone transformation values"
    
    comp_index: bpy.props.IntProperty(default=-1)
    layer_index: bpy.props.IntProperty(default=-1)
    bone_index: bpy.props.IntProperty(default=-1)
    
    @classmethod
    def poll(cls, context):
        return BR_CLIPBOARD["b_scale"] is not None
        
    def execute(self, context):
        comp = context.scene.rzm.addons.blend_resize.component_mappings[self.comp_index]
        layer = comp.layers[self.layer_index]
        bone = layer.bones[self.bone_index]
        bone.scale_mapped = BR_CLIPBOARD["b_scale"]
        bone.offset_mapped = BR_CLIPBOARD["b_offset"]
        bone.rotation_euler_mapped = BR_CLIPBOARD["b_rot"]
        self.report({'INFO'}, "Bone Transformations Pasted!")
        return {'FINISHED'}
classes_to_register = (
    RZM_OT_BRAddGroup,
    RZM_OT_BRRemoveGroup,
    RZM_OT_BRAddComp,
    RZM_OT_BRRemoveComp,
    RZM_OT_BRSelectComp,
    RZM_OT_BRAddLayer,
    RZM_OT_BRRemoveLayer,
    RZM_OT_BRAddLayerBone,
    RZM_OT_BRRemoveLayerBone,
    RZM_OT_BRBakeLayer,
    RZM_OT_BlendResizeExport,
    RZM_OT_BRCopyCoords,
    RZM_OT_BRPasteCoords,
    RZM_OT_BRCopyBoneCoords,
    RZM_OT_BRPasteBoneCoords,
)
