# RZMenu/data/p_blend_resize.py
import bpy
from bpy.props import StringProperty, IntProperty, FloatProperty, BoolProperty, EnumProperty, CollectionProperty, FloatVectorProperty

class RZMBResizeBakedBone(bpy.types.PropertyGroup):
    bone_index: IntProperty(name="Bone Index", default=0, min=0)
    scale_mapped: FloatVectorProperty(name="Scale (Mapped)", size=3, default=(1.0, 1.0, 1.0))

class RZMBResizeBakedLayer(bpy.types.PropertyGroup):
    name: StringProperty(name="Layer Name", default="Layer")
    slot_id: IntProperty(name="Slot ID", default=0, min=0, max=11)
    bone_count: IntProperty(name="Bone Count", default=0, min=0)
    
    head_mapped: FloatVectorProperty(name="Head (Mapped)", size=3, default=(0.0, 0.0, 0.0))
    bone_x_mapped: FloatVectorProperty(name="Bone X (Mapped)", size=3, default=(1.0, 0.0, 0.0))
    bone_y_mapped: FloatVectorProperty(name="Bone Y (Mapped)", size=3, default=(0.0, 1.0, 0.0))
    
    bones: CollectionProperty(type=RZMBResizeBakedBone)
    active_bone_index: IntProperty(default=-1)

class RZMComponentMapping(bpy.types.PropertyGroup):
    name: StringProperty(name="Component Map", default="")
    layers: CollectionProperty(type=RZMBResizeBakedLayer)
    active_layer_index: IntProperty(default=-1)

class RZMBoneResizeGroup(bpy.types.PropertyGroup):
    name: StringProperty(name="Group Name", default="New Group")
    slot_id: IntProperty(name="Slot ID", default=0, min=0, max=11)
    value_link: StringProperty(name="Value Link", description="Link to project variable ($Value)")

class RZMBResizeSettings(bpy.types.PropertyGroup):
    is_enabled: BoolProperty(name="Enable BlendResize", default=False)
    groups: CollectionProperty(type=RZMBoneResizeGroup)
    component_mappings: CollectionProperty(type=RZMComponentMapping)
